"""한 사이클의 상태 전이.

시나리오(docs/scenario.md)를 상태와 전이로 옮긴 것이다.
하드웨어를 직접 만지지 않는다. 주행·정차·인계는 interfaces.py 의
프로토콜을 통해서만 부르고, 시뮬레이션이든 실물이든 같은 코드가 돈다.

설계상 중요한 두 가지.

1. 완료 판정은 '신호를 받았다'가 아니라 'normal 을 다시 검출했다'로 한다.
   지시받은 쪽이 끝났다고 말한 것과, 결과가 실제로 그렇게 된 것은 다르다.
   재검출에 실패하면 성공으로 넘기지 않고 타임아웃으로 기록한다.

2. HUMAN_FIX 는 사람의 판단을 대신하지 않는다.
   이 상태 머신은 사람이 판단할 수 있는 지점까지 안전하게 이송·인계하고
   끝난다. 판정·조사·영향평가는 상태 머신 밖에 있다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .decision_policy import Action, Decision, DecisionPolicy, Detection
from .interfaces import DriveBase, PerceptionSource, Manipulator, Notifier


class State(str, Enum):
    IDLE = "IDLE"                       # 대기
    ACQUIRE = "ACQUIRE"                 # 대상 인식
    TRIAGE = "TRIAGE"                   # 판정
    ROUTE = "ROUTE"                     # 경로 선택
    TRANSIT = "TRANSIT"                 # 이송
    DOCK = "DOCK"                       # 마커 정차
    ROBOT_FIX = "ROBOT_FIX"             # 로봇 교체 처리
    HUMAN_HANDOFF = "HUMAN_HANDOFF"     # 사람 QC 인계
    VERIFY = "VERIFY"                   # 완료 확인
    RETURN = "RETURN"                   # 복귀
    DONE = "DONE"                       # 정상 종료
    SAFE_STOP = "SAFE_STOP"             # 오류 · 안전 정지


#: 허용된 전이만 담은 표. 여기에 없는 전이는 InvalidTransition 이다.
#: SAFE_STOP 은 종료 상태(DONE) 를 제외한 어느 상태에서든 갈 수 있다.
ALLOWED: dict[State, frozenset[State]] = {
    State.IDLE: frozenset({State.ACQUIRE}),
    State.ACQUIRE: frozenset({State.TRIAGE}),
    State.TRIAGE: frozenset({State.ROUTE}),
    State.ROUTE: frozenset({State.TRANSIT}),
    State.TRANSIT: frozenset({State.DOCK}),
    State.DOCK: frozenset({State.ROBOT_FIX, State.HUMAN_HANDOFF}),
    State.ROBOT_FIX: frozenset({State.VERIFY}),
    State.HUMAN_HANDOFF: frozenset({State.RETURN}),
    State.VERIFY: frozenset({State.RETURN}),
    State.RETURN: frozenset({State.DONE}),
    State.DONE: frozenset(),
    State.SAFE_STOP: frozenset(),
}

TERMINAL = frozenset({State.DONE, State.SAFE_STOP})


class InvalidTransition(RuntimeError):
    """표에 없는 상태 전이를 시도했을 때."""


@dataclass
class MissionEvent:
    state: State
    note: str


@dataclass
class MissionResult:
    final_state: State
    decision: Decision | None
    events: list[MissionEvent] = field(default_factory=list)
    verified: bool | None = None       # ROBOT_FIX 루트에서만 의미가 있다
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.final_state is State.DONE


class MissionStateMachine:
    """한 장의 플레이트를 처리하는 한 사이클."""

    def __init__(
        self,
        policy: DecisionPolicy,
        perception: PerceptionSource,
        drive: DriveBase,
        manipulator: Manipulator,
        notifier: Notifier,
        *,
        verify_class: str = "normal",
        verify_timeout_sec: float = 120.0,
    ):
        self._policy = policy
        self._perception = perception
        self._drive = drive
        self._manipulator = manipulator
        self._notifier = notifier
        self._verify_class = verify_class
        self._verify_timeout = verify_timeout_sec

        self.state: State = State.IDLE
        self.events: list[MissionEvent] = []

    # ---------------------------------------------------------------- 전이
    def transition(self, target: State, note: str = "") -> None:
        """표에 있는 전이만 허용한다."""
        if self.state in TERMINAL:
            raise InvalidTransition(f"{self.state.value} 는 종료 상태입니다.")
        if target is State.SAFE_STOP:
            self._record(target, note or "안전 정지")
            return
        if target not in ALLOWED[self.state]:
            raise InvalidTransition(
                f"허용되지 않은 전이: {self.state.value} -> {target.value}"
            )
        self._record(target, note)

    def safe_stop(self, note: str) -> None:
        self._notifier.alert("SAFE_STOP", note)
        self._record(State.SAFE_STOP, note)

    def _record(self, target: State, note: str) -> None:
        self.state = target
        self.events.append(MissionEvent(state=target, note=note))

    # ---------------------------------------------------------------- 실행
    def run(self) -> MissionResult:
        """한 사이클을 끝까지 돌린다.

        어떤 단계에서 예외가 나든 SAFE_STOP 으로 떨어뜨리고,
        구동계를 멈춘 뒤 결과를 돌려준다. 예외를 삼키지 않고 error 에 남긴다.
        """
        decision: Decision | None = None
        verified: bool | None = None
        try:
            self.transition(State.ACQUIRE, "판정 대상 접근")
            detection = self._perception.acquire()

            self.transition(State.TRIAGE, "대응표 조회")
            decision = self._policy.decide(detection)
            self._notifier.alert(
                "TRIAGE",
                f"{decision.reason.value} -> {decision.action.value}"
                f" ({decision.destination})",
            )

            self.transition(State.ROUTE, f"목적지 {decision.destination}")
            self.transition(State.TRANSIT, "이송 시작")
            self._drive.travel_to(decision.destination)

            self.transition(State.DOCK, "마커 정차")
            if not self._drive.dock(decision.destination):
                self.safe_stop(f"{decision.destination} 마커 정차 실패")
                return self._result(decision, verified)

            if decision.action is Action.ROBOT_REPLACE:
                self.transition(State.ROBOT_FIX, "매니퓰레이터 교체 요청")
                self._manipulator.request_replacement()

                self.transition(State.VERIFY, "완료 재인식 대기")
                verified = self._verify_completion()
                if not verified:
                    self.safe_stop(
                        f"{self._verify_timeout:.0f}초 안에 "
                        f"'{self._verify_class}' 를 재검출하지 못함"
                    )
                    return self._result(decision, verified)
                self.transition(State.RETURN, "교체 확인 후 복귀")
            else:
                # HUMAN_REVIEW 및 모든 fallback.
                # 여기서 하는 일은 '판단'이 아니라 '인계'다.
                self.transition(State.HUMAN_HANDOFF, "사람 QC 인계")
                self._manipulator.handoff_to_human()
                self._notifier.alert("HANDOFF", "판정은 자격자가 수행합니다.")
                self.transition(State.RETURN, "인계 후 복귀")

            self._drive.travel_to("ZONE1")
            self.transition(State.DONE, "복귀 완료")
            return self._result(decision, verified)

        except InvalidTransition:
            raise
        except Exception as exc:  # noqa: BLE001 - 어떤 실패든 안전 정지로 수렴시킨다
            self.safe_stop(f"예외: {exc}")
            return self._result(decision, verified, error=str(exc))
        finally:
            self._drive.stop()

    def _verify_completion(self) -> bool:
        detection = self._perception.wait_for_class(
            self._verify_class, timeout_sec=self._verify_timeout
        )
        return detection is not None

    def _result(
        self,
        decision: Decision | None,
        verified: bool | None,
        error: str | None = None,
    ) -> MissionResult:
        return MissionResult(
            final_state=self.state,
            decision=decision,
            events=list(self.events),
            verified=verified,
            error=error,
        )
