"""Layer 2 insight service entrypoint (PRD 3.2/4.5): POST /api/v1/insights/generate.

Persisting the resulting Insight (PRD 4.4) is the api service's job — it calls
this endpoint, then writes the returned content + model_version + eval_score
into Postgres alongside the audit log entry for who triggered the generation.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from insight_service.cache import cache_key, get_cached_insight, set_cached_insight
from insight_service.llm_client import llm_client
from insight_service.settings import settings

app = FastAPI(title="vitalstream-insight-service")


class GenerateInsightIn(BaseModel):
    user_id: str
    features: dict[str, float]
    model_version: str | None = None
    prompt_version: str | None = None


class GenerateInsightOut(BaseModel):
    content: str
    model_version: str
    prompt_version: str
    cached: bool


@app.post("/api/v1/insights/generate", response_model=GenerateInsightOut)
async def generate_insight(body: GenerateInsightIn) -> GenerateInsightOut:
    model_version = body.model_version or settings.llm_model_name
    prompt_version = body.prompt_version or settings.prompt_version
    key = cache_key(body.user_id, body.features, model_version, prompt_version)

    cached_content = await get_cached_insight(key)
    if cached_content is not None:
        return GenerateInsightOut(
            content=cached_content,
            model_version=model_version,
            prompt_version=prompt_version,
            cached=True,
        )

    response = await llm_client.generate_insight(body.features, model_version, prompt_version)
    await set_cached_insight(key, response.content)
    return GenerateInsightOut(
        content=response.content,
        model_version=response.model_version,
        prompt_version=response.prompt_version,
        cached=False,
    )


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
