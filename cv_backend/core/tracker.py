from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

import numpy as np

# HACKATHON: simplify — ByteTrack installed from source (see README).
# All ByteTrack calls are isolated here so the tracker can be swapped easily.
try:
    from yolox.tracker.byte_tracker import BYTETracker, STrack  # type: ignore[import]

    _BYTETRACK_AVAILABLE = True
except ImportError:
    _BYTETRACK_AVAILABLE = False


class _ByteTrackArgs:
    """Minimal args object expected by BYTETracker."""

    track_thresh: float = 0.45
    track_buffer: int = 30
    match_thresh: float = 0.8
    mot20: bool = False


class PersonTracker:
    """
    Wraps ByteTrack for multi-person tracking.
    Maintains a 30-frame centroid history per track_id for motion analysis.
    Falls back to detection pass-through if ByteTrack is not installed.
    """

    HISTORY_LEN: int = 30

    def __init__(self) -> None:
        if _BYTETRACK_AVAILABLE:
            self.tracker = BYTETracker(_ByteTrackArgs(), frame_rate=30)
        else:
            self.tracker = None  # type: ignore[assignment]

        # track_id → deque of (cx, cy) centroids
        self._history: dict[int, deque[tuple[float, float]]] = defaultdict(
            lambda: deque(maxlen=self.HISTORY_LEN)
        )
        self._track_ages: dict[int, int] = defaultdict(int)

    def update(
        self, detections: list[dict[str, Any]], frame_shape: tuple[int, ...]
    ) -> list[dict[str, Any]]:
        """
        Update tracker with new detections.

        Returns a list of tracked persons:
            [{track_id, bbox, age, is_new, centroid_history}]
        """
        if self.tracker is None or not _BYTETRACK_AVAILABLE:
            return self._passthrough(detections)

        h, w = frame_shape[:2]

        # ByteTrack expects [x1, y1, x2, y2, score] as float32 array
        det_array = np.array(
            [[*d["bbox"], d["confidence"]] for d in detections], dtype=np.float32
        ) if detections else np.empty((0, 5), dtype=np.float32)

        online_targets: list[STrack] = self.tracker.update(det_array, [h, w], [h, w])

        tracked: list[dict[str, Any]] = []
        for t in online_targets:
            tid = int(t.track_id)
            x1, y1, w_box, h_box = t.tlwh
            bbox = [x1, y1, x1 + w_box, y1 + h_box]

            cx, cy = x1 + w_box / 2, y1 + h_box / 2
            self._history[tid].append((cx, cy))
            self._track_ages[tid] += 1

            tracked.append(
                {
                    "track_id": tid,
                    "bbox": bbox,
                    "age": self._track_ages[tid],
                    "is_new": self._track_ages[tid] == 1,
                    "centroid_history": list(self._history[tid]),
                }
            )

        return tracked

    def _passthrough(self, detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Assign fake sequential track IDs when ByteTrack is unavailable."""
        result = []
        for i, d in enumerate(detections):
            x1, y1, x2, y2 = d["bbox"]
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            result.append(
                {
                    "track_id": i,
                    "bbox": d["bbox"],
                    "age": 1,
                    "is_new": True,
                    "centroid_history": [(cx, cy)],
                }
            )
        return result
