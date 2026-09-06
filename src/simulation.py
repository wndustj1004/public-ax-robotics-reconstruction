"""시뮬레이션 구현.

하드웨어가 없는 곳에서 상태 전이와 대응표 조회를 끝까지 돌려 보기 위한 것이다.
실제 로봇의 거동을 모사하지 않는다. 주행 시간, 모터 응답, 통신 지연을 흉내 내지
않으며, 여기서 나온 결과는 어떤 성능 지표도 되지 못한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .decision_policy import Detection


@dataclass
class ScriptedPerception:
    """미리 정해 둔 판정 결과를 순서대로 돌려주는 인식기.

    Args:
        script: acquire() 가 호출될 때마다 앞에서부터 꺼낼 판정 결과.
        verify_returns: wait_for_class() 가 성공할지 여부.
            False 면 타임아웃(None)을 돌려준다.
    """

    script: list[Detection | None] = field(default_factory=list)
    verify_returns: bool = True
    calls: list[str] = field(default_factory=list)

    def acquire(self) -> Detection | None:
        self.calls.append("acquire")
        if not self.script:
            return None
        return self.script.pop(0)

    def wait_for_class(self, class_name: str, timeout_sec: float) -> Detection | None:
        self.calls.append(f"wait:{class_name}")
        if not self.verify_returns:
            return None
        return Detection(class_name=class_name, confidence=1.0)


@dataclass
class SimulatedDrive:
    """이동 명령을 기록만 하는 구동계."""

    dock_succeeds: bool = True
    log: list[str] = field(default_factory=list)

    def travel_to(self, zone: str) -> None:
        self.log.append(f"travel_to:{zone}")

    def dock(self, zone: str) -> bool:
        self.log.append(f"dock:{zone}")
        return self.dock_succeeds

    def stop(self) -> None:
        self.log.append("stop")


@dataclass
class SimulatedManipulator:
    log: list[str] = field(default_factory=list)

    def request_replacement(self) -> None:
        self.log.append("request_replacement")

    def handoff_to_human(self) -> None:
        self.log.append("handoff_to_human")


@dataclass
class ConsoleNotifier:
    """표시 내용을 모아 두고, 원하면 화면에도 찍는다."""

    echo: bool = False
    log: list[tuple[str, str]] = field(default_factory=list)

    def alert(self, key: str, message: str) -> None:
        self.log.append((key, message))
        if self.echo:
            print(f"  [{key}] {message}")
