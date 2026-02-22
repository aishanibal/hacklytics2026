"""
Pose + LSTM anomaly detection — web dashboard.

Uses BLE distance matching to lock onto a single target person
and only run pose/LSTM on them.

Endpoints:
  GET  /pose/view   — HTML dashboard
  GET  /pose/live   — MJPEG video stream (skeleton overlay)
  WS   /pose/ws     — live JSON telemetry
"""

import asyncio
import json
import math
import os
import threading
import time
from typing import Any

import cv2
import numpy as np
import requests as http_requests
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse

from core.keypoint_extractor import KeypointExtractor
from core.feature_engineering import FeatureEngineer
from core.sequence_buffer import SequenceBuffer
from core.lstm_inference import AnomalyPredictor
from core.anomaly_classifier import classify_anomaly

router = APIRouter()

VIDEO_SOURCE: str = os.getenv("VIDEO_SOURCE", "0")
MODEL_PATH: str = os.getenv("MODEL_PATH", "models/pots_model_complete.pt")
FRAME_STEP: int = int(os.getenv("FRAME_STEP", "0"))  # 0 = use model config

# ── BLE config ──
BLE_DATA_URL: str = os.getenv("BLE_DATA_URL", "http://10.136.28.70:5000/ble-data")
USE_TEST_BLE: bool = os.getenv("USE_TEST_BLE", "true").lower() in ("1", "true", "yes")
# The Pi's ble_config.py already filters to only the target UUID,
# so the response list only ever contains the target device.
TARGET_BLE_UUID: str = os.getenv("TARGET_BLE_UUID", "a91c8e72-6b91-4f92-9c9b-6bafcd2e1d13")

TEST_BLE_REQUESTS = [
    {"UUID": "a91c8e72-6b91-4f92-9c9b-6bafcd2e1d13", "address": "AA:BB:CC:DD:EE:01", "distance": 2.5},
]

# ── Health Connect config ──
ANOMALY_HEALTH_DELAY: float = float(os.getenv("ANOMALY_HEALTH_DELAY", "3.0"))

# Latest health data pushed from the Flutter app via POST /pose/health-push
_latest_health: dict | None = None

# Latest anomaly signal (written by bg loop, read by GET /pose/anomaly)
_latest_anomaly: dict[str, Any] = {
    "is_anomaly": False,
    "anomaly_type": "",
    "timestamp": None,
}


def _get_ble_data() -> list[dict]:
    """Fetch BLE device list from the Pi API."""
    if USE_TEST_BLE:
        return TEST_BLE_REQUESTS
    try:
        r = http_requests.get(BLE_DATA_URL, timeout=8)
        if r.status_code != 200:
            print(f"[ble] API returned {r.status_code}")
            return []
        data = r.json()
        if isinstance(data, list):
            return data
        raw = (data.get("devices") or data.get("Requests")
               or data.get("requests") or [])
        print(f"[ble] Got {len(raw)} device(s): {raw}")
        return raw if isinstance(raw, list) else []
    except Exception as exc:
        print(f"[ble] Fetch failed: {exc}")
        return []



# FOCAL_HEIGHT = focal_length_px * avg_person_height
# Computed automatically from frame dimensions + camera vertical FoV.
# Override with FOCAL_HEIGHT env var if you know yours exactly.
CAMERA_VFOV: float = float(os.getenv("CAMERA_VFOV", "124"))   # degrees (110° HFOV → ~124° VFOV at 640x880)
AVG_PERSON_HEIGHT: float = 1.55                                # meters
_focal_height: float = float(os.getenv("FOCAL_HEIGHT", "0"))
_focal_initialized: bool = _focal_height > 0


def _init_focal_from_frame(frame_h: int):
    """Estimate FOCAL_HEIGHT from the frame height and camera vertical FoV."""
    global _focal_height, _focal_initialized
    if _focal_initialized:
        return
    vfov_rad = math.radians(CAMERA_VFOV)
    focal_px = frame_h / (2 * math.tan(vfov_rad / 2))
    _focal_height = focal_px * AVG_PERSON_HEIGHT
    _focal_initialized = True
    print(f"[pose] Initial FOCAL_HEIGHT = {_focal_height:.0f} "
          f"(frame_h={frame_h}, VFoV={CAMERA_VFOV}°)")


def _refine_focal(ble_dist: float, bbox_h: float):
    """Refine FOCAL_HEIGHT after a successful BLE match."""
    global _focal_height
    new_focal = ble_dist * bbox_h
    _focal_height = new_focal
    print(f"[pose] Refined FOCAL_HEIGHT = {_focal_height:.0f} "
          f"(BLE {ble_dist:.2f}m × {bbox_h:.0f}px)")


