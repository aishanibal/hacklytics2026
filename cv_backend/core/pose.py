from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import mediapipe as mp
import numpy as np


@dataclass
class PoseResult:
    landmarks: list[dict[str, float]] = field(default_factory=list)
    visibility_scores: list[float] = field(default_factory=list)
    is_pose_detected: bool = False


class PoseAnalyzer:
    """
    MediaPipe Pose wrapper.
    Crops the frame to the person's bounding box before inference for speed.
    """

    def __init__(self) -> None:
        self._pose = mp.solutions.pose.Pose(  # type: ignore[attr-defined]
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def analyze(self, frame: np.ndarray, bbox: list[float]) -> dict[str, Any]:
        """
        Run MediaPipe Pose on the person crop defined by bbox [x1, y1, x2, y2].

        Returns a dict suitable for JSON serialization:
            {"landmarks": [...], "visibility_scores": [...], "is_pose_detected": bool}
        """
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = (
            max(0, int(bbox[0])),
            max(0, int(bbox[1])),
            min(w, int(bbox[2])),
            min(h, int(bbox[3])),
        )

        if x2 <= x1 or y2 <= y1:
            return PoseResult().__dict__

        crop = frame[y1:y2, x1:x2]
        import cv2

        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        results = self._pose.process(crop_rgb)

        if not results.pose_landmarks:
            return PoseResult().__dict__

        landmarks: list[dict[str, float]] = []
        visibility_scores: list[float] = []

        for lm in results.pose_landmarks.landmark:
            # Translate normalized crop coords back to full-frame pixel coords
            px = x1 + lm.x * (x2 - x1)
            py = y1 + lm.y * (y2 - y1)
            landmarks.append({"x": px, "y": py, "z": float(lm.z)})
            visibility_scores.append(float(lm.visibility))

        return PoseResult(
            landmarks=landmarks,
            visibility_scores=visibility_scores,
            is_pose_detected=True,
        ).__dict__
