"""Layer 3 FastAPI backend entrypoint (PRD 3.3/4.5)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

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

# week8 Step 1: /metrics is deliberately unauthenticated (Prometheus scrapes
# it directly, with no bearer token) — it's read-only, aggregate-only
# (no per-user data, see api/metrics.py's docstring), and CORS still applies.
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

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
