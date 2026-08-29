# VitalStream

Distributed Wearable Health Insights Platform — a personal engineering project that
takes high-frequency wearable signals (heart rate, HRV, sleep, activity) from ingestion
through feature extraction, LLM-based health insight generation, and a role-aware
full-stack delivery layer.

See [docs/PRD.md](docs/PRD.md) for the full product requirements doc and
[docs/architecture.md](docs/architecture.md) for the system diagram.

## Architecture

```
device_simulator (replays WESAD/PPG-DaLiA)
      │  HTTP (asyncio)
      ▼
┌─────────────────┐      ┌───────────────────┐      ┌──────────────────────┐
│ ingestion        │ ──▶ │ Redpanda           │ ──▶ │ feature_extraction    │
│ (asyncio+uvloop) │      │ (Kafka protocol)   │      │ (NumPy/SciPy,         │
└─────────────────┘      └───────────────────┘      │  gray-release aware)  │
                                                       └──────────┬───────────┘
                                  ┌────────────────────┬──────────┴───────────┐
                                  ▼                    ▼ (throttled, aggregated snapshot)
                       ┌────────────────┐   ┌────────────────────┐
                       │ Postgres        │   │ Redpanda            │
                       │ features table  │   │ features-extracted  │
                       │ (TimescaleDB    │   │  topic              │
                       │  hypertable:    │   └──────────┬──────────┘
                       │  Week 8+)       │              ▼
                       └────────────────┘   ┌────────────────────┐
                                             │ insight_service     │
                                             │ .consumer (LLM,     │
                                             │  Redis cache) →     │
                                             │  device_insights    │
                                             └──────────┬──────────┘
                                                         │
                                       (separately: a logged-in user can also
                                        trigger .main's on-demand endpoint)
                                                         ▼
                                              ┌────────────────────┐
                                              │ api (FastAPI)       │
                                              │ JWT/OAuth2 + RBAC   │
                                              │ + audit log         │
                                              └──────────┬──────────┘
                                                         ▼
                                              ┌────────────────────┐
                                              │ frontend (Next.js)  │
                                              └────────────────────┘

config_service (FastAPI+Pydantic) controls feature_extraction algorithm versions
(validate → gray release → rollback) — feature_extraction falls back to a
default algo_version if config_service isn't running, so Layer 1 doesn't
depend on it being up.

Cross-cutting: OpenTelemetry (tracing), Prometheus + Grafana (metrics), Docker,
GitHub Actions (CI/CD).
```

## Repo layout

```
services/
  ingestion/           Layer 1 — asyncio + uvloop signal ingestion, produces to Redpanda
  feature_extraction/  Layer 1 — NumPy/SciPy windowed feature extraction, gray-release aware
  config_service/      Layer 1 — versioned config: validate / gray release / rollback
  device_simulator/    Replays a real WESAD/PPG-DaLiA subject against the ingestion API
  insight_service/     Layer 2 — LLM-based insight generation, caching, eval, A/B testing
  api/                 Layer 3 — FastAPI backend: auth (OAuth2/JWT), RBAC, audit log
libs/common/           Shared Pydantic schemas + telemetry helpers used across services
frontend/              Layer 3 — Next.js dashboard (patient/coach views)
infra/                 docker, prometheus, grafana, k6 load-test scripts, cloud VM bootstrap
data/                  Dataset download script + local data cache
docs/                  PRD and architecture docs
```

## Quick start

```bash
cp .env.example .env
docker compose up -d          # Kafka/Redis, Postgres, TimescaleDB, Prometheus, Grafana
make bootstrap                # create venvs and install each Python service in editable mode
make test                     # run all service test suites
```

Datasets (WESAD, PPG-DaLiA) are *not* fetched by the steps above — they're
only needed once a service actually replays them, so they're downloaded
directly on whichever machine runs `docker compose up`. On a fresh cloud VM,
[infra/cloud/bootstrap_vm.sh](infra/cloud/bootstrap_vm.sh) does the whole
thing (install Docker, clone this repo, `data/scripts/download_datasets.sh`,
`docker compose up -d`) in one shot. See [data/README.md](data/README.md).

