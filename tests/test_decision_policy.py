"""대응표 조회 테스트.

확인하는 것:
  · 정의된 클래스가 정해진 조치·목적지로 나가는가
  · 신뢰도 미달 / 모르는 클래스 / 검출 없음이 전부 사람 쪽으로 가는가
  · 다수결이 흔들리는 판정을 걸러 내는가
  · 설정 파일이 규약을 어기면 로드 단계에서 막히는가
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ConfigError, load_config
from src.decision_policy import (
    Action,
    DecisionPolicy,
    Detection,
    Reason,
    majority_vote,
)


class DecisionPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config()

    def setUp(self):
        self.policy = DecisionPolicy(self.cfg)

    # --------------------------------------------------- 정상 매핑
    def test_normal_maps_to_verification(self):
        d = self.policy.decide(Detection("normal", 0.95))
        self.assertIs(d.action, Action.VERIFY_COMPLETION)
        self.assertIs(d.reason, Reason.TABLE_HIT)
        self.assertFalse(d.requires_human)

    def test_robotfix_routes_to_robot_station(self):
        d = self.policy.decide(Detection("robotfix", 0.92))
        self.assertIs(d.action, Action.ROBOT_REPLACE)
        self.assertEqual(d.destination, "ZONE2")
        self.assertFalse(d.requires_human)
        self.assertFalse(d.is_fallback)

    def test_humanfix_routes_to_human_station(self):
        d = self.policy.decide(Detection("humanfix", 0.85))
        self.assertIs(d.action, Action.HUMAN_REVIEW)
        self.assertEqual(d.destination, "ZONE3")
        self.assertTrue(d.requires_human)

    def test_every_declared_class_has_an_entry(self):
        for name in self.cfg["class_names"]:
            with self.subTest(cls=name):
                d = self.policy.decide(Detection(name, 1.0))
                self.assertIs(d.reason, Reason.TABLE_HIT)

    # --------------------------------------------------- 보수적 실패
    def test_low_confidence_falls_back_to_human(self):
        below = self.policy.min_confidence - 0.01
        d = self.policy.decide(Detection("robotfix", below))
        self.assertIs(d.reason, Reason.LOW_CONFIDENCE)
        self.assertTrue(d.requires_human)
        self.assertIs(d.action, Action.HUMAN_REVIEW)

    def test_confidence_exactly_at_threshold_is_accepted(self):
        d = self.policy.decide(Detection("robotfix", self.policy.min_confidence))
        self.assertIs(d.reason, Reason.TABLE_HIT)

    def test_unknown_class_falls_back_to_human(self):
        d = self.policy.decide(Detection("contaminated", 0.99))
        self.assertIs(d.reason, Reason.UNKNOWN_CLASS)
        self.assertTrue(d.requires_human)

    def test_no_detection_falls_back_to_human(self):
        d = self.policy.decide(None)
        self.assertIs(d.reason, Reason.NO_DETECTION)
        self.assertTrue(d.requires_human)
        self.assertIsNone(d.source_class)

    def test_no_fallback_path_is_ever_unattended(self):
        cases = [None, Detection("robotfix", 0.1), Detection("???", 0.99)]
        for case in cases:
            with self.subTest(case=case):
                self.assertTrue(self.policy.decide(case).requires_human)


class MajorityVoteTest(unittest.TestCase):
    def test_majority_wins(self):
        window = [
            Detection("robotfix", 0.9),
            Detection("robotfix", 0.8),
            Detection("humanfix", 0.9),
            Detection("robotfix", 0.85),
        ]
        winner = majority_vote(window, required=3, min_confidence=0.7)
        self.assertIsNotNone(winner)
        self.assertEqual(winner.class_name, "robotfix")

    def test_no_class_reaches_quorum(self):
        window = [Detection("robotfix", 0.9), Detection("humanfix", 0.9)]
        self.assertIsNone(majority_vote(window, required=3, min_confidence=0.7))

    def test_low_confidence_frames_are_not_counted(self):
        window = [Detection("robotfix", 0.5)] * 5
        self.assertIsNone(majority_vote(window, required=3, min_confidence=0.7))

    def test_empty_window(self):
        self.assertIsNone(majority_vote([], required=1, min_confidence=0.7))

    def test_required_must_be_positive(self):
        with self.assertRaises(ValueError):
            majority_vote([], required=0, min_confidence=0.7)


class ConfigValidationTest(unittest.TestCase):
    def _write(self, body: str) -> Path:
        import tempfile

        tmp = Path(tempfile.mkdtemp()) / "classes.yaml"
        tmp.write_text(body, encoding="utf-8")
        return tmp

    def test_missing_file_is_reported_clearly(self):
        with self.assertRaises(ConfigError) as ctx:
            load_config("does/not/exist.yaml")
        self.assertIn("찾을 수 없습니다", str(ctx.exception))

    def test_class_without_action_entry_is_rejected(self):
        path = self._write(
            "class_names: [normal, robotfix]\n"
            "action_table:\n"
            "  normal: {action: VERIFY_COMPLETION, destination: ZONE2,"
            " requires_human: false}\n"
            "fallback: {action: HUMAN_REVIEW, destination: ZONE3,"
            " requires_human: true}\n"
            "detection: {min_confidence: 0.7}\n"
        )
        with self.assertRaises(ConfigError):
            load_config(path)

    def test_fallback_must_require_human(self):
        path = self._write(
            "class_names: [normal]\n"
            "action_table:\n"
            "  normal: {action: VERIFY_COMPLETION, destination: ZONE2,"
            " requires_human: false}\n"
            "fallback: {action: ROBOT_REPLACE, destination: ZONE2,"
            " requires_human: false}\n"
            "detection: {min_confidence: 0.7}\n"
        )
        with self.assertRaises(ConfigError) as ctx:
            load_config(path)
        self.assertIn("requires_human", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
