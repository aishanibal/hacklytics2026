"""
Send "Here is your report" email to the address collected from the dashboard.
Set SMTP values directly below.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

router = APIRouter(tags=["email-report"])

# Set these directly (e.g. Gmail: smtp.gmail.com, port 587, app password)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "anika.khatriprof@gmail.com"
SMTP_PASSWORD = "svas yuls ijsi uwrl"
FROM_EMAIL = "vigil@localhost"

SUBJECT = "Vigil deactivation report"
BODY = "Here is your report."


class SendReportRequest(BaseModel):
    email: EmailStr


def _send_email(to_email: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = SUBJECT
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg.attach(MIMEText(BODY, "plain"))

    if not SMTP_HOST or not SMTP_USER:
        raise HTTPException(
            status_code=503,
            detail="Email not configured. Edit SMTP_HOST, SMTP_USER, SMTP_PASSWORD in email_report.py.",
        )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        if SMTP_PASSWORD:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(FROM_EMAIL, [to_email], msg.as_string())


@router.post("/report/send-email")
async def send_report_email(request: SendReportRequest) -> dict:
    """
    Send an email to the given address with the message "Here is your report."
    Called from the dashboard when the user submits the deactivation report modal.
    """
    try:
        _send_email(request.email)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email: {e}")
    return {"status": "sent", "to": request.email}