Each service under `services/*` is an independently installable Python package
(`pip install -e .`) with its own `pyproject.toml` and `Dockerfile`, so it can run
standalone or as part of `docker compose`.

### Run the pipeline end-to-end (Layer 1 + Layer 2)

Once `docker compose up -d` and `make bootstrap` have run, and at least one
subject's data is under `data/raw/ppg_dalia/PPG_FieldStudy/` (see
[data/README.md](data/README.md)), run each of these in its own terminal.
`insight_service` needs a real `OPENAI_API_KEY` in `.env` to do anything
useful on a cache miss — without one it'll log-and-skip every generation
(Step 5's "调用失败时不要让整个consumer挂掉" applies to a missing key too).

```bash
services/config_service/.venv/bin/uvicorn config_service.main:app --app-dir services/config_service/src --port 8002
services/ingestion/.venv/bin/python -m ingestion.run
services/feature_extraction/.venv/bin/python -m feature_extraction.main
services/insight_service/.venv/bin/python -m insight_service.consumer
services/device_simulator/.venv/bin/python -m device_simulator.replay --subject S2
```

The simulator replays real wrist-PPG samples from PPG-DaLiA subject S2 as if
they were arriving live from a wearable (`--speed` controls playback speed;
default 20x). Within a couple of window-lengths you should see rows land in
Postgres:

```bash
docker exec vitalstream-postgres-1 psql -U vitalstream -d vitalstream \
  -c "SELECT device_id, feature_type, value, window_end FROM features ORDER BY window_end DESC LIMIT 10;"
```

To sanity-check the heart-rate algorithm itself against PPG-DaLiA's own
ground-truth labels (no live services needed):

```bash
services/feature_extraction/.venv/bin/python \
  services/feature_extraction/scripts/validate_ppg_dalia.py --subject S2 --plot
```

### Config management & gray release

`config_service` owns algorithm version state in Postgres (`algo_versions` +
`algo_version_audit` — every register/canary/promote/rollback call is
audited with an actor, action, and timestamp) and exposes it over HTTP.
`feature_extraction` polls `GET .../active` into an in-memory cache every 30s
(`CONFIG_REFRESH_INTERVAL_SECONDS` in `main.py`) rather than on every
message, and routes each *device* to a version by hashing its `device_id`
mod 100 against the canary's `rollout_pct` — so a given device stays on the
same version for the life of a rollout instead of flip-flopping per message.

```bash
# register the first stable version
curl -X POST localhost:8002/api/v1/config/feature-algo/register-stable \
  -d '{"algo_name":"heart_rate","version":"v1","actor":"you"}'

# gray-release a second version to 20% of devices
curl -X POST localhost:8002/api/v1/config/feature-algo \
  -d '{"algo_name":"heart_rate","version":"v2-naive-wideband","rollout_pct":20,"actor":"you"}'

# looks good? promote it to 100%
curl -X POST localhost:8002/api/v1/config/feature-algo/heart_rate/promote -d '{"actor":"you"}'

# looks bad? roll it back — works whether it's still a canary or already
# promoted to active (restores the previous version in the latter case)
curl -X POST localhost:8002/api/v1/config/feature-algo/heart_rate/v2-naive-wideband/rollback -d '{"actor":"you"}'

# who did what, when
curl localhost:8002/api/v1/config/feature-algo/heart_rate/audit-log
```

`features.HEART_RATE_ALGORITHMS` maps a version string to an actual
implementation — `v1` is the tuned algorithm, `v2-naive-wideband` is a real
(not synthetic) bad version: the pre-tuning parameters that scored ~37 bpm
MAE in `validate_ppg_dalia.py` before being fixed to ~8 bpm. Publishing it as
a canary and rolling it back is a genuine "ship a regression, catch it,
revert it" exercise, not a no-op toggle.

### Insights pipeline (Layer 2)

The PRD's second output path off of Layer 1: `feature_extraction` throttles
each device to at most one `InsightRequest` per `insight_throttle_seconds`
(default 60s), aggregating the last 5 windows into a snapshot
(`heart_rate_mean`/`heart_rate_trend`) rather than firing an LLM call per
8-second window — real products don't burn a token on every window, and
neither should this demo. Published to `features-extracted` (Kafka), never
by `insight_service` polling Postgres directly — same decoupling pattern as
Layer 1's `raw-signals` → `features` hop.

`insight_service.consumer` (distinct from `insight_service.main`'s
user-triggered, RBAC-gated `/insights/generate` HTTP endpoint — that one
persists to api's own `insights` table; this one is autonomous and owns its
own `device_insights` table) does, per request: normalize the snapshot to a
Redis cache key (rounded to 2 decimal places + prompt/model version, so
72.001 vs 72.002 bpm don't miss the cache) → on a hit, skip the LLM entirely;
on a miss, call OpenAI (one retry, 15s timeout, failures logged and skipped
rather than crashing the consumer), computing real cost from
`usage.prompt_tokens`/`completion_tokens` against a static price table
(`insight_service/pricing.py`) → persist the `DeviceInsight` either way,
`cache_hit`/`latency_ms`/`cost_usd` included (a hit costs $0 and takes
~1ms; a miss costs whatever the model call actually billed), so cache hit
rate and the latency/cost delta it buys are a query away, not a claim —
`insight_service.eval.cache_savings` runs that query and prints the
"缓存命中率 X%，节省了约 $Y / 降低了 Z ms" summary directly.

```bash
services/insight_service/.venv/bin/python -m insight_service.eval.cache_savings --limit 200
```

**Hit rate depends heavily on traffic shape, not just time elapsed** — see
[benchmarks/week5_eval_report.md](benchmarks/week5_eval_report.md) §2 for
the measured numbers: one continuously-varying device's own snapshots rarely
repeat exactly (0.2% hit rate over a full real replay), but multiple devices
in similar physiological states organically collide on the same rounded
snapshot constantly (56.9% across a synthetic fleet resting near the same
heart rate) — this cache pays off at fleet scale, not from one device
running longer.

### Evaluation & A/B testing

`benchmarks/cases.yaml` is 22 hand-written cases (4 categories: normal,
elevated heart rate, HRV drop, boundary/edge cases) — each with human-written
`checks` describing what a grounded, safe response should do, not full
expected-output text (exact-matching LLM output isn't realistic).
`insight_service.eval.judge` scores exactly two dimensions on purpose
(more would make the eval framework more complex than the thing it's
evaluating): `check_grounded` is a rule-based check (does the described
trend direction match the data, does the text cite an actual number) —
no LLM needed for that half. `check_hallucination` calls an LLM judge
(same or a different model, configurable) with a strict yes/no + reason
prompt, JSON-parsed; a judge failure scores as unscored (`None`), never a
silent "no hallucination found".

```bash
services/insight_service/.venv/bin/python -m insight_service.eval.run_benchmark --prompt-version v1 --model gpt-4o-mini
services/insight_service/.venv/bin/python -m insight_service.eval.run_benchmark --prompt-version v2 --model gpt-4o-mini
```

Each run calls the real LLM directly (bypassing Redis on purpose — eval
measures generation quality, not cache hits) and writes one row per case to
`benchmarks/results/{timestamp}_{prompt_version}_{model}.csv`, plus a
grounded_rate/hallucination_rate/avg_latency/avg_cost summary to stdout.
`v1` vs `v2` is a real, measured comparison, not a hypothetical one:
**grounded_rate 18.2% → 95.5%**, at the cost of ~32% more latency and ~40%
more cost per call. See
[benchmarks/week5_eval_report.md](benchmarks/week5_eval_report.md) for the
full comparison table, the chart, and — more interesting than the headline
number — why v2 actually helps (not the failure mode the project originally
guessed it would fix) and a real bug the eval process itself caught along
the way.

### Observability (tracing)

`docker compose up -d` includes Jaeger (`jaegertracing/all-in-one`) — UI at
[localhost:16686](http://localhost:16686). `ingestion` and
`feature_extraction` both call `vitalstream_common.telemetry.configure_tracing()`
and export spans via OTLP/HTTP to Jaeger. The interesting part isn't the
per-service spans (FastAPI is auto-instrumented) — it's that they're all
*one trace* across two processes: `ingestion.kafka_producer` injects the
current span's W3C trace context into the outgoing Kafka message's headers,
and `feature_extraction.main`'s consumer loop extracts it back out and
continues the same trace instead of starting a new one. Search for any
recent trace under service `ingestion` and you'll see:

```
POST /api/v1/devices/{id}/signals   (ingestion, HTTP)
└─ consume raw-signal               (feature_extraction, Kafka)
   ├─ compute feature (bandpass+peaks)
   ├─ produce features-topic
   └─ write features row (postgres)
```

one span per stage from device upload to DB write, with real per-stage
latency (typically: Postgres write and Kafka produce dominate; the actual
signal-processing math is comparatively cheap).

## Status

Layers 1-2 (PRD milestones: Week 1-2 through Week 5) are working end-to-end:

- **Week 1-2**: the device simulator replays real PPG-DaLiA wrist-BVP data
  over HTTP, ingestion batches it onto Redpanda, and feature_extraction
  derives heart rate via a bandpass-filter + peak-detection pipeline (tuned
  against ground truth — see `validate_ppg_dalia.py`; naive parameters
  produced a ~37 bpm MAE from picking up the PPG dicrotic notch as a second
  peak per beat, tightened to ~8 bpm), persisting `Feature` rows to Postgres.
- **Week 3**: `config_service` gray-releases feature-algo versions (Postgres-
  backed, audited, hash-bucketed per device — live-verified: a 20% canary
  landed in exactly 20/100 devices' feature rows, and rollback dropped that
  to 0/100 within one 30s cache-refresh cycle); a full ingestion→Kafka→
  feature_extraction→Postgres trace is visible in Jaeger; and benchmarking
  ingestion found a real bug (the producer was blocking each HTTP response on
  a full Kafka ack, not just returning 202 immediately) — fixing it measured
  ~4.8x throughput / ~6.5x P50 latency at fixed concurrency. See
  [benchmarks/results.md](benchmarks/results.md) for the full methodology,
  including a couple of benchmarking dead ends worth knowing about before
  trusting any throughput number on this stack.
- **Week 4**: `feature_extraction` throttles per-device output onto
  `features-extracted` (Kafka-decoupled, not Postgres-polled); `insight_service
  .consumer` turns aggregated snapshots into cached, LLM-generated advice.
  Live-verified end-to-end against real PPG-DaLiA replay and a real OpenAI
  key: generated insights correctly referenced the actual heart-rate numbers
  and trend direction (not templated filler), a real rate-limit/quota error
  was hit mid-run and the consumer logged-and-skipped it without crashing
  (features kept flowing throughout), and the fixed-precision cache key
  produced a genuine, unforced 13/26 (50%) cache hit rate during a short
  partial replay — Week 5's fuller run tells a more complete story (below).
- **Week 5**: real eval, not a placeholder — `benchmarks/cases.yaml` (22
  hand-written cases) scored on two dimensions (rule-based groundedness,
  LLM-judge hallucination detection). A real, measured prompt A/B:
  **grounded_rate 18.2% → 95.5%** (v1 → v2), for a real cost — ~32% more
  latency, ~40% more cost per call. The fix targeted a *different* problem
  than the one this project started out expecting (v1 essentially never
  hallucinated; it just too often skipped citing the actual number it was
  given), which only showed up because the benchmark was run for real
  instead of assumed. Real per-call cost from OpenAI's actual token usage
  (not estimated) is now in every `device_insights`/`Insight` row.
  Draining a full 514-row single-device replay to completion (not a partial
  snapshot mid-backlog) put the real organic cache hit rate at 0.2% — very
  different from Week 4's 50%, because a fleet of similar devices, not one
  continuously-varying device, is what actually drives this cache's hit
  rate (confirmed: 56.9% across 40 synthetic devices resting near the same
  heart rate). See [benchmarks/week5_eval_report.md](benchmarks/week5_eval_report.md).

Layer 3 (full-stack delivery) is still a scaffold — see
[docs/PRD.md](docs/PRD.md) section 7 for the milestone plan.
