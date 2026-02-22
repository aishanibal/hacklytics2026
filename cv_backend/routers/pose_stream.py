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
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
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
TARGET_BLE_NAME: str = os.getenv("TARGET_BLE_NAME", "TARGET_A15")

TEST_BLE_REQUESTS = [
    {"name": "TARGET_A15", "UUID": "a91c8e72-6b91-4f92-9c9b-6bafcd2e1d13", "mac-address": "AA:BB:CC:DD:EE:01", "distance": 2.5},
    {"name": "Device_02", "UUID": "b82d9f83-7ca2-5g03-0d0c-7cbgde3f2e24", "mac-address": "AA:BB:CC:DD:EE:02", "distance": 3.1},
    {"name": "Device_03", "UUID": "c93e0g94-8db3-6h14-1e1d-8dchef4g3f35", "mac-address": "AA:BB:CC:DD:EE:03", "distance": 1.8},
]


def _get_ble_data() -> list[dict]:
    """Fetch BLE device list (test or live API)."""
    if USE_TEST_BLE:
        return TEST_BLE_REQUESTS
    try:
        r = http_requests.get(BLE_DATA_URL, timeout=2)
        if r.status_code != 200:
            return TEST_BLE_REQUESTS
        data = r.json()
        if isinstance(data, list):
            return data
        raw = data.get("Requests") or data.get("requests") or []
        return raw if isinstance(raw, list) else TEST_BLE_REQUESTS
    except Exception:
        return TEST_BLE_REQUESTS



# Calibration constant: person at D meters has bbox height ≈ FOCAL_HEIGHT / D pixels.
# Tune for your camera: measure someone's bbox height at a known distance,
# then FOCAL_HEIGHT = distance_meters * bbox_height_pixels.
# e.g. person at 2m with bbox height 300px → FOCAL_HEIGHT = 600
FOCAL_HEIGHT: float = float(os.getenv("FOCAL_HEIGHT", "600"))


