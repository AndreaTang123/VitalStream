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

from insight_service.pricing import calculate_cost_usd
from insight_service.settings import settings

logger = logging.getLogger(__name__)

# Each version is a (system, user_template) pair rather than one flat string,
# so a version can tighten *system*-level constraints without changing how
# the per-request feature description is built.
#
# v2 exists because of a real finding, not the hypothesis this project
# started with (week5-layer2-deepening-guide.md Step 5 suggested v1 would
# drift into diagnostic language on extreme values — running the eval
# benchmark showed that DIDN'T happen: hallucination_rate was 0/22. What
# actually broke was groundedness — grounded_rate was 3/22, because v1 kept
# giving generic advice ("keep up the great work!") without ever restating
# the actual number it was given. v2's system prompt targets that specific,
# measured problem — see benchmarks/week5_eval_report.md for the full
# before/after comparison.
PROMPT_TEMPLATES: dict[str, dict[str, str]] = {
    "v1": {
        "system": (
            "You are a wellness assistant. Write one short, encouraging, "
            "non-diagnostic lifestyle tip. Ground every claim in the feature "
            "values given — do not invent numbers."
        ),
        "user_template": "Wearable-derived features: {features}",
    },
    "v2": {
        "system": (
            "You are a wellness assistant. Write one short, encouraging, non-diagnostic "
            "lifestyle tip based on the wearable data provided. "
            "You MUST explicitly restate at least one specific number from the data "
            "in your response (e.g. the exact bpm or ms value and its trend) — do not "
            "give purely generic advice with no reference to the actual reading. "
            "Ground every claim in the feature values given — do not invent numbers. "
            "Never use diagnostic or medical-emergency language (e.g. 'diagnosis', "
            "'arrhythmia', 'heart condition', 'seek immediate medical attention') — "
            "this is lifestyle guidance only, not medical advice."
        ),
        "user_template": "Wearable-derived features: {features}",
    },
}


# {snapshot_key_prefix: (human label, unit)} — feature_extraction's live
# pipeline only ever produces heart_rate_* today (week1-2), but the eval
# benchmark (week5-layer2-deepening-guide.md Step 2) wants an HRV category
# too, and this only needs to *describe* a snapshot, not compute one — so it
# generalizes to any metric shaped like "{prefix}_mean"/"{prefix}_trend"
# rather than staying hardcoded to heart rate. Real today for heart_rate;
# ready-but-unused for hrv_rmssd until feature_extraction actually emits it.
_METRIC_LABELS: dict[str, str] = {
    "heart_rate": "heart rate (bpm)",
    "hrv_rmssd": "heart rate variability / RMSSD (ms)",
}


def describe_snapshot(feature_snapshot: dict) -> str:
    """Turn an aggregated snapshot (feature_extraction.insight_throttle
    .aggregate_snapshot's output) into a sentence, rather than handing the LLM
    a raw dict — week4-layer2-milestone-guide.md Step 5's example: "过去 X
    分钟静息心率均值 72 bpm，较上一时段上升 5 bpm"."""
    windows = feature_snapshot.get("window_count")
    sentences = []
    for prefix, label in _METRIC_LABELS.items():
        mean = feature_snapshot.get(f"{prefix}_mean")
        if mean is None:
            continue
        trend = feature_snapshot.get(f"{prefix}_trend")
        direction = "up" if (trend or 0) > 0 else "down" if (trend or 0) < 0 else "flat, unchanged"
        trend_phrase = (
            f"trending {direction} {abs(trend):.1f} from the start of that period"
            if trend
            else "holding steady"
        )
        sentences.append(f"average {label} was {mean:.1f}, {trend_phrase}")

    if not sentences or windows is None:
        return str(feature_snapshot)  # unrecognized shape — fall back rather than crash

    return f"Over the last {int(windows)} monitoring windows, " + "; ".join(sentences) + "."


@dataclass
class LLMResponse:
    content: str
    model_version: str
    prompt_version: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
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

    async def _call_with_retry(
        self, model: str, system: str, user_content: str
    ) -> tuple[str, float, int, int]:
        """One retry on failure (week4-layer2-milestone-guide.md Step 5) — a
        transient timeout/rate-limit shouldn't skip an insight outright, but
        this consumer also shouldn't hang on a full retry queue this week.
        Raises on a second failure; callers decide whether to log-and-skip.
        Returns (content, latency_ms, prompt_tokens, completion_tokens) —
        token counts come from OpenAI's real `usage`, not an estimate
        (week5-layer2-deepening-guide.md Step 1/6)."""
        last_exc: Exception | None = None
        for attempt in range(2):
            start = time.monotonic()
            try:
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_content},
                    ],
                )
                latency_ms = (time.monotonic() - start) * 1000
                content = response.choices[0].message.content or ""
                usage = response.usage
                prompt_tokens = usage.prompt_tokens if usage else 0
                completion_tokens = usage.completion_tokens if usage else 0
                return content, latency_ms, prompt_tokens, completion_tokens
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
        user_content = template["user_template"].format(features=features)

        content, latency_ms, prompt_tokens, completion_tokens = await self._call_with_retry(
            model_version, template["system"], user_content
        )
        return LLMResponse(
            content=content,
            model_version=model_version,
            prompt_version=prompt_version,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=calculate_cost_usd(model_version, prompt_tokens, completion_tokens),
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
        user_content = template["user_template"].format(features=describe_snapshot(feature_snapshot))

        content, latency_ms, prompt_tokens, completion_tokens = await self._call_with_retry(
            model_version, template["system"], user_content
        )
        return LLMResponse(
            content=content,
            model_version=model_version,
            prompt_version=prompt_version,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=calculate_cost_usd(model_version, prompt_tokens, completion_tokens),
        )


llm_client = LLMClient()
