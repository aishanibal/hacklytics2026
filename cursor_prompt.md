# 🧠 Cursor AI Prompt — Hackathon Project: Health & Anomaly Detection Platform

---

## 📌 PROJECT OVERVIEW

You are helping build a **real-time health monitoring and anomaly detection platform** for a hackathon. The system has three major pillars:

1. **Flutter mobile app** — the primary UI and orchestration layer
2. **Samsung Galaxy Watch (Wear OS / Tizen) → Android (Kotlin)** — collects biometric sensor data from the smartwatch and pipes it to the Flutter app via platform channels
3. **Computer Vision (CV) backend** — FastAPI server running PyTorch YOLOv8, MediaPipe, and ByteTrack for real-time anomaly detection via video feed
4. **Generative AI Report Endpoint** — aggregates sensor + CV event data and generates a structured incident report

This is a hackathon codebase, so prioritize **working prototypes over production-level polish**, but keep the architecture clean and modular so pieces can be swapped or upgraded after the hackathon.

---

## 🗂️ PROJECT STRUCTURE

```
/
├── flutter_app/                  # Flutter frontend
│   ├── lib/
│   │   ├── main.dart
│   │   ├── screens/
│   │   ├── services/
│   │   │   ├── sensor_service.dart       # Platform channel to Kotlin
│   │   │   ├── cv_service.dart           # WebSocket/HTTP to FastAPI CV
│   │   │   └── report_service.dart       # GenAI report endpoint
│   │   ├── models/
│   │   │   ├── biometric_data.dart
│   │   │   └── incident_report.dart
│   │   └── widgets/
│   ├── android/
│   │   └── app/src/main/kotlin/com/yourapp/
│   │       ├── MainActivity.kt
│   │       ├── SamsungHealthPlugin.kt    # Samsung Health SDK bridge
│   │       └── WatchDataManager.kt       # Manages watch → phone BLE/SDK data
│   └── pubspec.yaml
│
├── cv_backend/                   # FastAPI computer vision server
│   ├── main.py                   # FastAPI app entrypoint
│   ├── routers/
│   │   ├── stream.py             # Video stream endpoint (WebSocket)
│   │   └── report.py             # GenAI report endpoint
│   ├── core/
│   │   ├── detector.py           # YOLOv8 inference wrapper
│   │   ├── tracker.py            # ByteTrack integration
│   │   ├── pose.py               # MediaPipe pose/holistic
│   │   └── anomaly.py            # Anomaly logic: fall, collapse, erratic motion
│   ├── models/                   # Downloaded model weights (gitignored)
│   ├── schemas/
│   │   ├── sensor_payload.py     # Incoming sensor data schema
│   │   └── incident_report.py    # Outgoing report schema
│   ├── requirements.txt
│   └── Dockerfile
│
└── notebooks/                    # Google Colab prototyping
    ├── cv_pipeline_prototype.ipynb
    └── genai_report_prototype.ipynb
```

---

## 📱 PILLAR 1 — FLUTTER APP

### General Rules
- Use **Flutter 3.x** with null safety enabled
- State management: **Riverpod** (preferred) or Provider
- Use **MethodChannel** for Kotlin communication, **EventChannel** for streaming sensor data
- Handle all sensor data as streams — display live vitals on a dashboard screen
- Use `http` and `web_socket_channel` packages for CV backend communication

### Key Screens to Scaffold
1. **Dashboard screen** — live heart rate, SpO2, steps, skin temp as cards with sparkline charts
2. **Camera/CV screen** — live video preview + overlay of detections, anomaly alert banner
3. **Incident Report screen** — displays the GenAI-generated report when an anomaly is confirmed

### Sensor Service (sensor_service.dart)
```dart
// scaffold this as a stream-based service
// EventChannel name: "com.yourapp/sensor_stream"
// Data arrives as a Map<String, dynamic> with keys:
//   heartRate (double, bpm)
//   spo2 (double, %)
//   stepCount (int)
//   skinTemperature (double, °C)
//   timestamp (int, epoch ms)
```

