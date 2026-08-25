"""LLM client for personalized insight generation (PRD 3.2).

Prompt templates are versioned in `PROMPT_TEMPLATES` so the A/B testing story
(PRD 3.2/6.2) is: pick a `prompt_version`, generate against the benchmark set,
compare eval scores/latency/cost across versions.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from openai import AsyncOpenAI

from insight_service.settings import settings

logger = logging.getLogger(__name__)

PROMPT_TEMPLATES: dict[str, str] = {
    "v1": (
        "You are a wellness assistant. Given these wearable-derived features: "
        "{features}. Write one short, encouraging, non-diagnostic lifestyle tip. "
        "Ground every claim in the feature values given — do not invent numbers."
    ),
}


def describe_snapshot(feature_snapshot: dict) -> str:
    """Turn an aggregated heart-rate snapshot (feature_extraction.insight_throttle
    .aggregate_snapshot's output) into a sentence, rather than handing the LLM
    a raw dict — week4-layer2-milestone-guide.md Step 5's example: "过去 X
    分钟静息心率均值 72 bpm，较上一时段上升 5 bpm"."""
    mean = feature_snapshot.get("heart_rate_mean")
    trend = feature_snapshot.get("heart_rate_trend")
    windows = feature_snapshot.get("window_count")
    if mean is None:
        return str(feature_snapshot)  # unrecognized shape — fall back rather than crash

    direction = "up" if (trend or 0) > 0 else "down" if (trend or 0) < 0 else "flat, unchanged"
    trend_phrase = (
        f"trending {direction} {abs(trend):.1f} bpm from the start of that period"
        if trend
        else "holding steady"
    )
    return f"Over the last {int(windows)} monitoring windows, average heart rate was {mean:.1f} bpm, {trend_phrase}."


@dataclass
class LLMResponse:
    content: str
    model_version: str
    prompt_version: str
    latency_ms: float
    cost_usd: float


class LLMClient:
    def __init__(self) -> None:
        # AsyncOpenAI raises at construction time (not call time) if api_key
        # is falsy, which would crash importing this module in any dev/test
        # environment without OPENAI_API_KEY set — a placeholder here just
        # defers that failure to the first real API call, where it belongs.
        # max_retries=0: _call_with_retry already retries once at this
        # layer — leaving the SDK's own default retry-with-backoff on top
        # would silently multiply every failure into several HTTP calls
        # (observed live: a single quota error fanned out into 6 requests).
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key or "not-set",
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )

    async def _call_with_retry(self, model: str, prompt: str) -> tuple[str, float]:
        """One retry on failure (week4-layer2-milestone-guide.md Step 5) — a
        transient timeout/rate-limit shouldn't skip an insight outright, but
        this consumer also shouldn't hang on a full retry queue this week.
        Raises on a second failure; callers decide whether to log-and-skip."""
        last_exc: Exception | None = None
        for attempt in range(2):
            start = time.monotonic()
            try:
                response = await self._client.chat.completions.create(
                    model=model, messages=[{"role": "user", "content": prompt}]
                )
                latency_ms = (time.monotonic() - start) * 1000
                return response.choices[0].message.content or "", latency_ms
            except Exception as exc:  # noqa: BLE001 - deliberately broad: any failure gets one retry
                last_exc = exc
                logger.warning("LLM call failed (attempt %d/2): %s", attempt + 1, exc)
        assert last_exc is not None
        raise last_exc

    async def generate_insight(
        self, features: dict, model_version: str | None = None, prompt_version: str | None = None
    ) -> LLMResponse:
        model_version = model_version or settings.llm_model_name
        prompt_version = prompt_version or settings.prompt_version
        template = PROMPT_TEMPLATES[prompt_version]
        prompt = template.format(features=features)

        content, latency_ms = await self._call_with_retry(model_version, prompt)
        return LLMResponse(
            content=content,
            model_version=model_version,
            prompt_version=prompt_version,
            latency_ms=latency_ms,
            cost_usd=0.0,  # TODO: response.usage * the model's per-token pricing
        )

    async def generate_device_insight(
        self, feature_snapshot: dict, prompt_version: str | None = None, model_version: str | None = None
    ) -> LLMResponse:
        """The autonomous device-insight pipeline's entrypoint
        (week4-layer2-milestone-guide.md Step 5) — same underlying call as
        generate_insight, but the prompt is built from a natural-language
        description of the snapshot rather than a raw features dict."""
        model_version = model_version or settings.llm_model_name
        prompt_version = prompt_version or settings.prompt_version
        template = PROMPT_TEMPLATES[prompt_version]
        prompt = template.format(features=describe_snapshot(feature_snapshot))

        content, latency_ms = await self._call_with_retry(model_version, prompt)
        return LLMResponse(
            content=content,
            model_version=model_version,
            prompt_version=prompt_version,
            latency_ms=latency_ms,
            cost_usd=0.0,
        )


llm_client = LLMClient()
