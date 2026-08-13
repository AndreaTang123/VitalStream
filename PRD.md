# Personalized Wearable Health Insights Platform

**Distributed Wearable Health Insights Platform**

Product Description + Architecture Implementation PRD (Full-Stack Python Implementation)

- **Author:** Xueying Tang
- **Date:** August 11, 2026
- **Status:** Draft · Personal Job-Search Project Plan
- **Version:** v2 (Python)

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [Goals and Non-Goals](#2-goals-and-non-goals)
3. [Core Functional Requirements](#3-core-functional-requirements)
4. [System Architecture](#4-system-architecture)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [Evaluation and Testing Strategy](#6-evaluation-and-testing-strategy)
7. [Milestones and Timeline (8-Week Plan)](#7-milestones-and-timeline-8-week-plan)
8. [Success Metrics (For Resume Quantification)](#8-success-metrics-for-resume-quantification)
9. [Risks and Mitigations](#9-risks-and-mitigations)
10. [Out of Scope / Future Extensions](#10-out-of-scope--future-extensions)

---

## 1. Product Overview

### 1.1 Background and Problem Statement

Wearable devices (smartwatches, fitness rings, CGMs, etc.) can continuously generate high-frequency physiological signals, but most consumer products stop at "displaying raw data" and lack two key capabilities: first, distributed infrastructure that can process data streams stably and with low latency at scale across many concurrent devices; second, an AI inference layer that can turn raw signals into trustworthy, explainable, evaluation-validated personalized health recommendations. This project aims to independently design and build a complete platform that covers both capabilities, delivered with enterprise-grade quality (authentication, authorization, auditing).

### 1.2 Product Vision

Build an end-to-end personalized health insights platform: starting from high-frequency signal ingestion from wearable devices, through a safely rollback-able feature extraction pipeline, to personalized recommendation generation based on a large language model with built-in evaluation and safeguards, ultimately delivered securely as an enterprise-grade full-stack application to end users (patients) and collaborating roles (coaches/clinicians).

### 1.3 Target Users and Roles

- **Patient** — Binds a wearable device, views personal health insights and historical trends.
- **Coach / Clinical Collaborator** — Within authorized scope, views aggregated health insights for the patients they are responsible for, used for remote guidance.
- **(Internal) Platform Operator Role** — Manages versioning, rollout, and rollback of feature extraction algorithms; views system monitoring and audit logs.

### 1.4 This Project's Position in the Job-Search Narrative

This project is not an isolated portfolio piece — it is deliberately designed as a "flagship project" that ties together three existing experiences: the data ingestion and processing layer borrows distributed system design patterns learned at ByteDance (staged config rollout, distributed tracing, high-concurrency data processing), but is reimplemented in Python (asyncio) to systematically deepen personal Python engineering skills, while also proving that engineering design ability transfers across languages and is not tied to a specific stack; the AI inference layer echoes the LLM-for-precision-health research direction pursued at UNC (but uses a different type of physiological signal and a different engineering focus, to avoid overlapping with the research project's content); the full-stack delivery layer corresponds to full-stack platform development experience at BioCryst. Combining all three layers demonstrates the ability to independently deliver a complete closed loop from infrastructure to product delivery.

## 2. Goals and Non-Goals

### 2.1 Goals

- Validate that the system can process high-frequency physiological signals from a large number of concurrent simulated devices at acceptable latency (specific concurrency and latency targets are in Section 9, to be determined from actual load-test results).
- Implement a safe release mechanism for feature extraction algorithms: version validation, staged rollout, one-click rollback.
- Implement an LLM-based health insight generation service with a built-in evaluation framework (hallucination rate, traceability), rather than a simple prompt wrapper.
- Deliver a full-stack application with authentication, role-based access control, and audit logging, meeting baseline compliance awareness for health-data scenarios.
- Produce quantified engineering metrics usable in a technical job search: throughput, latency percentiles, cache hit rate, evaluation accuracy, etc., all derived from real testing rather than fabricated.
- Systematically improve Python async programming, performance tuning, and engineering skills through this project, to address a gap from prior Python experience being mostly application-layer (FastAPI CRUD, scripts) and lacking practice with high-concurrency system design.

### 2.2 Non-Goals

- Not pursuing medical-grade diagnostic accuracy; all generated health advice is general lifestyle reference only, not clinical diagnosis.
- Not integrating with real hospital systems or real patient data; entirely simulated using public research datasets (e.g., WESAD, PPG-DaLiA).
- Not implementing a full HIPAA compliance certification process; only reflecting compliance-related engineering practices (audit logging, access control) at the architecture level.
- Not pursuing production-grade high availability (e.g., multi-region disaster recovery); focused on demonstrating core distributed systems and AI engineering capability.

## 3. Core Functional Requirements

### 3.1 Data Ingestion and Processing (Layer 1)

- Support simulated devices continuously reporting physiological signals (heart rate, HRV, sleep, activity level, etc.) via asynchronous HTTP/WebSocket.
- Signals are first written to a message queue (Kafka or Redis Streams) for peak-shaving buffering, then consumed by the feature extraction service.
- The feature extraction service, based on NumPy/SciPy, windows raw signals into structured features (e.g., resting heart rate, HRV trend, sleep quality score).
- Feature extraction algorithms support multiple concurrent versions, can be rolled out gradually by percentage, and can be rolled back to the last stable version with one click when anomalies are detected.
- Key processing paths are instrumented with distributed tracing to locate per-request latency and failure points across services.
- The ingestion service is built on asyncio, incorporating the uvloop event loop, connection pooling, and batched writes to mitigate Python's raw-throughput disadvantage relative to compiled languages.

### 3.2 AI Health Insight Generation (Layer 2)

- Consumes structured features and calls an LLM to generate personalized health advice text for patients.
- Caches results for identical or similar requests to avoid the cost and latency waste of repeated calls.
- Maintains a small, manually curated benchmark test set to quantify the hallucination rate and traceability (whether advice is grounded in supporting evidence) of generated content.
- Supports A/B comparison across different prompt versions / model versions, recording each version's evaluation score, latency, and cost.

### 3.3 Full-Stack Delivery Platform (Layer 3)

- Patients can register, log in, bind a simulated device, and view their personal historical health insights and trend charts.
- Coaches can view the list of patients they are authorized to access along with aggregated insights, for remote guidance scenarios.
- All authentication is based on OAuth2 / JWT; APIs are access-controlled by role (RBAC).
- Key access events on health data (who viewed whose data, when) are written to an audit log, with a query interface provided.

## 4. System Architecture

### 4.1 Architecture Overview

The system is organized into three layers, from bottom to top: the data ingestion and processing layer, the AI inference layer, and the full-stack delivery layer, with cross-cutting concerns including configuration management, observability, and deployment infrastructure:

> Simulated wearable devices → Python async ingestion service (asyncio + uvloop) → Kafka / Redis Streams → Python feature extraction service (NumPy/SciPy, staged rollout controlled by the configuration management service)

The feature extraction service's output splits into two paths: one is written to TimescaleDB for time-series storage and historical queries; the other flows into the LLM inference service (with caching, evaluation, and A/B testing) to generate personalized insights.

Both result paths are ultimately exposed through a FastAPI backend API to a Next.js frontend dashboard. The backend handles authentication (JWT), access control (RBAC), and audit logging uniformly, with data persisted in PostgreSQL.

Cross-cutting concerns: OpenTelemetry handles end-to-end distributed tracing; Prometheus + Grafana handle system metrics monitoring and alerting; GitHub Actions handles CI/CD; Docker handles containerization for consistency between local and cloud environments. All services are implemented uniformly in Python, to allow concentrated focus on deepening async programming and performance-tuning skills.

### 4.2 Layer Responsibilities and Key Design Decisions

- The data ingestion layer switches to Python (asyncio + aiokafka) instead of directly reusing the Go stack used at ByteDance; the core purpose is to systematically deepen async concurrent programming and performance-tuning skills. Design patterns such as event-driven ingestion, backpressure handling, and batched writes follow the same thinking as the Go version, demonstrating that engineering design ability is not tied to a specific language.
- The feature extraction algorithms use NumPy/SciPy/Pandas to implement sliding-window statistics and frequency-domain feature computation — this is another technical justification for choosing Python over continuing with the Go stack: Python has a clear advantage in the maturity of its scientific computing and signal processing libraries, not merely a personal-skill-building consideration.
- The configuration management service is designed after ByteDance's three-stage "validate → gradual rollout → rollback" release process, and is one of this project's core highlights that distinguishes it from an ordinary "CRUD project."
- The AI inference layer deliberately uses a different type of physiological signal than the UNC research (general wearable signals rather than CGM glucose data), and its engineering focus is on serving, caching, evaluation, and cost control rather than model fine-tuning itself, to ensure it complements rather than duplicates prior research experience.
- The RBAC and audit logging design in the full-stack delivery layer draws on experience building a Microsoft Entra ID permission system at BioCryst, but uses a lighter-weight OAuth2/JWT scheme suited to the time budget of independent development.
- To offset Python's raw-throughput gap relative to Go, the ingestion service introduces the uvloop event loop, connection pool reuse, and batched-write optimization, and this tuning process itself is treated as one of the project's technical highlights.

### 4.3 Technology Choices

| Layer | Technology | Purpose | Corresponding Experience |
|---|---|---|---|
| Data Ingestion / Processing | Python (asyncio, aiokafka/confluent-kafka), uvloop | Ingestion, buffering, and concurrent processing of high-frequency wearable signals | ByteDance distributed design pattern transfer + Python engineering skill-building |
| Feature Extraction Algorithms | NumPy, SciPy, Pandas | Sliding-window statistics, frequency-domain analysis, and other physiological signal feature computation | Natural advantage of Python's scientific computing ecosystem |
| Configuration Management | Self-built versioned configuration service (FastAPI + Pydantic, with validation/gradual rollout/rollback) | Safe release and rollback of feature extraction algorithms | ByteDance configuration management experience (pattern transfer) |
| Time-Series Storage | TimescaleDB | Storing raw signals and extracted feature time series | New tech stack |
| AI Inference Layer | OpenAI API / open-source models, Redis cache | Generating personalized health insights, caching repeated requests | UNC research + BioCryst LLM integration experience |
| Backend API | FastAPI | REST API, authentication, business logic | BioCryst full-stack experience |
| Frontend | Next.js | User dashboard, insight visualization | BioCryst full-stack experience |
| Database | PostgreSQL | User accounts, insight history, audit logs | BioCryst full-stack experience |
| Auth & Access Control | OAuth2 / JWT, RBAC | Patient/coach role differentiation and access control | BioCryst RBAC experience |
| Observability | OpenTelemetry (Python SDK), Prometheus, Grafana | Distributed tracing and system monitoring | ByteDance production operations experience |
| Load Testing | k6 / Locust | Validating system behavior under concurrent load | New tech stack |
| Deployment | Docker, GitHub Actions, Azure/AWS | Containerization, CI/CD, cloud deployment | BioCryst Azure deployment experience |

### 4.4 Core Data Model

| Entity | Key Fields | Description |
|---|---|---|
| User | `id`, `email`, `role` (patient/coach), `created_at` | Platform user account, distinguishing patient and coach roles |
| Device | `id`, `user_id`, `device_type`, `status` | Simulated wearable device bound to a user |
| RawSignal | `device_id`, `signal_type`, `value`, `timestamp` | Raw high-frequency physiological signal written by the ingestion layer |
| Feature | `device_id`, `feature_type`, `value`, `window`, `algo_version` | Structured feature produced by the feature extraction service, tagged with algorithm version |
| ConfigVersion | `id`, `algo_name`, `version`, `status`, `rollout_pct` | Versioned configuration for feature extraction algorithms, supporting gradual rollout |
| Insight | `id`, `user_id`, `content`, `model_version`, `eval_score`, `created_at` | Personalized health advice generated by the LLM, with an evaluation score |
| AuditLog | `id`, `actor_id`, `action`, `resource`, `timestamp` | Records who accessed/modified which health data, and when |

### 4.5 Key API Overview

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/devices/{id}/signals` | Ingest a single or batch of raw physiological signals (called internally by the ingestion service) |
| `GET` | `/api/v1/users/{id}/insights` | Retrieve a user's historical health insight list |
| `POST` | `/api/v1/insights/generate` | Trigger generation of a personalized insight based on the latest features |
| `GET` | `/api/v1/features/{device_id}` | Query the structured feature time series for a device |
| `POST` | `/api/v1/config/feature-algo` | Publish a new version of the feature extraction algorithm configuration (gradual rollout) |
| `POST` | `/api/v1/config/feature-algo/{version}/rollback` | Roll back the specified algorithm configuration version |
| `GET` | `/api/v1/audit-logs` | (Coach/admin role) Query audit logs |
| `POST` | `/api/v1/auth/login` | OAuth2 / JWT login authentication |

## 5. Non-Functional Requirements

### 5.1 Performance

The system must produce real measured values under load testing for the following metrics (values are to be obtained via actual k6/Locust testing after development; the PRD stage does not set specific targets, to avoid committing to unvalidated promises):

- Number of sustained concurrent simulated devices the system can handle
- End-to-end latency P50 / P95 / P99
- Signal ingestion throughput (events/sec)
- Average response latency and cache hit rate of the LLM inference service

### 5.2 Reliability and Fault Tolerance

- Message queue consumption failures must support retries and a dead-letter queue, so a single bad record doesn't block the entire pipeline.
- Configuration release failures or anomalies must be rollback-able within minutes.
- Key services must have health checks and automatic restart mechanisms.

### 5.3 Security and Compliance Awareness

- All access to health data requires authentication and role verification.
- Sensitive operations (viewing another user's health data, publishing configuration changes) must be written to an audit log, including actor, timestamp, and target object.
- No real personally identifiable information is stored; all test data comes from public research datasets or synthetic data.

### 5.4 Observability

- End-to-end distributed tracing covers the critical path from ingestion to insight generation.
- Grafana dashboards display system throughput, latency, error rate, and resource usage.

## 6. Evaluation and Testing Strategy

### 6.1 System-Level Testing

- Unit tests (pytest) cover core business logic (feature extraction algorithms, access control checks, audit log writes, etc.).
- Integration tests validate end-to-end correctness from ingestion to insight generation.
- Load testing with k6 / Locust simulates a large number of concurrent devices reporting continuously, recording how latency and throughput change with load.

### 6.2 AI-Generated Content Evaluation

- Build a small, manually labeled benchmark set covering typical health signal patterns and expected advice directions.
- Quantify the hallucination rate of generated content (whether it contains unsupported medical claims) and its traceability (whether it can be linked back to specific input features).
- Compare evaluation scores, latency, and cost across different prompt/model versions on the benchmark set, as a basis for version iteration.

## 7. Milestones and Timeline (8-Week Plan)

Total time budget: 1–2 months. The core milestone is reaching an end-to-end demonstrable pipeline by the end of Week 4; remaining time is used to progressively deepen "industrial-grade" evidence (real load-test data, monitoring, CI/CD). Using Python uniformly across the full stack avoids the cost of switching between multiple language environments. If personal time availability is limited, the overall plan can be extended to 10–12 weeks, but the Week 4 milestone should be preserved as closely as possible without major delay.

| Phase | Focus | Deliverables |
|---|---|---|
| Week 0 | Preparation | Finalize datasets (WESAD / PPG-DaLiA), draw architecture diagram, set up local docker-compose environment, establish repo skeleton |
| Weeks 1–2 | Layer 1 Core | Python async ingestion service (asyncio) + Kafka/Redis Streams integration + feature extraction service (NumPy/SciPy); get the simplest end-to-end pipeline running |
| Week 3 | Layer 1 Deepening | Configuration management service (versioning/gradual rollout/rollback) + OpenTelemetry distributed tracing + uvloop performance tuning |
| Week 4 | Layer 2 Core (Milestone) | LLM inference service integrated, consuming structured features to generate personalized advice; Redis caching; a demonstrable end-to-end pipeline should exist at this point |
| Week 5 | Layer 2 Deepening | Evaluation framework (hallucination/groundedness scoring, benchmark set) + prompt version A/B testing + cost/latency tracking |
| Week 6 | Layer 3 Core | FastAPI backend API + PostgreSQL schema + JWT authentication + RBAC + audit logging |
| Week 7 | Layer 3 Wrap-up | Next.js frontend dashboard, connected to the backend, producing a usable demo UI |
| Week 8 | Polish | Real concurrency/latency/throughput data from k6/Locust load testing + Prometheus/Grafana monitoring dashboard + CI/CD + README architecture diagram + demo recording |

## 8. Success Metrics (For Resume Quantification)

The following metrics will be filled into the resume's Projects section after the project is completed, based on real test results. At the PRD stage, only the metric types are listed, without preset values:

- Number of concurrent simulated devices the system stably supports under load testing
- End-to-end processing latency (P99)
- Signal ingestion and processing throughput
- Throughput improvement ratio from uvloop/batched-write optimization (compared to the unoptimized version)
- Cost/latency savings ratio from the LLM inference service's cache hit rate
- Evaluation accuracy / hallucination rate of AI-generated content on the benchmark set
- Unit test coverage

## 9. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Switching the full stack to Python weakens the direct connection to ByteDance's Go stack | May reduce persuasiveness of the "replicating ByteDance experience" story in interviews | Emphasize that what's being transferred is engineering design patterns (gradual rollout/distributed tracing/configuration management), not the language itself; use the NumPy/SciPy signal-processing choice and uvloop performance tuning as new technical highlights, directly addressing "why Python" |
| Limited personal time; four-layer scope is too large | Project risks being unfinished, or each layer being shallow | Preserve the Week 4 "end-to-end working" milestone; if time is short, prioritize deepening Layer 1, and downgrade Layer 3 to the simplest possible demo |
| AI inference layer overlaps in content with the UNC research project | Two resume projects tell the same story, appearing redundant | Use general wearable signals such as heart rate/HRV/sleep rather than CGM glucose data; clearly position this project around serving/infrastructure and the UNC project around the model itself |
| Lack of real device data makes load-test results unconvincing | Resume performance numbers won't hold up; follow-up interview questions would expose this | Use public real physiological datasets such as WESAD/PPG-DaLiA for replay, rather than randomly generated fake data |
| LLM call costs spiral out of control | API expenses exceed budget during development | Prioritize small-scale test data + a caching layer; use open-source models or capped testing during the evaluation phase |
| Putting an unfinished project on the resume too early | Can't answer detailed interview questions, which hurts rather than helps | Only consider adding it to the resume after completing the Week 4 milestone and having a demonstrable demo, and all figures must come from real measurements |

## 10. Out of Scope / Future Extensions

- Integrate real wearable device SDKs (e.g., Apple HealthKit, Fitbit API) to replace simulated device data.
- Introduce a stricter HIPAA/GDPR compliance certification process.
- Expand to multi-region deployment and disaster recovery capability.
- Explore privacy-preserving techniques such as federated learning for cross-user model optimization (could serve as an independent extension project if future job search direction leans toward ML research).
