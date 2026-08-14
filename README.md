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
                                  ▼                    ▼
                       ┌────────────────┐   ┌────────────────────┐
                       │ TimescaleDB     │   │ insight_service     │
                       │ (raw + feature  │   │ (LLM, Redis cache,  │
                       │  time series)   │   │  eval, A/B)         │
                       └────────────────┘   └──────────┬──────────┘
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

### Run the Layer 1 pipeline end-to-end

Once `docker compose up -d` and `make bootstrap` have run, and at least one
subject's data is under `data/raw/ppg_dalia/PPG_FieldStudy/` (see
[data/README.md](data/README.md)), run each of these in its own terminal:

```bash
services/config_service/.venv/bin/uvicorn config_service.main:app --app-dir services/config_service/src --port 8002
services/ingestion/.venv/bin/python -m ingestion.run
services/feature_extraction/.venv/bin/python -m feature_extraction.main
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

Layer 1 (PRD milestones: Week 1-2 + Week 3) is working end-to-end and
load-tested:

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

Layers 2-3 (LLM insights, full-stack delivery) are still scaffolds — see
[docs/PRD.md](docs/PRD.md) section 7 for the milestone plan.
