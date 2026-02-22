"""
Pose + LSTM anomaly detection — web dashboard.

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

# ── shared state (written by bg thread, read by endpoints) ──

_lock = threading.Lock()
_state: dict[str, Any] = {
    "jpeg": b"",
    "telemetry": {},
}


def _bg_loop():
    """Background thread: camera → YOLO → features → LSTM → classifier."""
    source: Any = int(VIDEO_SOURCE) if VIDEO_SOURCE.isdigit() else VIDEO_SOURCE
    use_cap = isinstance(source, int)

    predictor = AnomalyPredictor(model_path=MODEL_PATH)
    cfg = predictor.pipeline_config
    frame_step = FRAME_STEP or cfg.get("frame_step", 10)
    window_size = cfg["window_size"]

    extractor = KeypointExtractor()
    engineer = FeatureEngineer()
    buffer = SequenceBuffer(window_size=window_size, num_features=75)

    cap = None
    if use_cap:
        cap = cv2.VideoCapture(source)

    frame_count = 0
    label = "Waiting for buffer..."
    score = 0.0
    threshold = predictor.threshold
    is_anomaly = False
    anomaly_type = ""
    fps = 0.0
    prev_t = time.time()
    last_eng: dict = {}
    last_joints: dict = {}

    eng_names = ["nose_y", "hip_y", "torso_len", "full_height",
                 "shoulder_angle", "knee_angle", "vertical_ratio"]
    joint_map = [
        (0, "Nose"), (5, "L Shoulder"), (6, "R Shoulder"),
        (9, "L Wrist"), (10, "R Wrist"),
        (11, "L Hip"), (12, "R Hip"),
        (15, "L Ankle"), (16, "R Ankle"),
    ]

    while True:
        # grab frame
        if use_cap:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue
        else:
            import requests as _req
            try:
                resp = _req.get(source, timeout=5)
                arr = np.frombuffer(resp.content, dtype=np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame is None:
                    raise ValueError("decode failed")
            except Exception:
                time.sleep(1)
                continue

        frame_count += 1
        fh, fw = frame.shape[:2]

        kps_raw, annotated = extractor.extract(frame)

        if kps_raw is not None:
            # joints for telemetry
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
            label = "No person detected"
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
        }

        with _lock:
            _state["jpeg"] = jpeg.tobytes()
            _state["telemetry"] = telemetry

        time.sleep(0.01)


_thread_started = False


def _ensure_bg():
    global _thread_started
    if not _thread_started:
        _thread_started = True
        t = threading.Thread(target=_bg_loop, daemon=True)
        t.start()


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

connectWS();
</script>
</body>
</html>"""


@router.get("/pose/view", response_class=HTMLResponse)
async def pose_dashboard():
    _ensure_bg()
    return HTMLResponse(DASHBOARD_HTML)
