"""
Gemini: takes sensor data + pose/training data and returns JSON for easier alerts.
Work in progress — to be wired to pose/report pipeline.
"""

import json
import re

import google.generativeai as genai
from pydantic import BaseModel, Field

# Configure Gemini — set your API key directly or use env GOOGLE_API_KEY
GEMINI_API_KEY = "your-gemini-api-key"  # or os.getenv("GOOGLE_API_KEY", "your-gemini-api-key")
genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-1.5-flash"  # or gemini-1.5-pro for heavier reasoning

# Expected JSON shape from Gemini
SYSTEM_INSTRUCTION = """You take sensor data and pose/training data as input. Your job is to output valid JSON only (no markdown or extra text) that makes it easier to trigger and prioritize alerts.

Output format (use exactly these keys):
{
  "high_alert": true or false,
  "alert_level": "NORMAL" | "LOW" | "MODERATE" | "HIGH" | "CRITICAL",
  "person_id": "optional identifier or 'unknown'",
  "symptoms": ["symptom1", "symptom2", ...],
  "summary": "One or two sentences summarizing what the sensor and pose data suggest (e.g. patterns, anomalies) so alerts can be raised or dismissed."
}

Rules:
- Base your output only on the sensor and pose data provided. You are not giving medical advice; you are structuring that data into a consistent JSON format for alerting.
- high_alert: true when the combined sensor + pose data suggest an alert should be raised; false otherwise.
- symptoms: list of observable patterns or signs derived from the data (e.g. "elevated heart rate", "posture collapse", "prolonged swaying").
- If nothing concerning in the data, use high_alert: false, alert_level: "NORMAL", symptoms: [].
- Respond with nothing but the JSON object."""

USER_PROMPT_TEMPLATE = """Sensor data and pose/training data:

Context:
{context}

Sensor + pose data:
{observations}

Produce the JSON object (high_alert, alert_level, person_id, symptoms, summary) from this data only."""


class GeminiAlertResponse(BaseModel):
    """Structured JSON from Gemini for alerts (from sensor + pose data)."""
    high_alert: bool = Field(description="True when data suggests an alert should be raised")
    alert_level: str = Field(description="NORMAL | LOW | MODERATE | HIGH | CRITICAL")
    person_id: str = Field(default="unknown", description="Identifier for the person")
    symptoms: list[str] = Field(default_factory=list, description="Patterns/signs from the data (e.g. posture collapse, swaying)")
    summary: str = Field(default="", description="Short summary from sensor + pose data for alerting")


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of the model response (handles markdown code blocks)."""
    text = text.strip()
    # Remove optional markdown code block
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


def get_medical_alert_json(context: str, observations: str) -> GeminiAlertResponse:
    """
    Call Gemini with sensor + pose data; returns structured JSON for alerts.
    WIP: Wire to pose stream / report — pass context and observations (sensor + pose/training data).
    """
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    prompt = USER_PROMPT_TEMPLATE.format(context=context, observations=observations)
    response = model.generate_content(prompt)
    raw = response.text
    data = _extract_json(raw)
    return GeminiAlertResponse(
        high_alert=data.get("high_alert", False),
        alert_level=data.get("alert_level", "NORMAL"),
        person_id=data.get("person_id", "unknown"),
        symptoms=data.get("symptoms") or [],
        summary=data.get("summary", ""),
    )


# ─── Latest alert store (for Flutter to poll) ───

import time

_latest_alert: dict | None = None
_latest_alert_at: float = 0.0


def _store_latest_alert(resp: GeminiAlertResponse) -> None:
    global _latest_alert, _latest_alert_at
    _latest_alert = resp.model_dump()
    _latest_alert_at = time.time()


# ─── FastAPI router: generate alert + endpoint for Flutter ───

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/ai", tags=["ai-config"])


class AlertRequest(BaseModel):
    context: str = "Single person tracked via BLE; sensor and pose data."
    observations: str = ""


@router.post("/medical-alert", response_model=GeminiAlertResponse)
async def post_medical_alert(request: AlertRequest) -> GeminiAlertResponse:
    """
    Send sensor + pose data to Gemini; returns JSON and stores it as latest alert for Flutter.
    """
    if not request.observations.strip():
        raise HTTPException(400, detail="observations cannot be empty")
    try:
        resp = get_medical_alert_json(
            context=request.context,
            observations=request.observations,
        )
        _store_latest_alert(resp)
        return resp
    except Exception as e:
        raise HTTPException(502, detail=f"Gemini call failed: {e}")


@router.get("/alert/latest")
async def get_alert_latest() -> dict:
    """
    Returns the latest alert JSON for Flutter to poll. When high_alert is true,
    Flutter can show an on-phone alert/notification.
    """
    if _latest_alert is None:
        return {
            "high_alert": False,
            "alert_level": "NORMAL",
            "person_id": "unknown",
            "symptoms": [],
            "summary": "",
            "updated_at": None,
        }
    out = dict(_latest_alert)
    out["updated_at"] = _latest_alert_at
    return out
