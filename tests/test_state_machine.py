"""상태 전이 테스트.

확인하는 것:
  · 두 루트가 각각 정해진 상태를 밟고 끝나는가
  · 재검출 실패를 성공으로 넘기지 않는가
  · 정차 실패·예외가 안전 정지로 수렴하고 구동계가 멈추는가
  · 표에 없는 전이가 거부되는가
  · 사람 판단이 필요한 경우 로봇이 판정을 대신하지 않는가
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.decision_policy import DecisionPolicy, Detection
from src.simulation import (
    ConsoleNotifier,
    ScriptedPerception,
    SimulatedDrive,
    SimulatedManipulator,
)
from src.state_machine import (
    ALLOWED,
    InvalidTransition,
    MissionStateMachine,
    State,
)


def build(detection, *, verify_ok=True, dock_ok=True, cfg=None):
    cfg = cfg or load_config()
    drive = SimulatedDrive(dock_succeeds=dock_ok)
    manipulator = SimulatedManipulator()
    machine = MissionStateMachine(
        policy=DecisionPolicy(cfg),
        perception=ScriptedPerception(script=[detection], verify_returns=verify_ok),
        drive=drive,
        manipulator=manipulator,
        notifier=ConsoleNotifier(),
        verify_class=cfg["verification"]["expect_class"],
        verify_timeout_sec=cfg["verification"]["timeout_sec"],
    )
    return machine, drive, manipulator


class RobotFixRouteTest(unittest.TestCase):
    def test_completes_through_verification(self):
        machine, drive, manipulator = build(Detection("robotfix", 0.93))
        result = machine.run()

        self.assertTrue(result.succeeded)
        self.assertIs(result.final_state, State.DONE)
        self.assertTrue(result.verified)
        self.assertIn("request_replacement", manipulator.log)
        self.assertIn("travel_to:ZONE2", drive.log)
        self.assertIn("travel_to:ZONE1", drive.log)

    def test_visits_verify_state(self):
        machine, _, _ = build(Detection("robotfix", 0.93))
        result = machine.run()
        states = [e.state for e in result.events]
        self.assertIn(State.ROBOT_FIX, states)
        self.assertIn(State.VERIFY, states)
        self.assertNotIn(State.HUMAN_HANDOFF, states)

    def test_timeout_is_not_treated_as_success(self):
        machine, drive, _ = build(Detection("robotfix", 0.93), verify_ok=False)
        result = machine.run()

        self.assertFalse(result.succeeded)
        self.assertIs(result.final_state, State.SAFE_STOP)
        self.assertFalse(result.verified)
        self.assertIn("stop", drive.log)


class HumanFixRouteTest(unittest.TestCase):
    def test_hands_off_without_deciding(self):
        machine, drive, manipulator = build(Detection("humanfix", 0.88))
        result = machine.run()

        self.assertTrue(result.succeeded)
        self.assertIn("handoff_to_human", manipulator.log)
        self.assertIn("travel_to:ZONE3", drive.log)
        # 사람 루트에서는 로봇이 교체를 실행하지 않는다.
        self.assertNotIn("request_replacement", manipulator.log)
        # 완료 검증도 하지 않는다. 판정은 사람 몫이다.
        self.assertIsNone(result.verified)

    def test_route_does_not_enter_robot_fix(self):
        machine, _, _ = build(Detection("humanfix", 0.88))
        states = [e.state for e in machine.run().events]
        self.assertIn(State.HUMAN_HANDOFF, states)
        self.assertNotIn(State.ROBOT_FIX, states)


class FallbackRouteTest(unittest.TestCase):
    def test_low_confidence_goes_to_human_station(self):
        machine, drive, manipulator = build(Detection("robotfix", 0.30))
        result = machine.run()
        self.assertTrue(result.succeeded)
        self.assertIn("travel_to:ZONE3", drive.log)
        self.assertIn("handoff_to_human", manipulator.log)
        self.assertNotIn("request_replacement", manipulator.log)

    def test_unknown_class_goes_to_human_station(self):
        machine, drive, _ = build(Detection("mould", 0.99))
        machine.run()
        self.assertIn("travel_to:ZONE3", drive.log)

    def test_no_detection_goes_to_human_station(self):
        machine, drive, _ = build(None)
        machine.run()
        self.assertIn("travel_to:ZONE3", drive.log)


class SafeStopTest(unittest.TestCase):
    def test_dock_failure_stops_safely(self):
        machine, drive, manipulator = build(
            Detection("robotfix", 0.93), dock_ok=False
        )
        result = machine.run()

        self.assertIs(result.final_state, State.SAFE_STOP)
        self.assertNotIn("request_replacement", manipulator.log)
        self.assertIn("stop", drive.log)

    def test_exception_is_captured_not_swallowed(self):
        class ExplodingDrive(SimulatedDrive):
            def travel_to(self, zone):
                super().travel_to(zone)
                raise RuntimeError("모터 통신 두절")

        cfg = load_config()
        drive = ExplodingDrive()
        machine = MissionStateMachine(
            policy=DecisionPolicy(cfg),
            perception=ScriptedPerception(script=[Detection("robotfix", 0.93)]),
            drive=drive,
            manipulator=SimulatedManipulator(),
            notifier=ConsoleNotifier(),
        )
        result = machine.run()

        self.assertIs(result.final_state, State.SAFE_STOP)
        self.assertIn("모터 통신 두절", result.error)
        self.assertEqual(drive.log[-1], "stop")


class TransitionTableTest(unittest.TestCase):
    def test_disallowed_transition_is_rejected(self):
        machine, _, _ = build(Detection("robotfix", 0.93))
        with self.assertRaises(InvalidTransition):
            machine.transition(State.ROBOT_FIX)   # IDLE -> ROBOT_FIX 는 없다

    def test_cannot_skip_verification(self):
        machine, _, _ = build(Detection("robotfix", 0.93))
        machine.transition(State.ACQUIRE)
        machine.transition(State.TRIAGE)
        machine.transition(State.ROUTE)
        machine.transition(State.TRANSIT)
        machine.transition(State.DOCK)
        machine.transition(State.ROBOT_FIX)
        with self.assertRaises(InvalidTransition):
            machine.transition(State.RETURN)      # VERIFY 를 건너뛸 수 없다

    def test_safe_stop_is_reachable_from_any_live_state(self):
        for state in ALLOWED:
            if state in (State.DONE, State.SAFE_STOP):
                continue
            with self.subTest(state=state):
                machine, _, _ = build(Detection("robotfix", 0.93))
                machine.state = state
                machine.safe_stop("테스트")
                self.assertIs(machine.state, State.SAFE_STOP)

    def test_terminal_states_do_not_continue(self):
        machine, _, _ = build(Detection("robotfix", 0.93))
        machine.run()
        with self.assertRaises(InvalidTransition):
            machine.transition(State.ACQUIRE)

    def test_table_has_no_dangling_targets(self):
        for source, targets in ALLOWED.items():
            for target in targets:
                with self.subTest(edge=f"{source}->{target}"):
                    self.assertIn(target, ALLOWED)


if __name__ == "__main__":
    unittest.main()
