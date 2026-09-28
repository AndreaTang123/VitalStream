"""Business-level Prometheus metrics (week8 Step 1).

feature_extraction has no HTTP server of its own (it's a Kafka consumer
loop), so these are exposed on a standalone metrics HTTP server
(`prometheus_client.start_http_server`) rather than piggybacking on a
FastAPI app the way ingestion/api do — see `main.py`'s `start()`.

`PIPELINE_E2E_SECONDS` is the metric the whole "define end-to-end latency
honestly" decision in the week8 guide hinges on: ingest_ts -> Kafka header
(written by `ingestion.kafka_producer`) -> read back here -> subtracted
from "now" at the moment the resulting feature row is actually written to
Postgres. The 8-second window's own accumulation time is NOT part of this
number (that's an intentional design latency, not a bug) — see main.py's
`_emit_window` for exactly where this is recorded.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

FEATURE_WINDOWS_TOTAL = Counter(
    "feature_windows_total", "Feature windows successfully computed", ["algo_version"]
)
FEATURE_COMPUTE_SECONDS = Histogram(
    "feature_compute_seconds", "Bandpass filter + peak detection compute time per window"
)
PIPELINE_E2E_SECONDS = Histogram(
    "pipeline_e2e_seconds",
    "ingest_ts (ingestion receipt) -> feature row written to Postgres",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
CONSUMER_LAG_MESSAGES = Gauge(
    "consumer_lag_messages", "Kafka consumer lag (highwater - position)", ["partition"]
)
