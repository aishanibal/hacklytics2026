import asyncio
import base64
import json
import os
import time
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.anomaly import AnomalyClassifier
from core.detector import AnomalyDetector
from core.pose import PoseAnalyzer
from core.tracker import PersonTracker

router = APIRouter()

# Process every Nth frame to keep latency under 200ms
INFERENCE_STRIDE: int = int(os.getenv("INFERENCE_STRIDE", "2"))

detector = AnomalyDetector()
tracker = PersonTracker()
pose_analyzer = PoseAnalyzer()
anomaly_classifier = AnomalyClassifier()

# Internal queue for confirmed anomaly events (consumed by /report/generate)
anomaly_event_queue: asyncio.Queue = asyncio.Queue()


@router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket) -> None:
    """
    Receives base64-encoded JPEG frames from Flutter, runs the full CV pipeline,
    and returns detection/anomaly results.

    Flutter sends:  { "frame": "<base64 jpeg>", "sensor_data": {...} }
    Server returns: { "tracks": [...], "anomalies": [...], "pose_data": {...}, "frame_id": int }
    """
    await websocket.accept()
    frame_id: int = 0

    try:
        while True:
            raw = await websocket.receive_text()
            payload: dict[str, Any] = json.loads(raw)

            frame_id += 1

            # Drop frames according to INFERENCE_STRIDE to manage latency
            if frame_id % INFERENCE_STRIDE != 0:
                await websocket.send_json({"frame_id": frame_id, "skipped": True})
                continue

            # Decode base64 JPEG → numpy array
            img_bytes = base64.b64decode(payload["frame"])
            np_arr = np.frombuffer(img_bytes, dtype=np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None:
                await websocket.send_json({"frame_id": frame_id, "error": "invalid frame"})
                continue

            sensor_data: dict = payload.get("sensor_data", {})

            # Run pipeline in a thread so we don't block the event loop
            result = await asyncio.to_thread(
                _run_pipeline, frame, sensor_data, frame_id
            )

            # If anomalies were found, push to internal queue for report generation
            for anomaly in result.get("anomalies", []):
                await anomaly_event_queue.put({"anomaly": anomaly, "sensor_data": sensor_data})

            await websocket.send_json(result)

    except WebSocketDisconnect:
        pass


@router.post("/analyze/frame")
async def analyze_single_frame(payload: dict[str, Any]) -> dict[str, Any]:
    """Single-frame analysis endpoint — useful for testing without a live stream."""
    img_bytes = base64.b64decode(payload["frame"])
    np_arr = np.frombuffer(img_bytes, dtype=np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if frame is None:
        return {"error": "invalid frame"}

    sensor_data = payload.get("sensor_data", {})
    return await asyncio.to_thread(_run_pipeline, frame, sensor_data, 0)


def _run_pipeline(frame: np.ndarray, sensor_data: dict, frame_id: int) -> dict[str, Any]:
    """Blocking CV pipeline — called via asyncio.to_thread."""
    detections = detector.detect(frame)
    tracks = tracker.update(detections, frame.shape)

    pose_results: dict = {}
    anomalies: list = []

    for track in tracks:
        pose_result = pose_analyzer.analyze(frame, track["bbox"])
        pose_results[track["track_id"]] = pose_result

        anomaly = anomaly_classifier.classify(track, pose_result)
        if anomaly:
            anomalies.append(anomaly)

    return {
        "frame_id": frame_id,
        "tracks": tracks,
        "anomalies": anomalies,
        "pose_data": pose_results,
        "timestamp": int(time.time() * 1000),
    }