def _match_target(detections: list[dict], ble_devices: list[dict],
                  target_name: str) -> tuple[dict | None, float | None]:
    """
    Use BLE distance to pick the person in the crowd whose bbox-estimated
    distance best matches the BLE-reported distance.
    Returns (detection, ble_distance) or (None, None).
    """
    if not detections:
        return None, None

    target_ble = None
    for b in ble_devices:
        if (b.get("name") or "") == target_name:
            target_ble = b
            break

    if target_ble is None:
        return None, None

    ble_dist = float(target_ble.get("distance", 999))

    # estimate each person's distance from camera using bbox height
    # then pick the one closest to the BLE distance
    best: dict | None = None
    best_diff = float("inf")
    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        bbox_h = max(y2 - y1, 1)
        estimated_dist = FOCAL_HEIGHT / bbox_h
        diff = abs(estimated_dist - ble_dist)
        if diff < best_diff:
            best_diff = diff
            best = det

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
            matched, matched_dist = _match_target(detections, ble_devices, TARGET_BLE_NAME)
            if matched is not None:
                target = matched
                target_bbox = matched["bbox"]
                ble_dist = matched_dist
                lost_count = 0
                tracking_mode = "TRACKING"
                x1, y1, x2, y2 = matched["bbox"]
                est = FOCAL_HEIGHT / max(y2 - y1, 1)
                print(f"[pose] Locked onto {TARGET_BLE_NAME} "
                      f"(BLE: {ble_dist:.1f}m, est: {est:.1f}m, bbox_h: {y2-y1:.0f}px)")
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

            dist_label = f"{TARGET_BLE_NAME}"
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
                    else:
                        label = "Normal"
                        anomaly_type = ""
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
            "target_ble": TARGET_BLE_NAME,
            "ble_distance": round(ble_dist, 2) if ble_dist is not None else None,
            "persons_detected": len(detections),
            "tracking_mode": tracking_mode,
            "lost_count": lost_count,
        }

        with _lock:
            _state["jpeg"] = jpeg.tobytes()
            _state["telemetry"] = telemetry


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
            if t:
                await ws.send_text(json.dumps(t))
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
  body{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;background:#0f1117;color:#e0e0e0;overflow-x:hidden}
  .header{background:#161a25;padding:14px 24px;display:flex;align-items:center;gap:16px;border-bottom:1px solid #252a38}
  .header h1{font-size:18px;font-weight:600;color:#fff}
  .header .dot{width:10px;height:10px;border-radius:50%;background:#555;flex-shrink:0}
  .header .dot.live{background:#22c55e;box-shadow:0 0 6px #22c55e}
  .main{display:grid;grid-template-columns:1fr 340px;height:calc(100vh - 52px)}
  .video-pane{position:relative;background:#000;display:flex;align-items:center;justify-content:center;overflow:hidden}
  .video-pane img{width:100%;height:100%;object-fit:contain}
  .side{background:#161a25;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:14px;border-left:1px solid #252a38}
  .card{background:#1c2030;border-radius:10px;padding:14px 16px;border:1px solid #252a38}
  .card h2{font-size:13px;text-transform:uppercase;letter-spacing:1px;color:#8b92a8;margin-bottom:10px}
  .status-row{display:flex;align-items:center;gap:10px;margin-bottom:8px}
  .badge{padding:4px 12px;border-radius:6px;font-size:14px;font-weight:700;letter-spacing:0.5px}
  .badge.normal{background:#14532d;color:#4ade80}
  .badge.anomaly{background:#7f1d1d;color:#fca5a5}
  .badge.waiting{background:#3b3b1f;color:#fde68a}
  .type-badge{padding:3px 10px;border-radius:5px;font-size:13px;font-weight:600;color:#fff}
  .type-FAINTING{background:#dc2626}
  .type-SWAYING{background:#ea580c}
  .type-CROUCHING{background:#2563eb}
  .type-HAND_ON_HEAD{background:#16a34a}
  .type-UNKNOWN{background:#6b7280}
  .bar-container{background:#252a38;border-radius:4px;height:14px;position:relative;overflow:hidden;margin-top:6px}
  .bar-fill{height:100%;border-radius:4px;transition:width .3s}
  .bar-threshold{position:absolute;top:-2px;bottom:-2px;width:2px;background:#fff;border-radius:1px}
  .score-row{display:flex;justify-content:space-between;font-size:12px;color:#8b92a8;margin-top:4px}
  .feat-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}
  .feat-item{display:flex;justify-content:space-between;font-size:12px;padding:4px 8px;background:#252a38;border-radius:5px}
  .feat-item .label{color:#8b92a8}
  .feat-item .val{color:#e0e0e0;font-weight:500;font-variant-numeric:tabular-nums}
  .joint-grid{display:grid;grid-template-columns:1fr 1fr;gap:4px}
  .joint-item{font-size:11px;padding:3px 8px;background:#252a38;border-radius:4px;display:flex;justify-content:space-between;gap:6px}
  .joint-item .name{color:#8b92a8}
  .joint-item .coord{font-variant-numeric:tabular-nums}
  .conf-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:4px}
  .buf-bar{background:#252a38;border-radius:4px;height:8px;overflow:hidden;margin-top:4px}
  .buf-fill{height:100%;background:#6366f1;border-radius:4px;transition:width .3s}
  .fps{font-size:12px;color:#8b92a8}
  .fps span{color:#22c55e;font-weight:600}
</style>
</head>
<body>

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
    <!-- Control + BLE target card -->
    <div class="card">
      <h2>Tracking Control</h2>
      <div style="display:flex;gap:8px;margin-bottom:10px">
        <button id="btnActivate" onclick="activate()" style="flex:1;padding:8px;border:none;border-radius:6px;background:#16a34a;color:#fff;font-weight:700;font-size:14px;cursor:pointer">ACTIVATE</button>
        <button id="btnDeactivate" onclick="deactivate()" style="flex:1;padding:8px;border:none;border-radius:6px;background:#dc2626;color:#fff;font-weight:700;font-size:14px;cursor:pointer">DEACTIVATE</button>
      </div>
      <div style="font-size:13px;display:flex;justify-content:space-between">
        <span id="bleName">--</span>
        <span id="bleDist" style="color:#6366f1;font-weight:600">--</span>
      </div>
      <div style="font-size:12px;color:#8b92a8;margin-top:4px">
        Persons in frame: <b id="personCount">0</b> &middot; Mode: <b id="trackMode">--</b>
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
        <div class="bar-fill" id="scoreBar" style="width:0%;background:#22c55e"></div>
        <div class="bar-threshold" id="threshLine" style="left:50%"></div>
      </div>
      <div class="score-row">
        <span>Score: <b id="scoreVal">0</b></span>
        <span>Threshold: <b id="threshVal">0</b></span>
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
  document.getElementById("personCount").textContent = d.persons_detected || 0;
  const tm = d.tracking_mode || "--";
  const tmEl = document.getElementById("trackMode");
  tmEl.textContent = tm;
  tmEl.style.color = tm === "TRACKING" ? "#22c55e" : tm === "LOCK-ON" ? "#fde68a" : "#8b92a8";

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
  bar.style.background = d.is_anomaly ? "#ef4444" : "#22c55e";
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

  // Joints
  const jg = document.getElementById("jointGrid");
  let jhtml = "";
  for (const [name, coords] of Object.entries(d.joints || {})) {
    const [x, y, conf] = coords;
    const color = conf > 0.5 ? "#22c55e" : "#ef4444";
    jhtml += `<div class="joint-item"><span class="name"><span class="conf-dot" style="background:${color}"></span>${name}</span><span class="coord">${x},${y}</span></div>`;
  }
  jg.innerHTML = jhtml;
}

function activate() {
  fetch("/pose/activate", {method: "POST"}).then(() => {
    document.getElementById("btnActivate").style.opacity = "1";
    document.getElementById("btnDeactivate").style.opacity = "0.4";
  });
}

function deactivate() {
  fetch("/pose/deactivate", {method: "POST"}).then(() => {
    document.getElementById("btnActivate").style.opacity = "0.4";
    document.getElementById("btnDeactivate").style.opacity = "1";
  });
}

document.getElementById("btnActivate").style.opacity = "0.4";
document.getElementById("btnDeactivate").style.opacity = "1";

connectWS();
</script>
</body>
</html>"""


@router.get("/pose/view", response_class=HTMLResponse)
async def pose_dashboard():
    _ensure_bg()
    return HTMLResponse(DASHBOARD_HTML)
