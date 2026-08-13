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

## Status

Layer 1 (PRD milestone: Week 1-2) is working end-to-end: the device simulator
replays real PPG-DaLiA wrist-BVP data over HTTP, ingestion batches it onto
Redpanda, and feature_extraction derives heart rate via a bandpass-filter +
peak-detection pipeline (tuned against ground truth — see
`validate_ppg_dalia.py`; naive parameters produced a ~37 bpm MAE from
picking up the PPG dicrotic notch as a second peak per beat, tightened to
~8 bpm), persisting `Feature` rows to Postgres. Layers 2-3 (LLM insights,
full-stack delivery) are still scaffolds — see [docs/PRD.md](docs/PRD.md)
section 7 for the milestone plan.
