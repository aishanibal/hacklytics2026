from __future__ import annotations

from typing import Any

import numpy as np


class AnomalyDetector:
    """
    YOLOv8 wrapper that detects persons in a frame.
    Model weights are auto-downloaded on first run and cached locally.
    """

    PERSON_CLASS_ID: int = 0
    CONFIDENCE_THRESHOLD: float = 0.45
    # TODO: fine-tune — swap yolov8n for yolov8s if accuracy is too low
    DEFAULT_MODEL: str = "yolov8n.pt"

    def __init__(self, model_path: str = DEFAULT_MODEL) -> None:
        from ultralytics import YOLO  # lazy import so startup doesn't fail if GPU missing

        self.model = YOLO(model_path)

    def detect(self, frame: np.ndarray) -> list[dict[str, Any]]:
        """
        Run YOLOv8 inference on a single frame.

        Returns a list of detections filtered to persons only:
            [{"bbox": [x1, y1, x2, y2], "confidence": float, "class_id": int, "class_name": str}]
        """
        results = self.model(frame, verbose=False)[0]
        detections: list[dict[str, Any]] = []

        for box in results.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])

            if class_id != self.PERSON_CLASS_ID:
                continue
            if confidence < self.CONFIDENCE_THRESHOLD:
                continue

            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append(
                {
                    "bbox": [x1, y1, x2, y2],
                    "confidence": confidence,
                    "class_id": class_id,
                    "class_name": "person",
                }
            )

        return detections
