"""
Live video stream + YOLOv8-pose + LSTM anomaly detection.

Fetches frames from camera, runs YOLO pose, engineers 75 features,
buffers into sliding windows, runs LSTM autoencoder, overlays result.

    python -m frame.live_pose_lstm --source 0               # webcam
    python -m frame.live_pose_lstm --source 1               # external USB camera
    python -m frame.live_pose_lstm --source http://...      # HTTP stream (Pi)
"""

import argparse
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import requests

_cv_backend = Path(__file__).resolve().parent.parent
if str(_cv_backend) not in sys.path:
    sys.path.insert(0, str(_cv_backend))

from core.keypoint_extractor import KeypointExtractor
from core.feature_engineering import FeatureEngineer
from core.sequence_buffer import SequenceBuffer
from core.lstm_inference import AnomalyPredictor
from core.anomaly_classifier import classify_anomaly, COLOR_MAP

VIDEO_STREAM_URL = "http://10.136.28.70:5000/video-stream"


def fetch_frame(url: str) -> np.ndarray | None:
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            arr = np.frombuffer(resp.content, dtype=np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"Frame fetch error: {e}")
    return None


def draw_overlay(frame, label, score, threshold, is_anomaly, fps,
                 buf_fill, buf_size, engineered, kps_raw,
                 anomaly_type, anomaly_color):
    h, w = frame.shape[:2]
    panel_w = 280

    # --- right-side info panel ---
    overlay = frame.copy()
    cv2.rectangle(overlay, (w - panel_w, 0), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    x0 = w - panel_w + 10
    y = 25
    white = (255, 255, 255)
    gray = (160, 160, 160)
    green = (0, 255, 0)
    red = (0, 0, 255)
    cyan = (255, 255, 0)

    def text(txt, color=white, scale=0.45, thick=1):
        nonlocal y
        cv2.putText(frame, txt, (x0, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick)
        y += 20

    def heading(txt):
        nonlocal y
        cv2.putText(frame, txt, (x0, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cyan, 1)
        y += 22

    # LSTM status
    heading("LSTM ANOMALY DETECTION")
    status_color = red if is_anomaly else green
    text(f"Status: {label}", status_color, 0.5, 2)
    if is_anomaly:
        text(f"Type:  {anomaly_type}", anomaly_color, 0.55, 2)
    text(f"Score:     {score:.6f}", white)
    text(f"Threshold: {threshold:.6f}", gray)
    text(f"Buffer:    {buf_fill} / {buf_size} frames", gray)
    y += 5

    # anomaly bar
    bar_x = x0
    bar_w = panel_w - 20
    cv2.rectangle(frame, (bar_x, y), (bar_x + bar_w, y + 10), (50, 50, 50), -1)
    fill = min(score / (threshold * 2 + 1e-8), 1.0)
    cv2.rectangle(frame, (bar_x, y), (bar_x + int(fill * bar_w), y + 10), status_color, -1)
    thresh_x = int((threshold / (threshold * 2 + 1e-8)) * bar_w) + bar_x
    cv2.line(frame, (thresh_x, y - 2), (thresh_x, y + 12), white, 2)
    y += 22

    # engineered features
    if engineered is not None:
        heading("ENGINEERED FEATURES")
        names = ["Nose Y", "Hip Y", "Torso Len", "Full Height",
                 "Shoulder Ang", "Knee Ang", "Vert Ratio"]
        for name, val in zip(names, engineered):
            if "Ang" in name:
                text(f"{name:>12s}: {math.degrees(val):6.1f} deg", gray)
            else:
                text(f"{name:>12s}: {val:.4f}", gray)
        y += 5

    # key joint positions (pixel coords)
    if kps_raw is not None:
        heading("KEY JOINTS (px)")
        joint_names = [
            (0, "Nose"), (5, "L Shoulder"), (6, "R Shoulder"),
            (9, "L Wrist"), (10, "R Wrist"),
            (11, "L Hip"), (12, "R Hip"),
            (15, "L Ankle"), (16, "R Ankle"),
        ]
        for idx, name in joint_names:
            px, py, conf = kps_raw[idx]
            c = green if conf > 0.5 else red
            text(f"{name:>12s}: ({int(px):4d},{int(py):4d}) {conf:.2f}", c)

    # --- big classification banner when anomaly ---
    if is_anomaly and anomaly_type != "UNKNOWN":
        banner_h = 50
        banner_overlay = frame.copy()
        cv2.rectangle(banner_overlay, (0, h - banner_h), (w - panel_w, h), anomaly_color, -1)
        cv2.addWeighted(banner_overlay, 0.6, frame, 0.4, 0, frame)
        cv2.putText(frame, anomaly_type, (15, h - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, white, 3)

    # FPS top-left
    cv2.rectangle(frame, (0, 0), (130, 30), (0, 0, 0), -1)
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, green, 2)

    return frame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=VIDEO_STREAM_URL,
                        help="Camera index (0,1,..) or stream URL")
    parser.add_argument("--model", default="models/pots_model_complete.pt")
    parser.add_argument("--frame-step", type=int, default=None,
                        help="Feed LSTM every N-th frame (default: from model config)")
    args = parser.parse_args()

    source = args.source
    use_videocap = source.isdigit()
    if use_videocap:
        source = int(source)

    print("Loading LSTM model...")
    predictor = AnomalyPredictor(model_path=args.model)
    cfg = predictor.pipeline_config
    frame_step = args.frame_step or cfg.get("frame_step", 10)
    window_size = cfg["window_size"]
    print(f"  window={window_size}  frame_step={frame_step}  threshold={predictor.threshold:.4f}")

    extractor = KeypointExtractor()
    engineer = FeatureEngineer()
    buffer = SequenceBuffer(window_size=window_size, num_features=75)

    cap = None
    if use_videocap:
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            print(f"Cannot open camera {source}")
            sys.exit(1)
        print(f"Opened camera {source}")
    else:
        print(f"Streaming from {source}")

    print("Press 'q' to quit.\n")

    frame_count = 0
    label = "Waiting for buffer..."
    score = 0.0
    threshold = predictor.threshold
    is_anomaly = False
    anomaly_type = ""
    anomaly_color = COLOR_MAP["UNKNOWN"]
    fps = 0.0
    prev_t = time.time()
    last_engineered = None
    last_kps_raw = None

    while True:
        if use_videocap:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue
        else:
            frame = fetch_frame(source)
            if frame is None:
                time.sleep(1)
                continue

        frame_count += 1
        fh, fw = frame.shape[:2]

        kps_raw, annotated = extractor.extract(frame)

        if kps_raw is not None:
            last_kps_raw = kps_raw
            if frame_count % frame_step == 0:
                features = engineer.compute(kps_raw, frame_w=fw, frame_h=fh)
                last_engineered = features[68:]
                ready = buffer.add(features)
                if ready:
                    window = buffer.get_window()
                    result = predictor.predict(window)
                    score = result["score"]
                    is_anomaly = result["is_anomaly"]
                    threshold = result["threshold"]
                    if is_anomaly:
                        label = "ANOMALY DETECTED"
                        anomaly_type, anomaly_color = classify_anomaly(window)
                    else:
                        label = "Normal"
                        anomaly_type = ""
                        anomaly_color = COLOR_MAP["UNKNOWN"]
        else:
            label = "No person detected"
            last_kps_raw = None
            last_engineered = None

        now = time.time()
        fps = 0.9 * fps + 0.1 / max(now - prev_t, 1e-6)
        prev_t = now

        annotated = draw_overlay(
            annotated, label, score, threshold, is_anomaly,
            fps, len(buffer._buffer), buffer.window_size,
            last_engineered, last_kps_raw,
            anomaly_type, anomaly_color,
        )
        cv2.imshow("Live Pose + LSTM", annotated)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    if cap:
        cap.release()
    extractor.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
