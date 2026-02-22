import os

from dotenv import load_dotenv

load_dotenv()  # load .env from cv_backend/ (or current working directory)

# So Gemini key is definitely loaded before ai_config is imported
_google_key = os.getenv("GOOGLE_API_KEY", "").strip()
if _google_key and _google_key != "your-gemini-api-key":
    print("[env] GOOGLE_API_KEY loaded (Gemini endpoints will work)")
else:
    print("[env] GOOGLE_API_KEY not set — set it in cv_backend/.env with no spaces: GOOGLE_API_KEY=your-key")

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import pose_stream, report, email_report

app = FastAPI(title="Health Anomaly Detection API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pose_stream.router)
app.include_router(report.router)
app.include_router(email_report.router)

try:
    from routers import ai_config
    app.include_router(ai_config.router)
except Exception:
    pass

try:
    from routers import stream
    app.include_router(stream.router)
except Exception:
    pass


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}