---

## ⌚ PILLAR 2 — KOTLIN / SAMSUNG HEALTH BRIDGE

### Context
- Target device: **Samsung Galaxy Watch** (Galaxy Watch 4/5/6 — Wear OS)
- Data flows: Watch → Samsung Health app on phone → our app via **Samsung Health SDK** or **Health Platform API**
- Use **Samsung Health SDK for Android** (privileged access requires partner approval, but use the public Health Connect / Samsung Health Data API for hackathon)
- Fallback: Use **Android Health Connect API** (`androidx.health.connect`) which Samsung watches write to

### Files to Generate

#### `SamsungHealthPlugin.kt`
- Registers a Flutter `MethodChannel` (`com.yourapp/samsung_health`) and `EventChannel` (`com.yourapp/sensor_stream`)
- On `startListening` method call: initializes Health Connect client, requests permissions for:
  - `HeartRate`
  - `OxygenSaturation` (SpO2)
  - `Steps`
  - `SkinTemperature`
- Reads data on a **15-second polling loop** using coroutines
- Broadcasts data to Flutter via `EventChannel` sink

#### `WatchDataManager.kt`
- Manages the Health Connect `HealthConnectClient`
- Provides suspend functions:
  - `getLatestHeartRate(): Double?`
  - `getLatestSpO2(): Double?`
  - `getStepCount(durationMinutes: Int): Int`
  - `getLatestSkinTemperature(): Double?`
- Handles permission checks and graceful fallbacks (return null if unavailable)

#### `MainActivity.kt`
- Registers the plugin and handles the Health Connect permission result callback

### Important Notes for Cursor
- Import `androidx.health.connect.client.*` — do NOT use deprecated Google Fit APIs
- Use `kotlinx.coroutines` for async reads
- All sensor reads should be wrapped in `try/catch` — never crash if a sensor is unavailable
- The EventChannel should use a `Handler` on the main thread to broadcast to Flutter

---

## 🎥 PILLAR 3 — COMPUTER VISION BACKEND (FastAPI)

### Tech Stack
- **FastAPI** — async API framework
- **PyTorch + Ultralytics YOLOv8** — object/person detection
- **MediaPipe** — pose estimation (landmarks), holistic model
- **ByteTrack** — multi-object tracking across frames
- **OpenCV** — frame capture and preprocessing

### `main.py` — FastAPI App
```python
# Scaffold a FastAPI app with:
# - WebSocket endpoint: /ws/stream  (receives base64 JPEG frames from Flutter)
# - POST endpoint: /analyze/frame   (single frame analysis, for testing)
# - POST endpoint: /report/generate (GenAI report, see Pillar 4)
# - GET endpoint:  /health          (healthcheck)
# CORS enabled for all origins (hackathon mode)
```

### `core/detector.py` — YOLOv8 Wrapper
```python
# Class: AnomalyDetector
# - Loads yolov8n.pt or yolov8s.pt on init (auto-download)
# - Method: detect(frame: np.ndarray) -> List[Detection]
#   Returns: [{bbox, confidence, class_id, class_name}]
# - Filter to person class (class_id=0) only
# - Confidence threshold: 0.45
```

### `core/tracker.py` — ByteTrack Integration
```python
# Use: pip install bytetracker (or git+https://github.com/ifzhang/ByteTrack)
# Class: PersonTracker
# - Wraps ByteTrack BYTETracker
# - Method: update(detections, frame_shape) -> List[TrackedPerson]
#   Each TrackedPerson: {track_id, bbox, age, is_new}
# - Maintains track history (last 30 frames) per track_id for motion analysis
```

