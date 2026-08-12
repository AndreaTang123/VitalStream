# Architecture

Maps [PRD section 4](PRD.md#4-系统架构) onto the actual repo layout.

```mermaid
flowchart TB
    subgraph devices["Simulated wearables"]
        D[HTTP / WebSocket signal replay]
    end

    subgraph l1["Layer 1 — data ingestion & processing"]
        ING["ingestion<br/>(asyncio + uvloop)<br/>services/ingestion"]
        KAFKA[("Kafka / Redis Streams")]
        FE["feature_extraction<br/>(NumPy/SciPy)<br/>services/feature_extraction"]
        CFG["config_service<br/>validate → gray release → rollback<br/>services/config_service"]
        TSDB[("TimescaleDB")]
    end

    subgraph l2["Layer 2 — AI inference"]
        INS["insight_service<br/>LLM + Redis cache + eval/A-B<br/>services/insight_service"]
    end

    subgraph l3["Layer 3 — full-stack delivery"]
        API["api<br/>FastAPI, JWT/OAuth2, RBAC, audit log<br/>services/api"]
        PG[("PostgreSQL")]
        FE_UI["frontend<br/>Next.js dashboard<br/>frontend/"]
    end

    D -->|POST /devices/{id}/signals| ING
    ING --> KAFKA
    KAFKA --> FE
    CFG -.->|active algo version| FE
    FE -->|features topic| TSDB
    FE -->|features| API
    API -->|features| INS
    INS -->|content, model_version| API
    API <--> PG
    API --> FE_UI
```

## Cross-cutting concerns (PRD 4.1)

| Concern | Tooling | Status in this scaffold |
|---|---|---|
| Distributed tracing | OpenTelemetry (`libs/common/telemetry.py`) | helper exists; not yet called from service entrypoints |
| Metrics | Prometheus + Grafana (`infra/prometheus`, `infra/grafana`) | scrape config drafted; services don't expose `/metrics` yet |
| CI/CD | GitHub Actions (`.github/workflows/ci.yml`) | lint + test per service, frontend build |
| Containerization | Docker (`services/*/Dockerfile`, `docker-compose.yml`) | Dockerfiles written; compose app services commented out until runnable |
| Load testing | k6 (`infra/k6/load_test.js`) | one scenario against `ingestion`; PRD 5.1 metrics still need real numbers |

## What's actually wired up vs. stubbed

This scaffold implements the shape of each PRD 3.x requirement (endpoints, data
model, RBAC rules, gray-release state machine) with working unit tests, but
several integration points are deliberately left as `TODO`s rather than faked:

- `feature_extraction` produces `Feature` messages onto Kafka but does not yet
  write them to TimescaleDB — `GET /api/v1/features/{device_id}` in `api`
  returns `501` until that sink exists.
- `insight_service`'s cost/latency fields on `LLMResponse` are placeholders
  (`0.0`) until real timing/usage accounting is added around the OpenAI call.
- No service exports Prometheus metrics yet; `docker-compose.yml`'s Prometheus
  scrape targets are aspirational.
