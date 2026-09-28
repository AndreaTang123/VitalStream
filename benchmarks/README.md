# Load testing — methodology, defined before the numbers (week8)

Written and committed *before* `loadtest/run_steps.sh` ran — the SLO
thresholds and metric definitions below are what the run was judged
against, not picked afterward to make a chart look better. See
[week8_load_test_results.md](week8_load_test_results.md) for the actual
numbers this methodology produced.

## Definitions

**Concurrent device**: one simulated device posting one `SignalBatch` of 64
samples (1 second of 64Hz PPG) per second — matches Week 1-2's simulator
pacing exactly. **N devices = N req/s = 64N samples/s.** Any "supports N
devices" claim implies this rate; a device posting less often is a
different, larger number.

**Stable at a given device count** means, for the whole test duration:
- ingestion HTTP P99 < 200ms
- error rate < 1%
- Kafka consumer lag (`consumer_lag_messages`) does not trend upward —
  HTTP staying fast while `feature_extraction` quietly falls behind is a
  system that's "stable" by the first two bullets and not actually stable.
- pipeline end-to-end P99 (defined below) stays under a few seconds

**Pipeline end-to-end latency** is *not* what k6 measures (k6 only sees
"device → ingestion → 202", which never touches Kafka or feature
extraction). Defined as: the timestamp `ingestion.kafka_producer` stamps
into the outgoing Kafka message's `ingest_ts` header, to the moment the
resulting feature row is written to Postgres. Recorded using the **most
recent** batch's `ingest_ts` at the moment a window closes — the 8-second
window's own accumulation time is a designed latency (PRD's windowing
choice), not a system bottleneck, and is deliberately excluded. See
`feature_extraction/metrics.py` and `main.py`'s `_emit_window`.

## Environment (this run)

| | |
|---|---|
| Machine | Single MacBook (Apple Silicon, arm64) |
| CPU / RAM available to Docker | 10 CPUs / 7.75 GiB (`docker info`) |
| OS | macOS |
| k6 vs system under test | **Same machine, running concurrently** — no separate load-generator host was available. This makes every number here a conservative floor, not a ceiling: k6 and the services it's hitting compete for the same CPUs. Called out explicitly rather than presented as a clean isolated measurement. |
| uvicorn | no `--reload`; `log_level=warning` (`ingestion/run.py`) — default `info` access-logging is itself measurable per-request overhead at load |
| Workers | 1 (single uvicorn worker per service; not swept — see Limitations) |
| Warm-up | first ~10s of each run's traffic is ramp-up inside k6's own `constant-arrival-rate`, not pre-excluded separately |
| Repeats | every tier ran once — a real limitation, not a 3x-median methodology; see [week8_load_test_results.md](week8_load_test_results.md) §1 for the honest caveat this implies on the 1000-device row specifically |
| LLM | `LLM_MODE=mock` (`docker-compose.loadtest.yml`) — a load test must not depend on OpenAI's latency/availability, and must not cost real money at 500-1000 simulated devices each triggering throttled insight requests. No number in this report is an LLM-quality number; those are 100% Week 5's real-OpenAI runs (`week5_eval_report.md`), never re-measured against the mock. |

## Reproducing

```bash
services/device_simulator/.venv/bin/python loadtest/prepare_payloads.py       # real PPG-DaLiA chunks
services/api/.venv/bin/python -m scripts.seed --load-devices 1000             # register load-test devices
docker compose -f docker-compose.yml -f docker-compose.loadtest.yml up -d     # LLM_MODE=mock
DEVICE_TIERS="25 50 100 250 500 1000" DURATION=60s SERVICE_TOKEN=<from .env> ./loadtest/run_steps.sh
```

Grafana (`localhost:3001`) during the run shows exactly what each tier did
to consumer lag / pipeline E2E latency / error rate — see README
"Observability" for panel-by-panel meaning.
