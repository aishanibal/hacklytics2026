import os
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import stream, report

app = FastAPI(title="Health Anomaly Detection API", version="0.1.0")

# HACKATHON: wide-open CORS — lock this down post-hackathon
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stream.router)
app.include_router(report.router)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}
