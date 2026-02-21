from __future__ import annotations

from pydantic import BaseModel

from schemas.sensor_payload import AnomalyEvent, SensorSnapshot


class IncidentReport(BaseModel):
    report_id: str                  # uuid
    generated_at: int               # epoch ms
    severity: str                   # LOW | MODERATE | HIGH | CRITICAL
    summary: str                    # 2-3 sentence plain-English summary
    vitals_assessment: str          # interpretation of sensor data
    cv_assessment: str              # what was visually detected
    recommended_action: str         # e.g. "Call emergency services"
    raw_sensor: SensorSnapshot
    raw_anomaly: AnomalyEvent
