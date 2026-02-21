# Health & Anomaly Detection Platform — Hacklytics 2026

Real-time health monitoring and anomaly detection using wearable sensors and computer vision.

---

## Architecture

```
Samsung Galaxy Watch
       │ (Health Connect / BLE)
       ▼
Android (Kotlin)  ←──────────────────────────────────┐
  SamsungHealthPlugin.kt                               │
  WatchDataManager.kt                                  │ Platform Channel
       │                                               │
       ▼                                               │
Flutter App  ──── WebSocket ────►  FastAPI CV Backend  │
  Dashboard                         YOLOv8 + ByteTrack │
  Camera feed overlay               MediaPipe Pose     │
  Incident Report                   Anomaly Classifier │
                                    GenAI Report (GPT) │
```

## Project Structure

```
├── flutter_app/               # Flutter frontend (Riverpod, fl_chart)
│   ├── lib/
│   │   ├── main.dart
│   │   ├── screens/
│   │   │   ├── dashboard_screen.dart
│   │   │   ├── camera_screen.dart
│   │   │   └── report_screen.dart
│   │   ├── services/
│   │   │   ├── sensor_service.dart
│   │   │   ├── cv_service.dart
│   │   │   └── report_service.dart
│   │   ├── models/
│   │   │   ├── biometric_data.dart
│   │   │   └── incident_report.dart
│   │   └── widgets/
│   │       └── vital_card.dart
│   └── android/app/src/main/kotlin/com/yourapp/
│       ├── MainActivity.kt
│       ├── SamsungHealthPlugin.kt
│       └── WatchDataManager.kt
│
├── cv_backend/                # FastAPI computer vision server
│   ├── main.py
│   ├── routers/
│   │   ├── stream.py          # WebSocket /ws/stream + POST /analyze/frame
│   │   └── report.py          # POST /report/generate (GenAI)
│   ├── core/
│   │   ├── detector.py        # YOLOv8 person detection
│   │   ├── tracker.py         # ByteTrack multi-person tracking
│   │   ├── pose.py            # MediaPipe pose estimation
│   │   └── anomaly.py         # Fall / collapse / erratic motion rules
│   ├── schemas/
│   │   ├── sensor_payload.py
│   │   └── incident_report.py
│   ├── requirements.txt
│   └── Dockerfile
│
└── notebooks/                 # Google Colab prototyping
    ├── cv_pipeline_prototype.ipynb
    └── genai_report_prototype.ipynb
```

---

## Getting Started

### 1. CV Backend

```bash
cd cv_backend
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY

pip install -r requirements.txt

# Install ByteTrack from source
git clone https://github.com/ifzhang/ByteTrack
pip install -e ByteTrack/

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Test the health endpoint:
```bash
curl http://localhost:8000/health
```

### 2. Flutter App

```bash
cd flutter_app
flutter pub get
flutter run
```

Before running, update the backend URL in:
- `lib/services/cv_service.dart` → `_wsBaseUrl`
- `lib/services/report_service.dart` → `_baseUrl`

### 3. Samsung Galaxy Watch Setup

1. Install the **Health Connect** app on the Android phone.
2. Open Health Connect → grant permissions for Heart Rate, SpO2, Steps, Skin Temperature.
3. Ensure your Galaxy Watch is paired and syncing to Health Connect.

---

## Environment Variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key for incident report generation |
| `INFERENCE_STRIDE` | Process every Nth frame (default: `2`) |

---

## Notes

- Model weights (`*.pt`) are auto-downloaded by Ultralytics and cached in `cv_backend/models/` (gitignored).
- All API keys must be set via environment variables — never hardcoded.
- The platform channel prefix `com.yourapp/` must stay consistent across Kotlin and Dart.