def _match_target(detections: list[dict],
                  ble_devices: list[dict]) -> tuple[dict | None, float | None]:
    """
    The Pi's BLE scan already filters to only the target UUID,
    so ble_devices contains at most one entry — the target.
    Pick the person whose bbox-estimated distance best matches that BLE distance.
    After matching, refine FOCAL_HEIGHT from the result.
    """
    if not detections or not ble_devices:
        return None, None

    ble_dist = float(ble_devices[0].get("distance", 999))
    print(f"[ble] Target distance = {ble_dist:.2f}m  |  "
          f"FOCAL = {_focal_height:.0f}  |  persons = {len(detections)}")

    best: dict | None = None
    best_diff = float("inf")
    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        bbox_h = max(y2 - y1, 1)
        estimated_dist = _focal_height / bbox_h
        diff = abs(estimated_dist - ble_dist)
        print(f"  bbox_h={bbox_h:.0f}  est={estimated_dist:.2f}m  diff={diff:.2f}")
        if diff < best_diff:
            best_diff = diff
            best = det

    if best is not None:
        bx1, by1, bx2, by2 = best["bbox"]
        _refine_focal(ble_dist, max(by2 - by1, 1))

    return best, ble_dist

# ── IoU helper ──

def _iou(box_a: list, box_b: list) -> float:
    """Intersection-over-union between two [x1, y1, x2, y2] boxes."""
    xa = max(box_a[0], box_b[0])
    ya = max(box_a[1], box_b[1])
    xb = min(box_a[2], box_b[2])
    yb = min(box_a[3], box_b[3])
    inter = max(0, xb - xa) * max(0, yb - ya)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


IOU_THRESHOLD = 0.3
LOST_FRAMES_BEFORE_RELOCK = 15

# ── shared state (written by bg thread, read by endpoints) ──

_lock = threading.Lock()
_state: dict[str, Any] = {
    "jpeg": b"",
    "telemetry": {},
}
_active = threading.Event()        # tracking on/off
_request_relock = threading.Event() # signal bg loop to re-fetch BLE


