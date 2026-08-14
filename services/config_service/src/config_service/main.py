"""Layer 1 config management service (PRD 3.1/4.2/4.5): validate -> gray release -> rollback.

Endpoints below extend the PRD's API sketch with the operations feature_extraction
actually needs (an `/active` lookup) and the ones a config-service admin needs
(register the first stable version, promote a canary, roll one back). Backed
by Postgres (config_service.db) since Week 3 — state now survives a restart,
and every mutation is audited (config_service.store).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import create_async_engine

from config_service.settings import settings
from config_service.store import ConfigError, ConfigStore

config_store = ConfigStore(create_async_engine(settings.postgres_dsn))


@asynccontextmanager
async def lifespan(_: FastAPI):
    await config_store.start()
    yield
    await config_store.stop()


app = FastAPI(title="vitalstream-config-service", lifespan=lifespan)


class RegisterStableIn(BaseModel):
    algo_name: str
    version: str
    actor: str = "unknown"


class PublishCanaryIn(BaseModel):
    algo_name: str
    version: str
    rollout_pct: int = Field(ge=0, le=100)
    actor: str = "unknown"


class ActorIn(BaseModel):
    actor: str = "unknown"


@app.post("/api/v1/config/feature-algo/register-stable", status_code=201)
async def register_stable(body: RegisterStableIn):
    try:
        return await config_store.register_initial_stable(body.algo_name, body.version, body.actor)
    except ConfigError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/v1/config/feature-algo", status_code=201)
async def publish_canary(body: PublishCanaryIn):
    try:
        return await config_store.publish_canary(
            body.algo_name, body.version, body.rollout_pct, body.actor
        )
    except ConfigError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/v1/config/feature-algo/{algo_name}/promote")
async def promote_canary(algo_name: str, body: ActorIn = ActorIn()):
    try:
        return await config_store.promote_canary(algo_name, body.actor)
    except ConfigError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/v1/config/feature-algo/{algo_name}/{version}/rollback")
async def rollback(algo_name: str, version: str, body: ActorIn = ActorIn()):
    try:
        return await config_store.rollback(algo_name, version, body.actor)
    except ConfigError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/v1/config/feature-algo/{algo_name}/active")
async def get_active(algo_name: str):
    try:
        return await config_store.get_active(algo_name)
    except ConfigError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/config/feature-algo/{algo_name}/audit-log")
async def get_audit_log(algo_name: str):
    return await config_store.audit_log(algo_name)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
