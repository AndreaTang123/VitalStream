"""Layer 3 FastAPI backend entrypoint (PRD 3.3/4.5)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import audit_logs, auth, coach, config, devices, features, insights, users
from api.settings import settings

app = FastAPI(title="vitalstream-api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(insights.router)
app.include_router(features.router)
app.include_router(devices.router)
app.include_router(coach.router)
app.include_router(config.router)
app.include_router(audit_logs.router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
