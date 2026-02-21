import time
import uuid

from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI

from schemas.incident_report import IncidentReport
from schemas.sensor_payload import ReportRequest

router = APIRouter(prefix="/report", tags=["report"])

client = AsyncOpenAI()  # reads OPENAI_API_KEY from environment


@router.post("/generate", response_model=IncidentReport)
async def generate_report(request: ReportRequest) -> IncidentReport:
    """
    Aggregates sensor + CV anomaly event data and generates a structured
    incident report using an LLM.
    # TODO: fine-tune the prompt once we have real data patterns
    """
    anomaly = request.anomaly_event
    sensor = request.sensor_snapshot

    # TODO: fine-tune — expand system prompt with domain knowledge
    system_prompt = (
        "You are a medical triage assistant analyzing wearable sensor data and "
        "computer-vision anomaly events. Respond ONLY with the requested fields, "
        "no extra commentary."
    )

    # TODO: fine-tune — add more biometric context, historical baselines
    user_prompt = (
        f"Anomaly detected: {anomaly.type}.\n"
        f"Confidence: {anomaly.confidence:.0%}.\n"
        f"Duration: {anomaly.duration_seconds or 'unknown'} seconds.\n"
        f"Biometrics at time of event:\n"
        f"  Heart rate: {sensor.heart_rate} bpm\n"
        f"  SpO2: {sensor.spo2}%\n"
        f"  Skin temperature: {sensor.skin_temperature}°C\n"
        f"  Step count: {sensor.step_count}\n"
        f"Location context: {request.location_context or 'unknown'}.\n\n"
        "Generate a structured incident report with these exact fields:\n"
        "severity (LOW/MODERATE/HIGH/CRITICAL), summary (2-3 sentences), "
        "vitals_assessment, cv_assessment, recommended_action."
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,  # TODO: fine-tune — lower for more deterministic triage
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        llm_text = response.choices[0].message.content or ""
    except Exception as exc:
        # HACKATHON: simplify — fall back to a canned report rather than failing hard
        llm_text = ""

    parsed = _parse_llm_response(llm_text, request)

    return IncidentReport(
        report_id=str(uuid.uuid4()),
        generated_at=int(time.time() * 1000),
        severity=parsed["severity"],
        summary=parsed["summary"],
        vitals_assessment=parsed["vitals_assessment"],
        cv_assessment=parsed["cv_assessment"],
        recommended_action=parsed["recommended_action"],
        raw_sensor=sensor,
        raw_anomaly=anomaly,
    )


def _parse_llm_response(text: str, request: ReportRequest) -> dict:
    """
    Best-effort parser for the LLM output.
    # HACKATHON: simplify — switch to structured outputs / function-calling post-hackathon
    """
    fields = {
        "severity": "MODERATE",
        "summary": "Anomaly detected. Manual review recommended.",
        "vitals_assessment": "Sensor data collected.",
        "cv_assessment": f"CV detected {request.anomaly_event.type} event.",
        "recommended_action": "Check on individual.",
    }

    for line in text.splitlines():
        line = line.strip()
        for key in fields:
            prefix = f"{key}:"
            if line.lower().startswith(prefix.lower()):
                fields[key] = line[len(prefix):].strip()

    return fields
