"""LLM client for personalized insight generation (PRD 3.2).

Prompt templates are versioned in `PROMPT_TEMPLATES` so the A/B testing story
(PRD 3.2/6.2) is: pick a `prompt_version`, generate against the benchmark set,
compare eval scores/latency/cost across versions.
"""

from __future__ import annotations

from dataclasses import dataclass

from openai import AsyncOpenAI

from insight_service.settings import settings

PROMPT_TEMPLATES: dict[str, str] = {
    "v1": (
        "You are a wellness assistant. Given these wearable-derived features: "
        "{features}. Write one short, encouraging, non-diagnostic lifestyle tip. "
        "Ground every claim in the feature values given — do not invent numbers."
    ),
}


@dataclass
class LLMResponse:
    content: str
    model_version: str
    prompt_version: str
    latency_ms: float
    cost_usd: float


class LLMClient:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate_insight(
        self, features: dict, model_version: str | None = None, prompt_version: str | None = None
    ) -> LLMResponse:
        model_version = model_version or settings.llm_model_name
        prompt_version = prompt_version or settings.prompt_version
        template = PROMPT_TEMPLATES[prompt_version]
        prompt = template.format(features=features)

        response = await self._client.chat.completions.create(
            model=model_version,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content or ""

        # TODO: derive latency_ms from a wall-clock timer around the call, and
        # cost_usd from response.usage + the model's per-token pricing.
        return LLMResponse(
            content=content,
            model_version=model_version,
            prompt_version=prompt_version,
            latency_ms=0.0,
            cost_usd=0.0,
        )


llm_client = LLMClient()
