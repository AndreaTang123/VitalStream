"""Business-level Prometheus metrics for the autonomous consumer (week8
Step 1) — exposed on their own HTTP server (`prometheus_client.
start_http_server`), same pattern as feature_extraction, since this is a
Kafka consumer loop with no FastAPI app of its own.

Deliberately scoped to `consumer.py` only, not `main.py`'s on-demand
endpoint — the autonomous pipeline is the one PRD 8's cache-savings metric
and Grafana's "AI" row are actually about; see README "Results" for why
that distinction (fleet-scale cache hit rate) matters.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

INSIGHT_CACHE_HITS_TOTAL = Counter("insight_cache_hits_total", "Autonomous insight cache hits")
INSIGHT_CACHE_MISSES_TOTAL = Counter("insight_cache_misses_total", "Autonomous insight cache misses")
LLM_REQUEST_SECONDS = Histogram("llm_request_seconds", "LLM call latency on a cache miss")
# Labeled by model + prompt_version (both small, fixed-cardinality sets —
# unlike device_id/user_id, safe to label with) so a prompt A/B's cost
# delta (README "Results": v1 $0.000052/call vs v2 $0.000073/call) is
# directly queryable, not just knowable from the offline eval report.
LLM_COST_USD_TOTAL = Counter(
    "llm_cost_usd_total", "Cumulative real LLM spend", ["model", "prompt_version"]
)
