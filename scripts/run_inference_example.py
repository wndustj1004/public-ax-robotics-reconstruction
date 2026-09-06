#!/usr/bin/env python3
"""실제 모델로 한 장을 판정해 조치까지 뽑아 보는 예제.

학습된 가중치가 있어야 돌아간다. 이 저장소에는 가중치가 들어 있지 않으므로,
그대로 실행하면 무엇이 없는지 알려 주고 종료한다.

사용법:
    python scripts/run_inference_example.py --weights runs/train/weights/best.pt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ConfigError, load_config
from src.decision_policy import DecisionPolicy
from src.inference import ModelNotAvailable, YoloPerception


class _SingleImageCamera:
    """이미지 파일 한 장을 프레임으로 내주는 최소 카메라 대역."""

    def __init__(self, image_path: Path):
        self._path = image_path
        self._served = False

    def get_frame(self):
        if self._served:
            return None
        try:
            import cv2
        except ImportError as exc:
            raise ModelNotAvailable(
                "opencv-python 이 필요합니다.  pip install -r requirements.txt"
            ) from exc
        frame = cv2.imread(str(self._path))
        if frame is None:
            raise FileNotFoundError(f"이미지를 열 수 없습니다: {self._path}")
        self._served = True
        return frame


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", required=True, help="학습된 .pt 경로")
    parser.add_argument("--image", required=True, help="판정할 이미지 경로")
    parser.add_argument("--config", help="classes.yaml 경로")
    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"[설정 오류] {exc}", file=sys.stderr)
        return 2

    try:
        perception = YoloPerception(
            weights_path=args.weights,
            camera=_SingleImageCamera(Path(args.image)),
            config=cfg,
        )
    except ModelNotAvailable as exc:
        print(f"[실제 추론 불가]\n{exc}", file=sys.stderr)
        return 3

    detection = perception.acquire()
    decision = DecisionPolicy(cfg).decide(detection)

    print(f"판정  : {detection}")
    print(f"조치  : {decision.action.value} / {decision.destination}")
    print(f"근거  : {decision.reason.value}")
    print(f"사람 판단 필요: {'예' if decision.requires_human else '아니오'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
