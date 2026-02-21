"""
Live video stream from URL + YOLO person detection + BLE distance overlay.

- Fetches frames from VIDEO_STREAM_URL.
- Uses test BLE data (replace with BLE API when ready); format:
  requests: [{"UUID": "...", "mac-address": "...", "distance": float}, ...]
- Runs YOLO to get person bounding boxes, assigns BLE distance to each detection
  (by order: first BLE device -> first person, etc.), draws boxes with distance labels.
- Press 'q' to quit.

Run from cv_backend:  python -m frame.gather_frames   or   python frame/gather_frames.py
For a display window you need opencv-python (not only opencv-python-headless).
"""

import sys
import time
from pathlib import Path

import cv2
import numpy as np
import requests

# Allow importing core when run from cv_backend or from frame/
_cv_backend = Path(__file__).resolve().parent.parent
if str(_cv_backend) not in sys.path:
    sys.path.insert(0, str(_cv_backend))

from core.detector import AnomalyDetector

# --- Config ---
VIDEO_STREAM_URL = "http://10.136.28.70:5000/video-stream"
BLE_DATA_URL = "http://10.136.28.70:5000/ble-data"  # use when API is ready

# Test BLE data — matches API format: Requests array with name, UUID, mac-address, distance
TEST_BLE_REQUESTS = [
    {"name": "TARGET_A15", "UUID": "a91c8e72-6b91-4f92-9c9b-6bafcd2e1d13", "mac-address": "AA:BB:CC:DD:EE:01", "distance": 2.5},
    {"name": "Device_02", "UUID": "b82d9f83-7ca2-5g03-0d0c-7cbgde3f2e24", "mac-address": "AA:BB:CC:DD:EE:02", "distance": 3.1},
    {"name": "Device_03", "UUID": "c93e0g94-8db3-6h14-1e1d-8dchef4g3f35", "mac-address": "AA:BB:CC:DD:EE:03", "distance": 1.8},
]


def _normalize_ble_entry(entry: dict) -> dict:
    """Ensure each BLE entry has distance and a display id (name, UUID, or mac-address)."""
    dist = entry.get("distance")
    if dist is not None:
        dist = float(dist)
    return {
        "name": entry.get("name"),
        "UUID": entry.get("UUID"),
        "mac-address": entry.get("mac-address"),
        "distance": dist,
    }


def get_ble_data(use_test_data: bool = True) -> list[dict]:
    """
    Return BLE list from API or test data.
    API format: { "Requests": [ { "name": "...", "UUID": "...", "mac-address": "...", "distance": float }, ... ] }
    Also accepts "requests" (lowercase). Returns list of normalized dicts with name, UUID, mac-address, distance.
    """
    if use_test_data:
        return [ _normalize_ble_entry(e) for e in TEST_BLE_REQUESTS ]

    try:
        r = requests.get(BLE_DATA_URL, timeout=2)
        if r.status_code != 200:
            return [ _normalize_ble_entry(e) for e in TEST_BLE_REQUESTS ]
        data = r.json()
        if isinstance(data, list):
            return [ _normalize_ble_entry(e) for e in data ]
        # API uses "Requests" (capital R)
        raw = data.get("Requests") or data.get("requests") or data.get("Reuqests") or []
        if not isinstance(raw, list):
            return [ _normalize_ble_entry(e) for e in TEST_BLE_REQUESTS ]
        return [ _normalize_ble_entry(e) for e in raw ]
    except Exception as e:
        print(f"BLE fetch failed: {e}, using test data")
    return [ _normalize_ble_entry(e) for e in TEST_BLE_REQUESTS ]


def fetch_frame(url: str) -> np.ndarray | None:
    """Get one frame from the video stream URL. Returns BGR frame or None."""
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            img_arr = np.frombuffer(response.content, dtype=np.uint8)
            frame = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
            return frame
    except Exception as e:
        print(f"Frame fetch error: {e}")
    return None


def assign_ble_to_detections(
    detections: list[dict],
    ble_requests: list[dict],
) -> list[tuple[dict, dict | None]]:
    """
    Pair each detection with a BLE device (by order: 1st detection <-> 1st BLE, etc.).
    Returns list of (detection, ble_entry or None).
    """
    pairs: list[tuple[dict, dict | None]] = []
    for i, det in enumerate(detections):
        ble = ble_requests[i] if i < len(ble_requests) else None
        pairs.append((det, ble))
    return pairs


def assign_ble_by_distance(
    detections: list[dict],
    ble_requests: list[dict],
) -> list[tuple[dict, dict | None]]:
    """
    Match persons to BLE devices by distance: closest person (largest bbox) gets
    closest BLE (smallest distance), so we draw bounding boxes that capture the
    person close to each BLE-reported distance.
    Returns list of (detection, ble_entry or None).
    """
    if not detections or not ble_requests:
        return [(d, None) for d in detections]

    # Sort persons by bbox area descending (larger = closer to camera)
    def bbox_area(d: dict) -> float:
        x1, y1, x2, y2 = d["bbox"]
        return (x2 - x1) * (y2 - y1)

    sorted_detections = sorted(detections, key=bbox_area, reverse=True)
    # Sort BLE by distance ascending (smallest = closest)
    sorted_ble = sorted(ble_requests, key=lambda b: float(b.get("distance", 999)))

    pairs: list[tuple[dict, dict | None]] = []
    for i, det in enumerate(sorted_detections):
        ble = sorted_ble[i] if i < len(sorted_ble) else None
        pairs.append((det, ble))
    return pairs


def draw_boxes_with_ble(
    frame: np.ndarray,
    pairs: list[tuple[dict, dict | None]],
) -> np.ndarray:
    """Draw YOLO bounding boxes and BLE distance labels on frame."""
    out = frame.copy()
    for det, ble in pairs:
        x1, y1, x2, y2 = (int(x) for x in det["bbox"])
        color = (0, 255, 0)  # green
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = "person"
        if ble is not None:
            dist = ble.get("distance")
            name = ble.get("name") or ""
            short_id = (ble.get("UUID") or ble.get("mac-address") or "")[:8]
            if dist is not None:
                label = f"{dist:.1f}m"
            if name:
                label = f"{name} {label}".strip()
            elif short_id:
                label = f"{label} ({short_id})"
        # Label above box
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        cv2.rectangle(out, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
        cv2.putText(out, label, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
    return out


def main() -> None:
    use_test_ble = True  # set False when BLE API is ready
    detector = AnomalyDetector()
    print("YOLO loaded. Fetching stream from", VIDEO_STREAM_URL)
    print("BLE: using test data" if use_test_ble else f"BLE: fetching from {BLE_DATA_URL}")
    print("Press 'q' to quit.")

    while True:
        ble_requests = get_ble_data(use_test_data=use_test_ble)
        frame = fetch_frame(VIDEO_STREAM_URL)
        if frame is None:
            print("No frame; retrying in 1s...")
            time.sleep(1)
            continue

        detections = detector.detect(frame)
        pairs = assign_ble_by_distance(detections, ble_requests)
        out = draw_boxes_with_ble(frame, pairs)

        cv2.imshow("Live feed (YOLO + BLE distance)", out)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        time.sleep(0.05)

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
