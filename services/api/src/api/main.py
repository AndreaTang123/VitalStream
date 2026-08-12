"""Layer 3 FastAPI backend entrypoint (PRD 3.3/4.5)."""

from __future__ import annotations

from fastapi import FastAPI

from api.routers import audit_logs, auth, config, features, insights, users

app = FastAPI(title="vitalstream-api")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(insights.router)
app.include_router(features.router)
app.include_router(config.router)
app.include_router(audit_logs.router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