### `core/pose.py` — MediaPipe Pose
```python
# Class: PoseAnalyzer
# - Uses mp.solutions.pose (Pose) — NOT holistic, for speed
# - Method: analyze(frame, bbox) -> PoseResult
#   Returns: {landmarks, visibility_scores, is_pose_detected}
# - Crops frame to bbox before running MediaPipe for efficiency
```

### `core/anomaly.py` — Anomaly Detection Logic
```python
# Class: AnomalyClassifier
# Input: TrackedPerson history + PoseResult
# Detects:
#   - FALL: person bbox aspect ratio suddenly becomes wide (width >> height), 
#           combined with low vertical landmark positions
#   - COLLAPSE: person disappears from frame after being tracked for >5s
#   - ERRATIC_MOTION: high variance in centroid displacement over last 10 frames
#   - STATIONARY_DOWN: person detected but motionless in non-standing pose for >10s
# Output: AnomalyEvent {type, track_id, confidence, timestamp, frame_snapshot_b64}
```

### WebSocket Flow (`routers/stream.py`)
```
Flutter sends: { "frame": "<base64 jpeg>", "sensor_data": {...} }
Server processes: decode → YOLO detect → ByteTrack → MediaPipe → Anomaly check
Server sends back: { 
  "tracks": [...], 
  "anomalies": [...],   # empty list if none
  "pose_data": {...},
  "frame_id": int 
}
If anomaly detected → also emit to an internal event queue for report generation
```

---

## 🤖 PILLAR 4 — GENERATIVE AI INCIDENT REPORT ENDPOINT

### Endpoint: `POST /report/generate`

### Input Schema (`schemas/sensor_payload.py`)
```python
class SensorSnapshot(BaseModel):
    heart_rate: Optional[float]       # bpm
    spo2: Optional[float]             # %
    step_count: Optional[int]
    skin_temperature: Optional[float] # °C
    timestamp: int                    # epoch ms

class AnomalyEvent(BaseModel):
    type: str                         # FALL | COLLAPSE | ERRATIC_MOTION | STATIONARY_DOWN
    confidence: float
    track_id: int
    timestamp: int
    duration_seconds: Optional[float]
    frame_snapshot_b64: Optional[str] # base64 JPEG thumbnail

class ReportRequest(BaseModel):
    anomaly_event: AnomalyEvent
    sensor_snapshot: SensorSnapshot
    location_context: Optional[str]   # e.g. "home", "gym", "outdoor"
    user_profile: Optional[dict]      # age, known conditions — stub for now
```

### Output Schema (`schemas/incident_report.py`)
```python
class IncidentReport(BaseModel):
    report_id: str                    # uuid
    generated_at: int                 # epoch ms
    severity: str                     # LOW | MODERATE | HIGH | CRITICAL
    summary: str                      # 2-3 sentence plain English summary
    vitals_assessment: str            # interpretation of sensor data
    cv_assessment: str                # what was visually detected
    recommended_action: str           # e.g. "Call emergency services", "Check on individual"
    raw_sensor: SensorSnapshot
    raw_anomaly: AnomalyEvent
```

### LLM Integration (stub, to be fine-tuned later)
```python
# Use OpenAI client (or swap for any OpenAI-compatible endpoint):
# from openai import AsyncOpenAI
# 
# Build a structured prompt:
# SYSTEM: "You are a medical triage assistant analyzing sensor and camera data..."
# USER: f"Anomaly detected: {anomaly_event.type}. 
#         Confidence: {anomaly_event.confidence:.0%}.
#         Biometrics at time of event — HR: {sensor.heart_rate} bpm, 
#         SpO2: {sensor.spo2}%, Skin temp: {sensor.skin_temperature}°C.
#         Location context: {location_context}.
#         Generate a structured incident report."
#
# Parse response into IncidentReport schema
# Model: gpt-4o-mini (fast + cheap for hackathon)
# Temperature: 0.3 (consistent outputs)
# Add "fine-tune this prompt later" comment markers throughout
```

---

## 📓 GOOGLE COLAB NOTEBOOK SCAFFOLD

