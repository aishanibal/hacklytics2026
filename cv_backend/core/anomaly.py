from __future__ import annotations

import base64
import time
from typing import Any

import cv2
import numpy as np

# Anomaly type constants
FALL = "FALL"
COLLAPSE = "COLLAPSE"
ERRATIC_MOTION = "ERRATIC_MOTION"
STATIONARY_DOWN = "STATIONARY_DOWN"

# Tunable thresholds — TODO: fine-tune with real data
FALL_ASPECT_RATIO_THRESHOLD: float = 1.4   # width/height ratio that signals a fall
ERRATIC_MOTION_VARIANCE_THRESHOLD: float = 800.0
STATIONARY_DOWN_SECONDS: float = 10.0
COLLAPSE_MIN_TRACK_AGE_FRAMES: int = 150   # ~5s at 30fps


class AnomalyClassifier:
    """
    Rule-based anomaly classifier operating on per-track history and pose data.
    Detects: FALL, COLLAPSE, ERRATIC_MOTION, STATIONARY_DOWN.
    """

    def __init__(self) -> None:
        # track_id → timestamp of last confirmed upright/motion
        self._last_active: dict[int, float] = {}
        self._last_seen: dict[int, float] = {}
        self._known_tracks: set[int] = set()

    def classify(
        self, track: dict[str, Any], pose_result: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Evaluate a single tracked person for anomalies.
        Returns an AnomalyEvent dict or None if no anomaly is detected.
        """
        tid: int = track["track_id"]
        bbox: list[float] = track["bbox"]
        history: list[tuple[float, float]] = track.get("centroid_history", [])
        age: int = track.get("age", 0)
        now = time.time()

        self._last_seen[tid] = now
        self._known_tracks.add(tid)

        x1, y1, x2, y2 = bbox
        box_w = x2 - x1
        box_h = y2 - y1

        # --- FALL detection ---
        if box_h > 0:
            aspect = box_w / box_h
            if aspect > FALL_ASPECT_RATIO_THRESHOLD:
                return self._make_event(FALL, tid, confidence=min(aspect / 3.0, 1.0))

        # --- ERRATIC_MOTION detection ---
        if len(history) >= 10:
            recent = history[-10:]
            cx_vals = [p[0] for p in recent]
            cy_vals = [p[1] for p in recent]
            variance = float(np.var(cx_vals) + np.var(cy_vals))
            if variance > ERRATIC_MOTION_VARIANCE_THRESHOLD:
                return self._make_event(
                    ERRATIC_MOTION, tid, confidence=min(variance / (ERRATIC_MOTION_VARIANCE_THRESHOLD * 3), 1.0)
                )

        # --- STATIONARY_DOWN detection ---
        if pose_result.get("is_pose_detected"):
            landmarks = pose_result.get("landmarks", [])
            if self._is_person_down(landmarks, box_h):
                if tid not in self._last_active:
                    self._last_active[tid] = now
                elif (now - self._last_active[tid]) >= STATIONARY_DOWN_SECONDS:
                    return self._make_event(STATIONARY_DOWN, tid, confidence=0.75)
            else:
                self._last_active.pop(tid, None)

        return None

    def check_collapses(self, active_track_ids: set[int]) -> list[dict[str, Any]]:
        """
        Call once per frame with the current set of active track IDs.
        Returns COLLAPSE events for tracks that were long-lived but just disappeared.
        # HACKATHON: simplify — called manually from stream.py for now
        """
        events: list[dict[str, Any]] = []
        now = time.time()

        for tid in list(self._known_tracks):
            if tid not in active_track_ids:
                last = self._last_seen.get(tid, now)
                if (now - last) > 1.0:  # disappeared for >1s
                    # Only flag as collapse if we tracked them for a meaningful time
                    # HACKATHON: simplify — use frame age proxy via last_seen gap
                    events.append(self._make_event(COLLAPSE, tid, confidence=0.65))
                    self._known_tracks.discard(tid)

        return events

    @staticmethod
    def _is_person_down(landmarks: list[dict[str, float]], box_h: float) -> bool:
        """
        Heuristic: if key lower-body landmarks (hips, knees) are close in Y to
        upper-body landmarks, the person is likely lying down.
        # TODO: fine-tune with more nuanced landmark analysis
        """
        if len(landmarks) < 28:
            return False
        # MediaPipe landmark indices: 11=left shoulder, 12=right shoulder,
        # 23=left hip, 24=right hip, 25=left knee, 26=right knee
        shoulder_y = (landmarks[11]["y"] + landmarks[12]["y"]) / 2
        hip_y = (landmarks[23]["y"] + landmarks[24]["y"]) / 2

        vertical_span = abs(hip_y - shoulder_y)
        return box_h > 0 and (vertical_span / box_h) < 0.25

    @staticmethod
    def _make_event(
        anomaly_type: str, track_id: int, confidence: float
    ) -> dict[str, Any]:
        return {
            "type": anomaly_type,
            "track_id": track_id,
            "confidence": round(confidence, 3),
            "timestamp": int(time.time() * 1000),
            "duration_seconds": None,
            "frame_snapshot_b64": None,  # TODO: attach thumbnail when anomaly fires
        }
