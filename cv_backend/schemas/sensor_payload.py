from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SensorSnapshot(BaseModel):
    heart_rate: Optional[float] = None        # bpm
    spo2: Optional[float] = None              # %
    step_count: Optional[int] = None
    skin_temperature: Optional[float] = None  # °C
    timestamp: int                            # epoch ms


class AnomalyEvent(BaseModel):
    type: str                                 # FALL | COLLAPSE | ERRATIC_MOTION | STATIONARY_DOWN
    confidence: float
    track_id: int
    timestamp: int                            # epoch ms
    duration_seconds: Optional[float] = None
    frame_snapshot_b64: Optional[str] = None  # base64 JPEG thumbnail


class ReportRequest(BaseModel):
    anomaly_event: AnomalyEvent
    sensor_snapshot: SensorSnapshot
    location_context: Optional[str] = None   # e.g. "home", "gym", "outdoor"
    user_profile: Optional[dict] = None      # age, known conditions — stub for now