def _bg_loop():
    """Background thread: BLE lock-on once → IoU tracking thereafter."""
    source: Any = int(VIDEO_SOURCE) if VIDEO_SOURCE.isdigit() else VIDEO_SOURCE

    predictor = AnomalyPredictor(model_path=MODEL_PATH)
    cfg = predictor.pipeline_config
    frame_step = FRAME_STEP or cfg.get("frame_step", 10)
    window_size = cfg["window_size"]

    extractor = KeypointExtractor()
    engineer = FeatureEngineer()
    buffer = SequenceBuffer(window_size=window_size, num_features=75)

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[pose] ERROR: Cannot open video source: {source}")
        return
    print(f"[pose] Opened video source: {source}")

    frame_count = 0
    label = "Inactive — press Activate"
    score = 0.0
    threshold = predictor.threshold
    is_anomaly = False
    anomaly_type = ""
    fps = 0.0
    prev_t = time.time()
    last_eng: dict = {}
    last_joints: dict = {}
    ble_dist: float | None = None

    # tracking state
    target_bbox: list | None = None  # None = lock-on mode
    lost_count = 0
    tracking_mode = "INACTIVE"

    # health data pull state
    anomaly_start_t: float | None = None
    health_fetched_this_episode = False
    health_snapshot: dict | None = None

    eng_names = ["nose_y", "hip_y", "torso_len", "full_height",
                 "shoulder_angle", "knee_angle", "vertical_ratio"]
    joint_map = [
        (0, "Nose"), (5, "L Shoulder"), (6, "R Shoulder"),
        (9, "L Wrist"), (10, "R Wrist"),
        (11, "L Hip"), (12, "R Hip"),
        (15, "L Ankle"), (16, "R Ankle"),
    ]

    while True:
        ret, frame = cap.read()
        if not ret:
            print(f"[pose] No frame from {source}, retrying...")
            time.sleep(0.5)
            cap.release()
            cap = cv2.VideoCapture(source)
            continue

        frame_count += 1
        fh, fw = frame.shape[:2]

        if frame_count == 1:
            _init_focal_from_frame(fh)

        detections = extractor.extract_all(frame)
        annotated = frame.copy()
        target: dict | None = None

        is_active = _active.is_set()

        # handle relock request (activate was pressed)
        if _request_relock.is_set():
            _request_relock.clear()
            target_bbox = None
            engineer.reset()
            buffer.reset()
            score = 0.0
            is_anomaly = False
            anomaly_type = ""
            label = "Waiting for buffer..."

        if not is_active:
            # ── INACTIVE: just show video, no tracking ──
            tracking_mode = "INACTIVE"
            target_bbox = None
            label = "Inactive — press Activate"
        elif target_bbox is None:
            # ── LOCK-ON: fetch BLE, match target by distance ──
            tracking_mode = "LOCK-ON"
            ble_devices = _get_ble_data()
            matched, matched_dist = _match_target(detections, ble_devices)
            if matched is not None:
                target = matched
                target_bbox = matched["bbox"]
                ble_dist = matched_dist
                lost_count = 0
                tracking_mode = "TRACKING"
                x1, y1, x2, y2 = matched["bbox"]
                bbox_h = max(y2 - y1, 1)
                est = _focal_height / bbox_h
                print(f"[pose] Locked onto target "
                      f"(BLE: {ble_dist:.1f}m, est: {est:.1f}m, bbox_h: {bbox_h:.0f}px, "
                      f"FOCAL: {_focal_height:.0f})")
        else:
            # ── TRACKING: find best IoU match to previous bbox ──
            tracking_mode = "TRACKING"
            best_iou = 0.0
            best_det = None
            for det in detections:
                overlap = _iou(target_bbox, det["bbox"])
                if overlap > best_iou:
                    best_iou = overlap
                    best_det = det

            if best_det is not None and best_iou >= IOU_THRESHOLD:
                target = best_det
                target_bbox = best_det["bbox"]
                lost_count = 0
            else:
                lost_count += 1
                if lost_count > LOST_FRAMES_BEFORE_RELOCK:
                    print(f"[pose] Lost target for {lost_count} frames, re-locking...")
                    target_bbox = None
                    engineer.reset()
                    buffer.reset()

        # draw non-target persons dimmed
        for det in detections:
            if det is not target:
                KeypointExtractor.draw_skeleton(
                    annotated, det["keypoints"],
                    color=(80, 80, 80), thickness=1,
                    bbox=det["bbox"],
                )

        # draw + process target person
        kps_raw = None
        if target is not None:
            kps_raw = target["keypoints"]

            dist_label = "BLE Target"
            if ble_dist is not None:
                dist_label += f" {ble_dist:.1f}m"

            KeypointExtractor.draw_skeleton(
                annotated, kps_raw,
                color=(0, 255, 0), thickness=2,
                label=dist_label,
                bbox=target["bbox"],
            )

        if kps_raw is not None:
            last_joints = {}
            for idx, name in joint_map:
                px, py, conf = kps_raw[idx]
                last_joints[name] = [round(float(px)), round(float(py)), round(float(conf), 2)]

            if frame_count % frame_step == 0:
                features = engineer.compute(kps_raw, frame_w=fw, frame_h=fh)
                eng_vals = features[68:]
                last_eng = {}
                for n, v in zip(eng_names, eng_vals):
                    if "angle" in n:
                        last_eng[n] = round(math.degrees(float(v)), 1)
                    else:
                        last_eng[n] = round(float(v), 4)

                ready = buffer.add(features)
                if ready:
                    window = buffer.get_window()
                    result = predictor.predict(window)
                    score = result["score"]
                    is_anomaly = result["is_anomaly"]
                    threshold = result["threshold"]
                    if is_anomaly:
                        label = "ANOMALY DETECTED"
                        anomaly_type, _ = classify_anomaly(window)
                        if anomaly_start_t is None:
                            anomaly_start_t = time.time()
                        elif (not health_fetched_this_episode
                              and time.time() - anomaly_start_t >= ANOMALY_HEALTH_DELAY):
                            print(f"[health] Anomaly sustained {ANOMALY_HEALTH_DELAY}s — snapshotting health data")
                            health_snapshot = _latest_health.copy() if _latest_health else None
                            health_fetched_this_episode = True
                    else:
                        label = "Normal"
                        anomaly_type = ""
                        anomaly_start_t = None
                        health_fetched_this_episode = False
        else:
            label = "No person detected" if not detections else "Target lost — re-locking..."
            last_joints = {}
            last_eng = {}

        now = time.time()
        dt = max(now - prev_t, 1e-6)
        fps = 0.9 * fps + 0.1 / dt
        prev_t = now

        _, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])

        telemetry = {
            "fps": round(fps, 1),
            "status": label,
            "score": round(score, 6),
            "threshold": round(threshold, 6),
            "is_anomaly": is_anomaly,
            "anomaly_type": anomaly_type,
            "buffer_fill": len(buffer._buffer),
            "buffer_size": buffer.window_size,
            "engineered": last_eng,
            "joints": last_joints,
            "target_ble": TARGET_BLE_UUID,
            "ble_distance": round(ble_dist, 2) if ble_dist is not None else None,
            "persons_detected": len(detections),
            "tracking_mode": tracking_mode,
            "lost_count": lost_count,
            "focal_height": round(_focal_height, 0),
            "focal_initialized": _focal_initialized,
            "health": health_snapshot,
        }

        with _lock:
            _state["jpeg"] = jpeg.tobytes()
            _state["telemetry"] = telemetry
            _latest_anomaly["is_anomaly"] = is_anomaly
            _latest_anomaly["anomaly_type"] = anomaly_type
            _latest_anomaly["timestamp"] = round(time.time(), 3) if is_anomaly else _latest_anomaly.get("timestamp")


_thread_started = False


def _ensure_bg():
    global _thread_started
    if not _thread_started:
        _thread_started = True
        t = threading.Thread(target=_bg_loop, daemon=True)
        t.start()


# ── Activate / Deactivate ──

@router.post("/pose/activate")
async def pose_activate():
    _ensure_bg()
    _active.set()
    _request_relock.set()
    return {"status": "activated", "info": "BLE lock-on triggered"}


@router.post("/pose/deactivate")
async def pose_deactivate():
    _active.clear()
    return {"status": "deactivated", "info": "Tracking stopped"}


@router.get("/pose/status")
async def pose_status():
    return {"active": _active.is_set()}