### `cv_pipeline_prototype.ipynb`

Structure the notebook with these cells/sections:

1. **Setup & Installs** — `ultralytics`, `mediapipe`, `lap`, bytetrack clone
2. **Upload Test Video** — use `google.colab.files.upload()` or mount Drive
3. **YOLOv8 Person Detection** — run on sample frames, visualize bboxes
4. **ByteTrack Integration** — track persons across frames, draw track IDs
5. **MediaPipe Pose on Tracked Persons** — crop + pose, visualize landmarks
6. **Anomaly Logic** — implement and test fall/collapse detection rules
7. **End-to-End Pipeline** — process full video, output annotated frames as GIF/MP4
8. **Export Colab → FastAPI** — notes on which classes map to which `core/` files

---

## ⚙️ DEVELOPMENT RULES FOR CURSOR

1. **Never hallucinate imports** — only use packages listed in `requirements.txt` or `pubspec.yaml`. If a package is needed, add it to those files explicitly.
2. **Async everywhere in FastAPI** — all endpoints and DB/model calls must be `async`. Use `asyncio.to_thread()` for blocking model inference.
3. **Type hints on everything** — Python files must have full type annotations. Dart files must have explicit types (no `var` for class-level fields).
4. **Sensor nullability** — always treat sensor values as nullable. The watch may not have all sensors or may be out of range. Never crash on null sensor data.
5. **Platform channel naming** — use the prefix `com.yourapp/` consistently for all channels.
6. **Model weights** — never commit weights to git. Always download on first run and cache locally. Add `models/*.pt` to `.gitignore`.
7. **ByteTrack** — assume install from source (`git clone` in requirements or Colab). Wrap all ByteTrack calls so they can be swapped for another tracker easily.
8. **Frame pipeline latency** — keep end-to-end WebSocket frame latency under 200ms. If inference is slow, drop frames (process every Nth frame, configurable via env var `INFERENCE_STRIDE=2`).
9. **Comments** — leave `# TODO: fine-tune` and `# HACKATHON: simplify` comments where shortcuts are taken.
10. **Secrets** — all API keys (OpenAI, etc.) via environment variables. Never hardcode. Provide a `.env.example` file.

---

## 📦 DEPENDENCIES

### `cv_backend/requirements.txt`
```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
ultralytics>=8.2.0
mediapipe>=0.10.14
opencv-python-headless>=4.9.0
numpy>=1.26.0
Pillow>=10.3.0
openai>=1.30.0
python-dotenv>=1.0.0
websockets>=12.0
pydantic>=2.7.0
lap>=0.4.0           # required by ByteTrack
torch>=2.3.0
torchvision>=0.18.0
# ByteTrack: install from source - see README
```

### `flutter_app/pubspec.yaml` additions
```yaml
dependencies:
  flutter_riverpod: ^2.5.1
  riverpod_annotation: ^2.3.5
  http: ^1.2.1
  web_socket_channel: ^3.0.0
  fl_chart: ^0.68.0         # sparkline charts for vitals
  camera: ^0.11.0           # camera access for CV stream
  permission_handler: ^11.3.1
  intl: ^0.19.0
```

---

## 🚀 GETTING STARTED (README scaffold)

```
1. Clone repo
2. cd cv_backend && cp .env.example .env && fill in OPENAI_API_KEY
3. pip install -r requirements.txt
4. git clone https://github.com/ifzhang/ByteTrack && pip install -e ByteTrack/
5. uvicorn main:app --reload --host 0.0.0.0 --port 8000
6. cd flutter_app && flutter pub get
7. Connect Samsung Galaxy Watch, ensure Health Connect app is installed on phone
8. flutter run
```

---

*This prompt is the single source of truth for Cursor. When generating any file, refer back to the schemas, class names, channel names, and rules defined here. When in doubt, scaffold and leave a TODO rather than guessing.*
