"""판정 결과를 다음 조치로 바꾸는 계층.

이 모듈이 담고 있는 설계 판단은 하나다.

    경로는 신뢰도 순위로 정하지 않는다.
    사전에 정의해 승인해 둔 '클래스 - 조치 - 목적지' 대응표를 조회한다.

그래서 모델을 바꾸거나 클래스를 늘려도 이 파일의 구조는 바뀌지 않고,
바뀌는 것은 configs/classes.yaml 한 장이다.

판정할 수 없는 경우(대응표에 없는 클래스, 신뢰도 미달, 검출 없음)에는
자동으로 처분하지 않고 사람 쪽으로 넘긴다. 보수적 실패가 기본값이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Action(str, Enum):
    """대응표가 지정할 수 있는 조치."""

    ROBOT_REPLACE = "ROBOT_REPLACE"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    VERIFY_COMPLETION = "VERIFY_COMPLETION"


class Reason(str, Enum):
    """왜 그 조치가 나왔는지. 로그와 테스트가 이 값을 본다."""

    TABLE_HIT = "TABLE_HIT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    UNKNOWN_CLASS = "UNKNOWN_CLASS"
    NO_DETECTION = "NO_DETECTION"


@dataclass(frozen=True)
class Detection:
    """모델 출력 한 건."""

    class_name: str
    confidence: float


@dataclass(frozen=True)
class Decision:
    """대응표 조회 결과."""

    action: Action
    destination: str
    requires_human: bool
    reason: Reason
    source_class: str | None
    confidence: float | None

    @property
    def is_fallback(self) -> bool:
        return self.reason is not Reason.TABLE_HIT


class DecisionPolicy:
    """설정에서 읽은 대응표를 조회하는 객체."""

    def __init__(self, config: dict[str, Any]):
        self._table = config["action_table"]
        self._fallback = config["fallback"]
        self._min_confidence = float(
            config.get("detection", {}).get("min_confidence", 0.0)
        )

    @property
    def min_confidence(self) -> float:
        return self._min_confidence

    def decide(self, detection: Detection | None) -> Decision:
        """검출 한 건을 조치로 바꾼다.

        Args:
            detection: 모델 출력. 아무것도 검출되지 않았으면 None.

        Returns:
            Decision. 대응표에 걸리지 않은 모든 경우는 fallback 으로 나가며,
            fallback 은 설정 검증 단계에서 requires_human=True 가 강제된다.
        """
        if detection is None:
            return self._fallback_decision(Reason.NO_DETECTION, None, None)

        if detection.confidence < self._min_confidence:
            return self._fallback_decision(
                Reason.LOW_CONFIDENCE, detection.class_name, detection.confidence
            )

        entry = self._table.get(detection.class_name)
        if entry is None:
            return self._fallback_decision(
                Reason.UNKNOWN_CLASS, detection.class_name, detection.confidence
            )

        return Decision(
            action=Action(entry["action"]),
            destination=str(entry["destination"]),
            requires_human=bool(entry["requires_human"]),
            reason=Reason.TABLE_HIT,
            source_class=detection.class_name,
            confidence=detection.confidence,
        )

    def _fallback_decision(
        self, reason: Reason, class_name: str | None, confidence: float | None
    ) -> Decision:
        return Decision(
            action=Action(self._fallback["action"]),
            destination=str(self._fallback["destination"]),
            requires_human=bool(self._fallback["requires_human"]),
            reason=reason,
            source_class=class_name,
            confidence=confidence,
        )


def majority_vote(
    detections: list[Detection], required: int, min_confidence: float
) -> Detection | None:
    """연속 프레임의 판정을 다수결로 모은다.

    단일 프레임 판정은 주행 중 흔들림 한 번에 경로가 바뀐다.
    임계값을 넘긴 검출만 세고, 최다 클래스가 required 표 이상일 때만 확정한다.
    확정하지 못하면 None 을 돌려주고, 호출부는 fallback 으로 간다.

    ※ 다수결은 이번 재구성에서 넣은 설계다. 당시 코드에 있었다는 근거는 없다.
    """
    if required <= 0:
        raise ValueError("required 는 1 이상이어야 합니다.")

    counts: dict[str, list[float]] = {}
    for det in detections:
        if det.confidence < min_confidence:
            continue
        counts.setdefault(det.class_name, []).append(det.confidence)

    if not counts:
        return None

    winner = max(counts.items(), key=lambda kv: (len(kv[1]), sum(kv[1])))
    name, confidences = winner
    if len(confidences) < required:
        return None

    return Detection(class_name=name, confidence=sum(confidences) / len(confidences))