# ── Anomaly signal (for polling / webhooks) ──

@router.get("/pose/anomaly")
async def get_anomaly_signal():
    """
    Return the latest anomaly signal from the pose/LSTM pipeline.
    Poll this to know when an anomaly is currently detected.
    """
    with _lock:
        out = dict(_latest_anomaly)
    return out


# ── Health data push (from Flutter app) ──

@router.post("/pose/health-push")
async def health_push(request: Request):
    """Accept health data pushed from the Flutter companion app."""
    global _latest_health
    body = await request.json()
    _latest_health = body
    return {"status": "ok"}


# ── MJPEG ──

async def _mjpeg_gen():
    _ensure_bg()
    while True:
        with _lock:
            jpeg = _state["jpeg"]
        if jpeg:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
                + jpeg + b"\r\n"
            )
        await asyncio.sleep(0.033)


@router.get("/pose/live")
async def pose_mjpeg():
    _ensure_bg()
    return StreamingResponse(
        _mjpeg_gen(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ── WebSocket telemetry ──

@router.websocket("/pose/ws")
async def pose_ws(ws: WebSocket):
    _ensure_bg()
    await ws.accept()
    try:
        while True:
            with _lock:
                t = _state["telemetry"]
            # Always send so clients get at least is_anomaly/anomaly_type (e.g. Flutter app)
            payload = t if t else {"is_anomaly": False, "anomaly_type": ""}
            await ws.send_text(json.dumps(payload))
            await asyncio.sleep(0.15)
    except WebSocketDisconnect:
        pass


# ── Dashboard HTML ──

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>POTS Anomaly Detection — Live Dashboard</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;background:#2a3234;color:#B8D8D8;overflow-x:hidden}
  .header{background:#3d484a;padding:14px 24px;display:flex;align-items:center;gap:16px;border-bottom:1px solid #4F6367}
  .header h1{font-size:18px;font-weight:600;color:#B8D8D8}
  .header .dot{width:10px;height:10px;border-radius:50%;background:#4F6367;flex-shrink:0}
  .header .dot.live{background:#EEFF5D;box-shadow:0 0 8px #EEFF5D}
  .main{display:grid;grid-template-columns:1fr 340px;height:calc(100vh - 52px)}
  .video-pane{position:relative;background:#1e2426;display:flex;align-items:center;justify-content:center;overflow:hidden}
  .video-pane img{width:100%;height:100%;object-fit:contain}
  .side{background:#2a3234;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:14px;border-left:1px solid #4F6367}
  .card{background:#3d484a;border-radius:10px;padding:14px 16px;border:1px solid #4F6367}
  .card h2{font-size:13px;text-transform:uppercase;letter-spacing:1px;color:#7A9E9F;margin-bottom:10px}
  .status-row{display:flex;align-items:center;gap:10px;margin-bottom:8px}
  .badge{padding:4px 12px;border-radius:6px;font-size:14px;font-weight:700;letter-spacing:0.5px}
  .badge.normal{background:rgba(122,158,159,0.35);color:#B8D8D8;border:1px solid #7A9E9F}
  .badge.anomaly{background:rgba(254,95,85,0.2);color:#FE5F55;border:1px solid #FE5F55}
  .badge.waiting{background:rgba(79,99,103,0.5);color:#7A9E9F;border:1px solid #4F6367}
  .type-badge{padding:3px 10px;border-radius:5px;font-size:13px;font-weight:600;color:#2a3234}
  .type-FAINTING{background:#FE5F55}
  .type-SWAYING{background:#EEFF5D}
  .type-CROUCHING{background:#7A9E9F}
  .type-HAND_ON_HEAD{background:#B8D8D8;color:#2a3234}
  .type-UNKNOWN{background:#4F6367;color:#B8D8D8}
  .bar-container{background:#2a3234;border-radius:4px;height:14px;position:relative;overflow:hidden;margin-top:6px;border:1px solid #4F6367}
  .bar-fill{height:100%;border-radius:4px;transition:width .3s}
  .bar-threshold{position:absolute;top:-2px;bottom:-2px;width:2px;background:#EEFF5D;border-radius:1px;box-shadow:0 0 4px #EEFF5D}
  .score-row{display:flex;justify-content:space-between;font-size:12px;color:#7A9E9F;margin-top:4px}
  .feat-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}
  .feat-item{display:flex;justify-content:space-between;font-size:12px;padding:4px 8px;background:#2a3234;border-radius:5px;border:1px solid #4F6367}
  .feat-item .label{color:#7A9E9F}
  .feat-item .val{color:#EEFF5D;font-weight:500;font-variant-numeric:tabular-nums}
  .joint-grid{display:grid;grid-template-columns:1fr 1fr;gap:4px}
  .joint-item{font-size:11px;padding:3px 8px;background:#2a3234;border-radius:4px;display:flex;justify-content:space-between;gap:6px;border:1px solid #4F6367}
  .joint-item .name{color:#7A9E9F}
  .joint-item .coord{color:#B8D8D8;font-variant-numeric:tabular-nums}
  .conf-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:4px}
  .buf-bar{background:#2a3234;border-radius:4px;height:8px;overflow:hidden;margin-top:4px;border:1px solid #4F6367}
  .buf-fill{height:100%;background:linear-gradient(90deg,#7A9E9F,#EEFF5D);border-radius:4px;transition:width .3s}
  .fps{font-size:12px;color:#7A9E9F}
  .fps span{color:#EEFF5D;font-weight:600}
  .health-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
  .health-metric{background:#252a38;border-radius:8px;padding:10px 12px;text-align:center}
  .health-metric .h-label{font-size:11px;color:#8b92a8;text-transform:uppercase;letter-spacing:0.5px}
  .health-metric .h-val{font-size:22px;font-weight:700;margin-top:2px;font-variant-numeric:tabular-nums}
  .health-metric .h-unit{font-size:11px;color:#8b92a8;font-weight:400}
  .health-metric.hr .h-val{color:#ef4444}
  .health-metric.hrv .h-val{color:#f59e0b}
  .health-metric.spo2 .h-val{color:#3b82f6}
  .health-metric.accel .h-val{color:#8b5cf6;font-size:14px}
  .health-alert{margin-top:8px;padding:6px 10px;border-radius:6px;font-size:12px;font-weight:600;text-align:center;display:none}
  .health-alert.tachycardia{display:block;background:#7f1d1d;color:#fca5a5}
  .health-alert.hrv-drop{display:block;background:#78350f;color:#fde68a}
  .health-waiting{text-align:center;color:#8b92a8;font-size:12px;padding:8px}
  .watch-list{display:flex;flex-direction:column;gap:10px}
  .watch-item{display:flex;flex-direction:column;gap:2px;padding:12px 14px;background:#3d484a;border-radius:8px;border:2px solid #4F6367;box-shadow:0 2px 8px rgba(0,0,0,0.25);transition:border .2s,background .2s,box-shadow .2s}
  .watch-item.primary{border-color:#EEFF5D;background:rgba(238,255,93,0.08);box-shadow:0 0 0 1px rgba(238,255,93,0.3),0 2px 8px rgba(0,0,0,0.25)}
  .watch-item.active{border-color:#EEFF5D;background:rgba(238,255,93,0.12);box-shadow:0 0 0 2px rgba(238,255,93,0.4),0 2px 8px rgba(0,0,0,0.25)}
  .watch-item:not(.active){border-color:#FE5F55;background:rgba(254,95,85,0.08);box-shadow:0 0 0 2px rgba(254,95,85,0.35),0 2px 8px rgba(0,0,0,0.25)}
  .watch-item.primary:not(.active){border-color:#FE5F55;background:rgba(254,95,85,0.1);box-shadow:0 0 0 2px rgba(254,95,85,0.4),0 2px 8px rgba(0,0,0,0.25)}
  .watch-name{font-size:14px;font-weight:600;color:#B8D8D8}
  .watch-item.primary .watch-name{color:#EEFF5D}
  .watch-item.primary:not(.active) .watch-name{color:#FE5F55}
  .watch-item:not(.active) .watch-name{color:#B8D8D8}
  .watch-uuid{font-size:11px;font-family:ui-monospace,monospace;color:#7A9E9F;word-break:break-all}
  .watch-item:not(.active) .watch-uuid{color:#7A9E9F}
  .watch-actions{display:flex;gap:6px;margin-top:8px}
  .watch-btn{flex:1;padding:6px 10px;border:none;border-radius:5px;font-size:12px;font-weight:600;cursor:pointer;transition:background .2s,color .2s,opacity .2s}
  .watch-btn.activate{background:#EEFF5D;color:#2a3234}
  .watch-btn.activate:hover{background:#B8D8D8;color:#2a3234}
  .watch-btn.deactivate{background:#FE5F55;color:#fff}
  .watch-btn.deactivate:hover{background:#e54d43;color:#fff}
  .watch-btn.hidden{display:none}
  .watch-status{font-size:11px;font-weight:600;margin-top:4px;text-transform:uppercase;letter-spacing:0.5px}
  .watch-item.active .watch-status{color:#EEFF5D}
  .watch-item:not(.active) .watch-status{color:#FE5F55}
  .modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:1000;align-items:center;justify-content:center;padding:20px}
  .modal-overlay.show{display:flex}
  .modal-box{background:#3d484a;border:2px solid #FE5F55;border-radius:10px;padding:24px;min-width:320px;max-width:400px;box-shadow:0 0 0 2px rgba(254,95,85,0.3),0 8px 32px rgba(0,0,0,0.5)}
  .modal-box h3{font-size:16px;color:#B8D8D8;margin-bottom:16px}
  .modal-box label{display:block;font-size:12px;color:#7A9E9F;margin-bottom:6px}
  .modal-box input[type=email]{width:100%;padding:10px 12px;border:1px solid #4F6367;border-radius:6px;background:#2a3234;color:#B8D8D8;font-size:14px;margin-bottom:16px;box-sizing:border-box}
  .modal-box input[type=email]:focus{outline:none;border-color:#FE5F55}
  .modal-actions{display:flex;gap:10px;justify-content:flex-end}
  .modal-btn{padding:8px 18px;border:none;border-radius:6px;font-size:13px;font-weight:600;cursor:pointer;transition:background .2s,color .2s}
  .modal-btn.cancel{background:#4F6367;color:#B8D8D8}
  .modal-btn.cancel:hover{background:#7A9E9F}
  .modal-btn.send{background:#FE5F55;color:#fff}
  .modal-btn.send:hover{background:#e54d43}
</style>
</head>
<body>

<!-- Deactivate report popup -->
<div class="modal-overlay" id="reportModal">
  <div class="modal-box">
    <h3>Send deactivation report</h3>
    <label for="reportEmail">Email address</label>
    <input type="email" id="reportEmail" placeholder="you@example.com" />
    <p id="reportModalMessage" style="margin-top:10px;font-size:12px;min-height:18px;color:#7A9E9F"></p>
    <div class="modal-actions">
      <button type="button" class="modal-btn send" id="modalSendReport">Send report</button>
    </div>
  </div>
</div>

<div class="header">
  <div class="dot" id="liveDot"></div>
  <h1>POTS Anomaly Detection — Live Dashboard</h1>
  <div class="fps">FPS: <span id="fpsVal">--</span></div>
</div>

<div class="main">
  <div class="video-pane">
    <img id="stream" src="/pose/live" alt="Live stream" />
  </div>

  <div class="side">
    <!-- Watches (UUID + name) + Tracking status -->
    <div class="card">
      <h2>Watches</h2>
      <div style="font-size:12px;color:#7A9E9F;margin-bottom:10px;display:flex;flex-wrap:wrap;gap:6px;align-items:center">
        Target: <span id="bleName">--</span> <span id="bleDist" style="color:#EEFF5D;font-weight:600">--</span>
        &middot; Persons: <b id="personCount">0</b> &middot; Mode: <b id="trackMode">--</b> &middot; Focal: <b id="focalVal" style="color:#EEFF5D">uncalibrated</b>
      </div>
      <div class="watch-list" id="watchList">
        <div class="watch-item primary active" data-watch-id="a91c8e72" data-real-watch="true">
          <span class="watch-name">Watch A15</span>
          <span class="watch-uuid">a91c8e72-6b91-4f92-9c9b-6bafcd2e1d13</span>
          <span class="watch-status">Active</span>
          <div class="watch-actions">
            <button type="button" class="watch-btn activate hidden">Activate</button>
            <button type="button" class="watch-btn deactivate">Deactivate</button>
          </div>
        </div>
        <div class="watch-item" data-watch-id="b82d9f83">
          <span class="watch-name">Watch B22</span>
          <span class="watch-uuid">b82d9f83-7ca2-5g03-0d0c-7cbgde3f2e24</span>
          <span class="watch-status">Inactive</span>
          <div class="watch-actions">
            <button type="button" class="watch-btn activate">Activate</button>
            <button type="button" class="watch-btn deactivate hidden">Deactivate</button>
          </div>
        </div>
        <div class="watch-item" data-watch-id="c93e0g94">
          <span class="watch-name">Watch C34</span>
          <span class="watch-uuid">c93e0g94-8db3-6h14-1e1d-8dchef4g3f35</span>
          <span class="watch-status">Inactive</span>
          <div class="watch-actions">
            <button type="button" class="watch-btn activate">Activate</button>
            <button type="button" class="watch-btn deactivate hidden">Deactivate</button>
          </div>
        </div>
        <div class="watch-item" data-watch-id="d04f1ha5">
          <span class="watch-name">Watch D45</span>
          <span class="watch-uuid">d04f1ha5-9ec4-7i25-2f2e-9edifg5h4g46</span>
          <span class="watch-status">Inactive</span>
          <div class="watch-actions">
            <button type="button" class="watch-btn activate">Activate</button>
            <button type="button" class="watch-btn deactivate hidden">Deactivate</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Status card -->
    <div class="card">
      <h2>Detection Status</h2>
      <div class="status-row">
        <span class="badge waiting" id="statusBadge">Waiting...</span>
        <span class="type-badge type-UNKNOWN" id="typeBadge" style="display:none"></span>
      </div>
      <div class="bar-container">
        <div class="bar-fill" id="scoreBar" style="width:0%;background:#7A9E9F"></div>
        <div class="bar-threshold" id="threshLine" style="left:50%"></div>
      </div>
      <div class="score-row">
        <span>Score: <b id="scoreVal">0</b></span>
        <span>Threshold: <b id="threshVal">0</b></span>
      </div>
    </div>

    <!-- Health Data card -->
    <div class="card" id="healthCard">
      <h2>Health Connect</h2>
      <div id="healthWaiting" class="health-waiting">Waiting for anomaly detection (3s)&hellip;</div>
      <div id="healthData" style="display:none">
        <div class="health-grid">
          <div class="health-metric hr">
            <div class="h-label">Heart Rate</div>
            <div class="h-val"><span id="hrVal">--</span> <span class="h-unit">bpm</span></div>
          </div>
          <div class="health-metric hrv">
            <div class="h-label">HRV</div>
            <div class="h-val"><span id="hrvVal">--</span> <span class="h-unit">ms</span></div>
          </div>
          <div class="health-metric spo2">
            <div class="h-label">SpO2</div>
            <div class="h-val"><span id="spo2Val">--</span> <span class="h-unit">%</span></div>
          </div>
          <div class="health-metric accel">
            <div class="h-label">Accelerometer</div>
            <div class="h-val" id="accelVal">--</div>
          </div>
        </div>
        <div class="health-alert" id="healthAlert"></div>
      </div>
    </div>

    <!-- Buffer card -->
    <div class="card">
      <h2>Sequence Buffer</h2>
      <div style="font-size:13px">
        <span id="bufText">0 / 9 frames</span>
      </div>
      <div class="buf-bar"><div class="buf-fill" id="bufBar" style="width:0%"></div></div>
    </div>

    <!-- Engineered features -->
    <div class="card">
      <h2>Engineered Features</h2>
      <div class="feat-grid" id="featGrid"></div>
    </div>

    <!-- Joints -->
    <div class="card">
      <h2>Key Joints</h2>
      <div class="joint-grid" id="jointGrid"></div>
    </div>
  </div>
</div>

<script>
const FEAT_LABELS = {
  nose_y: "Nose Y",
  hip_y: "Hip Y",
  torso_len: "Torso Len",
  full_height: "Full Height",
  shoulder_angle: "Shoulder Ang",
  knee_angle: "Knee Ang",
  vertical_ratio: "Vert Ratio"
};

const TYPE_CLASSES = {
  "FAINTING": "type-FAINTING",
  "SWAYING": "type-SWAYING",
  "CROUCHING": "type-CROUCHING",
  "HAND ON HEAD": "type-HAND_ON_HEAD",
  "UNKNOWN": "type-UNKNOWN"
};

function connectWS() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/pose/ws`);

  ws.onopen = () => {
    document.getElementById("liveDot").classList.add("live");
  };

  ws.onclose = () => {
    document.getElementById("liveDot").classList.remove("live");
    setTimeout(connectWS, 2000);
  };

  ws.onmessage = (e) => {
    const d = JSON.parse(e.data);
    update(d);
  };
}

function update(d) {
  // BLE
  document.getElementById("bleName").textContent = d.target_ble || "--";
  document.getElementById("bleDist").textContent = d.ble_distance != null ? d.ble_distance + "m" : "--";
  document.getElementById("focalVal").textContent = d.focal_initialized ? d.focal_height : "waiting";
  document.getElementById("personCount").textContent = d.persons_detected || 0;
  const tm = d.tracking_mode || "--";
  const tmEl = document.getElementById("trackMode");
  tmEl.textContent = tm;
  tmEl.style.color = tm === "TRACKING" ? "#EEFF5D" : tm === "LOCK-ON" ? "#7A9E9F" : "#7A9E9F";

  // FPS
  document.getElementById("fpsVal").textContent = d.fps;

  // Status badge
  const badge = document.getElementById("statusBadge");
  badge.textContent = d.status;
  badge.className = "badge " + (d.is_anomaly ? "anomaly" : d.status.includes("Waiting") ? "waiting" : "normal");

  // Type badge
  const tb = document.getElementById("typeBadge");
  if (d.is_anomaly && d.anomaly_type) {
    tb.style.display = "inline";
    tb.textContent = d.anomaly_type;
    tb.className = "type-badge " + (TYPE_CLASSES[d.anomaly_type] || "type-UNKNOWN");
  } else {
    tb.style.display = "none";
  }

  // Score bar
  const maxScore = d.threshold * 2 || 1;
  const pct = Math.min(d.score / maxScore * 100, 100);
  const bar = document.getElementById("scoreBar");
  bar.style.width = pct + "%";
  bar.style.background = d.is_anomaly ? "#FE5F55" : "#7A9E9F";
  document.getElementById("threshLine").style.left = Math.min(d.threshold / maxScore * 100, 100) + "%";
  document.getElementById("scoreVal").textContent = d.score.toFixed(6);
  document.getElementById("threshVal").textContent = d.threshold.toFixed(6);

  // Buffer
  document.getElementById("bufText").textContent = d.buffer_fill + " / " + d.buffer_size + " frames";
  document.getElementById("bufBar").style.width = (d.buffer_fill / d.buffer_size * 100) + "%";

  // Engineered features
  const fg = document.getElementById("featGrid");
  let fhtml = "";
  for (const [key, label] of Object.entries(FEAT_LABELS)) {
    const v = d.engineered[key];
    const display = v !== undefined ? (key.includes("angle") ? v + "°" : v) : "--";
    fhtml += `<div class="feat-item"><span class="label">${label}</span><span class="val">${display}</span></div>`;
  }
  fg.innerHTML = fhtml;

  // Health data
  const h = d.health;
  if (h) {
    document.getElementById("healthWaiting").style.display = "none";
    document.getElementById("healthData").style.display = "block";
    document.getElementById("hrVal").textContent = h.heart_rate != null ? h.heart_rate : "--";
    document.getElementById("hrvVal").textContent = h.hrv != null ? h.hrv : "--";
    document.getElementById("spo2Val").textContent = h.spo2 != null ? h.spo2 : "--";
    const ax = h.accelerometer;
    if (ax) {
      document.getElementById("accelVal").textContent =
        `x:${ax.x.toFixed(1)} y:${ax.y.toFixed(1)} z:${ax.z.toFixed(1)}`;
    }
    const alert = document.getElementById("healthAlert");
    if (h.heart_rate && h.heart_rate >= 120) {
      alert.className = "health-alert tachycardia";
      alert.textContent = "\\u26a0 Tachycardia — HR " + h.heart_rate + " bpm";
    } else if (h.hrv && h.hrv < 20) {
      alert.className = "health-alert hrv-drop";
      alert.textContent = "\\u26a0 Low HRV — " + h.hrv + " ms";
    } else {
      alert.className = "health-alert";
    }
  }

  // Joints
  const jg = document.getElementById("jointGrid");
  let jhtml = "";
  for (const [name, coords] of Object.entries(d.joints || {})) {
    const [x, y, conf] = coords;
    const color = conf > 0.5 ? "#EEFF5D" : "#FE5F55";
    jhtml += `<div class="joint-item"><span class="name"><span class="conf-dot" style="background:${color}"></span>${name}</span><span class="coord">${x},${y}</span></div>`;
  }
  jg.innerHTML = jhtml;
}

function activate() {
  fetch("/pose/activate", {method: "POST"});
}

function deactivate() {
  fetch("/pose/deactivate", {method: "POST"});
}

connectWS();

// Stored email when user sends report (from deactivate popup)
let reportEmail = null;

const reportModal = document.getElementById("reportModal");
const reportEmailInput = document.getElementById("reportEmail");
const modalSendReport = document.getElementById("modalSendReport");

function openReportModal() {
  reportEmailInput.value = "";
  document.getElementById("reportModalMessage").textContent = "";
  reportModal.classList.add("show");
  reportEmailInput.focus();
}
function closeReportModal() {
  reportModal.classList.remove("show");
}

reportModal.addEventListener("click", function(e) {
  if (e.target === reportModal) closeReportModal();
});
modalSendReport.addEventListener("click", function() {
  var email = reportEmailInput.value.trim();
  var msgEl = document.getElementById("reportModalMessage");
  if (!email) {
    msgEl.textContent = "Please enter an email address.";
    msgEl.style.color = "#FE5F55";
    return;
  }
  modalSendReport.disabled = true;
  msgEl.textContent = "Sending...";
  msgEl.style.color = "#7A9E9F";
  fetch("/report/send-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: email })
  })
  .then(function(r) {
    if (r.ok) {
      msgEl.textContent = "Report sent! Check your inbox.";
      msgEl.style.color = "#EEFF5D";
      reportEmail = email;
      setTimeout(closeReportModal, 1200);
    } else {
      return r.json().then(function(d) {
        msgEl.textContent = d.detail || "Failed to send.";
        msgEl.style.color = "#FE5F55";
      }).catch(function() {
        msgEl.textContent = "Failed to send report.";
        msgEl.style.color = "#FE5F55";
      });
    }
  })
  .catch(function() {
    msgEl.textContent = "Network error. Try again.";
    msgEl.style.color = "#FE5F55";
  })
  .finally(function() {
    modalSendReport.disabled = false;
  });
});

// Watch activate / deactivate — only the first watch (data-real-watch) calls backend
document.getElementById("watchList").addEventListener("click", function(e) {
  const btn = e.target.closest(".watch-btn");
  if (!btn) return;
  const item = btn.closest(".watch-item");
  const isRealWatch = item.getAttribute("data-real-watch") === "true";
  const statusEl = item.querySelector(".watch-status");
  const activateBtn = item.querySelector(".watch-btn.activate");
  const deactivateBtn = item.querySelector(".watch-btn.deactivate");
  if (btn.classList.contains("activate")) {
    // Deactivate all others, then activate this one (UI)
    document.querySelectorAll(".watch-item").forEach(function(w) {
      w.classList.remove("active", "primary");
      w.querySelector(".watch-status").textContent = "Inactive";
      w.querySelector(".watch-btn.activate").classList.remove("hidden");
      w.querySelector(".watch-btn.deactivate").classList.add("hidden");
    });
    item.classList.add("active", "primary");
    statusEl.textContent = "Active";
    activateBtn.classList.add("hidden");
    deactivateBtn.classList.remove("hidden");
    if (isRealWatch) activate();
  } else if (btn.classList.contains("deactivate")) {
    item.classList.remove("active", "primary");
    statusEl.textContent = "Inactive";
    activateBtn.classList.remove("hidden");
    deactivateBtn.classList.add("hidden");
    if (isRealWatch) {
      deactivate();
      openReportModal();
    }
  }
});
</script>
</body>
</html>"""


@router.get("/pose/view", response_class=HTMLResponse)
async def pose_dashboard():
    _ensure_bg()
    return HTMLResponse(DASHBOARD_HTML)


