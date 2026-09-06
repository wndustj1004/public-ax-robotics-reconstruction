#!/usr/bin/env python3
"""simulation 모드로 한 사이클을 돌려 본다.

하드웨어도 모델도 쓰지 않는다. 확인하는 것은 두 가지뿐이다.
  · 판정 결과가 대응표를 통해 어떤 조치·목적지로 이어지는가
  · 그 조치가 어떤 상태 전이를 밟고 어디서 끝나는가

사용법:
    python scripts/run_simulation.py                 # 시나리오 전부
    python scripts/run_simulation.py --case robotfix
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ConfigError, load_config
from src.decision_policy import DecisionPolicy, Detection
from src.simulation import (
    ConsoleNotifier,
    ScriptedPerception,
    SimulatedDrive,
    SimulatedManipulator,
)
from src.state_machine import MissionStateMachine

# (이름, 첫 판정, 재검출 성공 여부, 정차 성공 여부)
CASES: dict[str, tuple[Detection | None, bool, bool]] = {
    "robotfix": (Detection("robotfix", 0.93), True, True),
    "humanfix": (Detection("humanfix", 0.88), True, True),
    "low-confidence": (Detection("robotfix", 0.42), True, True),
    "unknown-class": (Detection("contaminated", 0.95), True, True),
    "no-detection": (None, True, True),
    "verify-timeout": (Detection("robotfix", 0.91), False, True),
    "dock-failed": (Detection("robotfix", 0.91), True, False),
}


def run_case(name: str, cfg: dict) -> bool:
    detection, verify_ok, dock_ok = CASES[name]
    policy = DecisionPolicy(cfg)
    perception = ScriptedPerception(script=[detection], verify_returns=verify_ok)
    drive = SimulatedDrive(dock_succeeds=dock_ok)
    machine = MissionStateMachine(
        policy=policy,
        perception=perception,
        drive=drive,
        manipulator=SimulatedManipulator(),
        notifier=ConsoleNotifier(echo=True),
        verify_class=cfg["verification"]["expect_class"],
        verify_timeout_sec=cfg["verification"]["timeout_sec"],
    )

    given = (
        f"{detection.class_name} conf={detection.confidence:.2f}"
        if detection
        else "검출 없음"
    )
    print(f"\n=== {name} ===")
    print(f"  입력  : {given}")

    result = machine.run()
    d = result.decision
    if d is not None:
        print(
            f"  대응표: {d.reason.value} -> {d.action.value} / {d.destination}"
            f" (사람 판단 필요: {'예' if d.requires_human else '아니오'})"
        )
    print("  전이  : " + " -> ".join(e.state.value for e in result.events))
    print(f"  결과  : {result.final_state.value}")
    return result.succeeded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=sorted(CASES), help="한 가지만 실행")
    parser.add_argument("--config", help="classes.yaml 경로")
    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"[설정 오류] {exc}", file=sys.stderr)
        return 2

    names = [args.case] if args.case else list(CASES)
    print("simulation 모드 — 하드웨어와 모델을 사용하지 않습니다.")
    for name in names:
        run_case(name, cfg)

    print(
        "\n※ 위 결과는 로직의 상태 전이만 확인한 것입니다. "
        "로봇 동작이나 인식 성능과는 무관합니다."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
