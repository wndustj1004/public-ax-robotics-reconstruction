"""하드웨어 경계.

상태 머신은 이 프로토콜만 알고, 그 뒤에 무엇이 있는지 모른다.
그래서 실물 로봇 없이도 같은 로직을 끝까지 돌릴 수 있다.

※ 실물 구현(주행 제어·마커 정차·이기종 로봇 간 통신)은 이 저장소에 없다.
   프로젝트 당시에도 그 부분은 팀원이 작성했고, 코드는 보존되어 있지 않다.
   여기 있는 것은 '무엇을 만족해야 하는가'를 적은 경계면뿐이다.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .decision_policy import Detection


@runtime_checkable
class PerceptionSource(Protocol):
    """카메라 + 판정 모델."""

    def acquire(self) -> Detection | None:
        """판정 대상을 한 번 판정한다. 확정하지 못하면 None."""

    def wait_for_class(
        self, class_name: str, timeout_sec: float
    ) -> Detection | None:
        """특정 클래스가 나타날 때까지 기다린다.

        시간 안에 나타나지 않으면 None. 호출부는 이것을 실패로 처리해야 하며,
        기다린 시간이 지났다는 이유로 성공 처리하면 안 된다.
        """


@runtime_checkable
class DriveBase(Protocol):
    """이동 장치."""

    def travel_to(self, zone: str) -> None:
        """지정한 존 근처까지 이동한다."""

    def dock(self, zone: str) -> bool:
        """마커 기준으로 정차한다.

        검출 즉시 멈추는 것이 아니라, 마커까지의 거리가 설정값 이하가 될 때
        멈춘다는 것이 이 인터페이스의 계약이다. 성공하면 True.
        """

    def stop(self) -> None:
        """구동 정지. 어떤 경로로 끝나든 반드시 호출된다."""


@runtime_checkable
class Manipulator(Protocol):
    """교체 스테이션 쪽 장치."""

    def request_replacement(self) -> None:
        """교체 작업을 요청한다. 완료 여부는 여기서 판단하지 않는다."""

    def handoff_to_human(self) -> None:
        """사람이 가져갈 수 있는 자세로 대상을 놓고 물러난다."""


@runtime_checkable
class Notifier(Protocol):
    """LCD·LED·부저·로그 등 상태 표시."""

    def alert(self, key: str, message: str) -> None:
        """상태를 사람이 읽을 수 있게 표시하고 기록한다."""
