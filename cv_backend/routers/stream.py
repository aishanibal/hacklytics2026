"""
Stream router: Raspberry Pi camera feed + YOLO + BLE distance bounding boxes.

- Fetches frames from the Raspberry Pi API URL (see frame.gather_frames).
- Uses test BLE data; matches each BLE device (by distance) to the person
  whose bbox best matches that distance (closest person ↔ closest BLE).
- Serves MJPEG at GET /stream/live and a browser page at GET /stream/view.

Also provides WebSocket and POST /analyze/frame for Flutter (separate pipeline).
"""

import asyncio
import base64
import json
import os
import time
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse

from core.detector import AnomalyDetector
from core.pose import PoseAnalyzer
from core.tracker import PersonTracker
from frame.gather_frames import (
    VIDEO_STREAM_URL as GATHER_VIDEO_URL,
    assign_ble_by_distance,
    draw_boxes_with_ble,
    fetch_frame,
    get_ble_data,
)

router = APIRouter()

INFERENCE_STRIDE: int = int(os.getenv("INFERENCE_STRIDE", "2"))

# YOLO detector for person bounding boxes (Pi camera + BLE feed)
detector = AnomalyDetector()
# Flutter pipeline (optional)
tracker = PersonTracker()
pose_analyzer = PoseAnalyzer()

# Raspberry Pi camera URL — same as in gather_frames.py; override with env if needed
VIDEO_STREAM_URL: str = os.getenv("VIDEO_STREAM_URL", GATHER_VIDEO_URL)
USE_TEST_BLE: bool = os.getenv("USE_TEST_BLE", "true").lower() in ("1", "true", "yes")


# --- Live feed from Raspberry Pi: YOLO + BLE distance boxes ---


async def _mjpeg_stream_generator():
    """
    Fetch frames from Pi URL, run YOLO, match persons to BLE by distance,
    draw bounding boxes, stream as MJPEG.
    """
    boundary = "frame"
    while True:
        frame = await asyncio.to_thread(fetch_frame, VIDEO_STREAM_URL)
        if frame is None:
            await asyncio.sleep(0.5)
            continue
        ble_requests = get_ble_data(use_test_data=USE_TEST_BLE)
        detections = await asyncio.to_thread(detector.detect, frame)
        # Match: person closest to camera (largest bbox) ↔ BLE with smallest distance
        pairs = assign_ble_by_distance(detections, ble_requests)
        out = draw_boxes_with_ble(frame, pairs)
        _, jpeg = cv2.imencode(".jpg", out)
        chunk = (
            f"--{boundary}\r\n"
            "Content-Type: image/jpeg\r\n"
            f"Content-Length: {len(jpeg.tobytes())}\r\n\r\n"
        ).encode() + jpeg.tobytes() + b"\r\n"
        yield chunk
        await asyncio.sleep(0.033)


@router.get("/stream/live", response_class=StreamingResponse)
async def stream_live_feed():
    """
    MJPEG stream: Raspberry Pi camera + YOLO bounding boxes with BLE distance.
    Each box captures the person closest to that BLE-reported distance.
    """
    return StreamingResponse(
        _mjpeg_stream_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/stream/view", response_class=HTMLResponse)
async def stream_view_page():
    """Browser page that shows the Pi camera feed with YOLO + BLE boxes."""
    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Pi camera – YOLO + BLE distance</title>
  <style>
    body {{ margin: 0; background: #111; display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
    img {{ max-width: 100%; max-height: 100vh; object-fit: contain; }}
    .info {{ position: fixed; top: 8px; left: 8px; color: #0f0; font-family: monospace; font-size: 12px; z-index: 1; }}
  </style>
</head>
<body>
  <div class="info">Raspberry Pi camera – YOLO + BLE (distance-matched boxes) · {VIDEO_STREAM_URL}</div>
  <img src="/stream/live" alt="Live stream" />
</body>
</html>
"""
    return HTMLResponse(html)


# --- Flutter WebSocket / single-frame analysis (unchanged) ---


@router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket) -> None:
    """
    Receives base64 JPEG frames from Flutter, runs CV pipeline (detect, track, pose).
    """
    await websocket.accept()
    frame_id: int = 0

    try:
        while True:
            raw = await websocket.receive_text()
            payload: dict[str, Any] = json.loads(raw)
            frame_id += 1

            if frame_id % INFERENCE_STRIDE != 0:
                await websocket.send_json({"frame_id": frame_id, "skipped": True})
                continue

            img_bytes = base64.b64decode(payload["frame"])
            np_arr = np.frombuffer(img_bytes, dtype=np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None:
                await websocket.send_json({"frame_id": frame_id, "error": "invalid frame"})
                continue

            sensor_data: dict = payload.get("sensor_data", {})
            result = await asyncio.to_thread(_run_pipeline, frame, sensor_data, frame_id)
            await websocket.send_json(result)

    except WebSocketDisconnect:
        pass


@router.post("/analyze/frame")
async def analyze_single_frame(payload: dict[str, Any]) -> dict[str, Any]:
    """Single-frame analysis (Flutter / testing)."""
    img_bytes = base64.b64decode(payload["frame"])
    np_arr = np.frombuffer(img_bytes, dtype=np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if frame is None:
        return {"error": "invalid frame"}
    sensor_data = payload.get("sensor_data", {})
    return await asyncio.to_thread(_run_pipeline, frame, sensor_data, 0)


def _run_pipeline(frame: np.ndarray, sensor_data: dict, frame_id: int) -> dict[str, Any]:
    """Blocking CV pipeline for Flutter frames: detect, track, pose."""
    detections = detector.detect(frame)
    tracks = tracker.update(detections, frame.shape)
    pose_results: dict = {}

    for track in tracks:
        pose_result = pose_analyzer.analyze(frame, track["bbox"])
        pose_results[track["track_id"]] = pose_result

    return {
        "frame_id": frame_id,
        "tracks": tracks,
        "pose_data": pose_results,
        "timestamp": int(time.time() * 1000),
    }
