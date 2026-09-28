"""Business-level Prometheus metrics (week8 Step 1).

Deliberately separate from `prometheus-fastapi-instrumentator`'s generic
`http_request_duration_seconds` (added in main.py) — these two measure
things the generic HTTP histogram can't: time actually spent handing a
batch to Kafka (not the whole request), and raw sample throughput
independent of request count (one request can carry many samples).

No `device_id` (or any other per-device) label on anything here — with
thousands of simulated devices that's thousands of time series per bucket,
which is exactly the cardinality blowup that makes Prometheus fall over.
Device-level detail belongs in Postgres, not here.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

KAFKA_PRODUCE_SECONDS = Histogram(
    "kafka_produce_seconds", "Time to hand a signal batch to the Kafka producer"
)
INGEST_SAMPLES_TOTAL = Counter("ingest_samples_total", "Cumulative raw signal samples ingested")
