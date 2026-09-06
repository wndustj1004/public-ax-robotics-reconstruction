"""추론 어댑터.

두 가지 모드가 있고, 서로 섞이지 않는다.

* real       — 학습된 가중치 파일을 ultralytics 로 불러 실제로 추론한다.
* simulation — 모델을 부르지 않는다. simulation.py 의 대체 구현을 쓴다.

모델 파일이 없는데 real 모드를 요구하면 조용히 넘어가지 않고 멈춘다.
'모델이 있는 척'을 만들지 않기 위한 것이다. 이 저장소에는 가중치가 없다.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .decision_policy import Detection, majority_vote


class ModelNotAvailable(FileNotFoundError):
    """실제 추론을 요청했으나 가중치나 런타임이 없을 때."""


class YoloPerception:
    """ultralytics 모델을 감싼 인식기.

    프레임을 여러 장 모아 다수결로 확정한다. 한 프레임의 흔들림이
    그대로 경로 결정이 되는 것을 막기 위해서다.

    ※ 이 클래스는 이번 재구성에서 새로 작성한 것이며, 실물 카메라·모델로
       실행해 검증하지 않았다. 실행 검증 범위는 README 의 '확인한 것' 참조.
    """

    def __init__(
        self,
        weights_path: str | Path,
        camera: Any,
        config: dict[str, Any],
    ):
        self._weights = Path(weights_path)
        self._camera = camera

        det = config.get("detection", {})
        self._min_confidence = float(det.get("min_confidence", 0.70))
        self._vote_window = int(det.get("vote_window", 5))
        self._vote_required = int(det.get("vote_required", 3))

        self._model = self._load_model()

    def _load_model(self) -> Any:
        if not self._weights.exists():
            raise ModelNotAvailable(
                f"모델 가중치를 찾을 수 없습니다: {self._weights}\n"
                "이 저장소에는 학습된 가중치가 들어 있지 않습니다.\n"
                "  · 직접 학습하려면  training/README.md 를 보십시오.\n"
                "  · 하드웨어 없이 로직만 확인하려면\n"
                "        python scripts/run_simulation.py\n"
                "    로 simulation 모드를 사용하십시오."
            )
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise ModelNotAvailable(
                "ultralytics 가 설치되어 있지 않습니다.\n"
                "  pip install -r requirements.txt\n"
                "설치 없이 로직만 보려면 simulation 모드를 사용하십시오."
            ) from exc
        return YOLO(str(self._weights))

    # ------------------------------------------------------------------
    def _detect_once(self) -> Detection | None:
        frame = self._camera.get_frame()
        if frame is None:
            return None

        results = self._model(frame, conf=self._min_confidence, verbose=False)
        best: Detection | None = None
        for result in results:
            for box in result.boxes:
                name = result.names[int(box.cls[0])]
                conf = float(box.conf[0])
                if best is None or conf > best.confidence:
                    best = Detection(class_name=name, confidence=conf)
        return best

    def acquire(self) -> Detection | None:
        """vote_window 장을 모아 다수결로 확정한다."""
        window: list[Detection] = []
        for _ in range(self._vote_window):
            det = self._detect_once()
            if det is not None:
                window.append(det)
        return majority_vote(window, self._vote_required, self._min_confidence)

    def wait_for_class(
        self, class_name: str, timeout_sec: float
    ) -> Detection | None:
        """지정한 클래스가 나타날 때까지 기다린다.

        시간이 지나면 None 을 돌려준다. 호출부는 이것을 실패로 다뤄야 한다.
        """
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            det = self._detect_once()
            if det is not None and det.class_name == class_name:
                if det.confidence >= self._min_confidence:
                    return det
            time.sleep(0.05)
        return None
