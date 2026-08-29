"""Static per-model token pricing (week5-layer2-deepening-guide.md Step 1/6).

Cost is computed from OpenAI's real `usage.prompt_tokens`/`completion_tokens`
on every call — this table is the only "made up" number in that
computation, and it's a published list price snapshot, not a guess. Update
it when OpenAI changes pricing; nothing else in the codebase re-derives a
rate, so this is the single place that can go stale.

USD per 1,000 tokens, as of OpenAI's published pricing in 2025.
"""

from __future__ import annotations

PRICING_USD_PER_1K: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input_per_1k": 0.00015, "output_per_1k": 0.00060},
    "gpt-4o": {"input_per_1k": 0.00250, "output_per_1k": 0.01000},
}

# Used only if a model isn't in the table above (e.g. mistyped/new model
# name) — gpt-4o-mini's rate, so an unrecognized model under-costs rather
# than silently returning $0 and hiding a real generation cost.
_FALLBACK_PRICE = PRICING_USD_PER_1K["gpt-4o-mini"]


def calculate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price = PRICING_USD_PER_1K.get(model, _FALLBACK_PRICE)
    return (prompt_tokens / 1000) * price["input_per_1k"] + (completion_tokens / 1000) * price["output_per_1k"]
