#!/usr/bin/env python3
"""학습 예제.

프로젝트 당시의 학습 스크립트는 보존되어 있지 않다. 이 파일은 당시의 학습 조건
(3클래스 / 100 epoch / 클라우드 GPU)을 같은 형태로 다시 돌릴 수 있게 적어 둔 것이며,
이 저장소에서 실행해 검증하지 않았다. 데이터셋이 없기 때문이다.

사용법:
    python training/train_example.py --data training/dataset_schema.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_EPOCHS = 100      # 당시 학습 조건(사용자 진술)
DEFAULT_IMGSZ = 640
DEFAULT_MODEL = "yolo11n.pt"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="데이터셋 yaml 경로")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--imgsz", type=int, default=DEFAULT_IMGSZ)
    parser.add_argument("--project", default="runs")
    parser.add_argument("--name", default="triage3")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"[중단] 데이터셋 yaml 이 없습니다: {data_path}", file=sys.stderr)
        return 2

    try:
        from ultralytics import YOLO
    except ImportError:
        print(
            "[중단] ultralytics 가 없습니다.\n"
            "  pip install -r requirements.txt\n"
            "학습에는 GPU 환경을 권장합니다. 엣지 보드에서 학습하지 마십시오.",
            file=sys.stderr,
        )
        return 3

    model = YOLO(args.model)
    model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        project=args.project,
        name=args.name,
    )

    print(
        "\n학습이 끝나면 best.pt 를 엣지 보드로 옮겨 온보드 추론에 사용합니다.\n"
        "추론을 외부 PC에 두면 통신 실패가 그대로 동작 실패가 되기 때문입니다.\n"
        "  python scripts/run_inference_example.py --weights <best.pt> --image <파일>"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
