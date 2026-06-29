# SpeedFlow

SpeedFlow is an AI-driven, **multi-tenant data platform** that ingests web and API data, processes it in real time, and serves it through domain-specific applications. A cognitive control layer (orchestrator + agent swarm) dynamically plans scraping jobs, selects processing strategies, and closes the loop using feedback from downstream apps.

The platform targets three business verticals out of the box: **Gaming & Esports**, **Financial Markets**, and **Accommodation**. Tenants subscribe to tiered plans (`starter`, `pro`, `enterprise`) that gate features such as proxy crawling, dedicated Kafka topics, and full AI agent access.

---

## Current Status (June 2026)

| Area | Status |
|------|--------|
| **Core scrape pipeline** | Working locally: `POST /scrape` → Crawlee worker → `raw_stream` → stream processor → `processed_stream` |
| **Infra (Docker)** | Postgres, Redis, Kafka, Schema Registry, OpenSearch run via Compose |
| **Apps (host)** | Platform API, AI Orchestrator, UI Portal run on host via `make start-local` |
| **Pipeline workers (host)** | Crawlee worker + stream processor via `make start-pipeline` |
| **Control portal** | React UI at :8030 — burger sidebar, clickable services/jobs, detail drawer with logs |
| **Near-term roadmap (items 1–6)** | Done (Connect image, Selenium/Playwright, quotas, job status, Avro, UI) |
| **Full Docker stack** | Not fully validated (`make up` — some images need stable Docker Hub pulls) |
| **Serving apps (8010–8014)** | Not started in local-dev path; show as down in UI |
| **Kafka Connect sinks** | Image exists; connectors not registered until Connect container runs |
| **Flink / Airflow / ML in prod path** | Scaffolded; not wired end-to-end |

**Recommended dev path:** `make install-local-deps` → `make start-local` → `make pipeline-test` → open http://localhost:8030

---

## Table of Contents

1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Folder Structure](#folder-structure)
5. [Running & Using Each Layer](#running--using-each-layer)
6. [Configuration Reference](#configuration-reference)
7. [Data Flow](#data-flow)
8. [Service URLs](#service-urls)
9. [What Still Needs Implementation](#what-still-needs-implementation)
10. [Next Phases — Mandatory TODO List](#next-phases--mandatory-todo-list)
11. [Completed Roadmap (Archive)](#completed-roadmap-archive)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  4-platform-api          Multi-tenant gateway (FastAPI + subscriptions) │
│  POST /scrape, /tenants, plan enforcement, API keys                     │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ natural-language scrape requests
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  0-ai-intelligence       Orchestrator + 5 Agents + 3 Bridges            │
│  Strategy → Discovery → Processing → Config → Scrape Planner            │
│  Bridges: Scraper (Redis/Crawlee) | Processing (Flink/ML) | Config      │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  1-ingestion-edge        Airflow DAGs, Crawlee workers, REST/WS scrapers│
│  Publishes RawEvent → Kafka raw_stream (+ per-tenant topics on Pro+)    │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  2-stream-compute        Stream processor, Flink cluster, ML service      │
│  raw_stream → stateful transforms / ML inference → processed_stream     │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
┌──────────────────────────┐         ┌──────────────────────────┐
│  Kafka Connect sinks     │         │  3-serving-api apps      │
│  Postgres + Elasticsearch│         │  Trading Bot, Aggregator,│
└──────────────────────────┘         │  Dashboard, Marketplace, │
                                      │  Auditing (+ feedback)   │
                                      └──────────────────────────┘
```

**Messaging backbone:** Kafka (`raw_stream`, `processed_stream`, `feedback_metrics`), Redis (job queues), Schema Registry (Avro schemas in `schemas/avro/`).

**Storage:** PostgreSQL (structured events, tenants, scrape jobs), OpenSearch (Elasticsearch-compatible search index; `platform-search` container).

---

## Prerequisites

| Requirement | Version / Notes |
|-------------|-----------------|
| Docker & Docker Compose | v2+ recommended |
| Make | Optional; wraps common commands |
| curl | For health checks and API examples |
| 8 GB+ RAM | Full stack runs ~25 containers |

Optional for enhanced AI behavior:

- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in `.env` (agents fall back to rule-based logic without keys)
- `CRAWLEE_PROXY_URL` for proxy-backed crawling at scale

---

## Quick Start

### Path A — Local dev (recommended, pipeline verified)

Uses Docker for infra only; runs API, orchestrator, portal, and pipeline workers on the host. Avoids heavy image builds during development.

```bash
# 1. Clone and configure
cp .env.example .env

# 2. One-time: Python deps for host workers
make install-local-deps

# 3. Start infra + apps + pipeline workers
make start-local
# Equivalent steps:
#   docker compose up -d postgres redis elasticsearch kafka schema-registry
#   make start-apps      # platform-api :8020, orchestrator :8000, portal :8030
#   make start-pipeline  # crawlee-worker + stream-processor

# 4. Verify end-to-end scrape pipeline
make pipeline-test

# 5. Check process status
make status

# 6. Open control portal
make portal   # → http://localhost:8030
```

**Stop host processes:**

```bash
make stop-local
```

**Host process logs:** `/tmp/speedflow-*.log` (also viewable in the UI detail drawer → Logs tab)

---

### Path B — Full Docker stack

```bash
# 1. Clone and configure
cp .env.example .env

# 2. Build and start all ~25 services
make up

# 3. Wait ~60s, then verify health
make health

# 4. Register Kafka topics schemas and Connect sinks
make schemas
make connectors

# 5. Create a tenant and submit a scrape
make tenant-create
API_KEY=sf_xxx make scrape-request

# 6. Run AI orchestration cycle
make orchestrate

# 7. Open portal
make portal   # → http://localhost:8030
```

**Scale Crawlee workers:**

```bash
docker compose up -d --scale crawlee-worker=5
```

**Stop everything:**

```bash
make down
```

**Tail logs:**

```bash
make logs
docker compose logs -f platform-api ai-orchestrator crawlee-worker
```

---

### Makefile reference

| Target | Description |
|--------|-------------|
| `make up` / `make down` | Full Docker Compose stack |
| `make start-local` | Infra in Docker + apps + pipeline on host |
| `make start-apps` | Platform API, orchestrator, portal only |
| `make start-pipeline` | Crawlee worker + stream processor only |
| `make stop-local` | Stop all host processes |
| `make status` | List host PIDs + Docker infra health |
| `make pipeline-test` | E2E: tenant → scrape → Kafka processed_stream |
| `make install-local-deps` | pip install for host pipeline workers |
| `make health` | Curl health checks for all services |
| `make tenant-create` | Create demo tenant via Platform API |
| `make scrape-request` | Submit scrape (`API_KEY=sf_...` required) |
| `make orchestrate` | Run full AI agent cycle |
| `make connectors` | Register Kafka Connect JDBC + ES sinks |
| `make schemas` | Register Avro schemas in Schema Registry |
| `make portal` | Print portal URL |

---

## Folder Structure

```
speedFlow/
├── 0-ai-intelligence/              # Cognitive control layer
│   ├── orchestrator/main.py        # FastAPI entry — POST /orchestrate, /feedback
│   ├── agents/                     # Strategy, Discovery, Processing, Config, Scrape Planner
│   ├── bridges/                    # Scraper, Processing, Config bridges (Redis/GitOps)
│   ├── shared/utils.py             # LLM helpers, YAML loading, AgentState
│   ├── Dockerfile
│   └── requirements.txt
│
├── 1-ingestion-edge/               # Data ingestion
│   ├── crawlee-service/            # Scalable Crawlee workers (proxy, session pool)
│   │   ├── crawler.py              # BeautifulSoupCrawler + document fetcher
│   │   ├── worker.py               # Redis queue consumer
│   │   └── config/proxies.yaml     # Tiered proxy pools
│   ├── scrapers/                   # REST, WebSocket, Selenium, Crawlee adapters
│   │   ├── rest/scraper.py
│   │   ├── websocket/scraper.py
│   │   ├── selenium/scraper.py     # Headless Chrome + Playwright engines
│   │   ├── crawlee/scraper.py
│   │   ├── shared/                 # Kafka Avro client, job_status, runner
│   │   └── config/*.yaml           # Per-scraper source definitions
│   └── airflow-dags/               # Parameter-driven parent DAG
│       └── dags/parent_orchestrator.py
│
├── 2-stream-compute/               # Stream processing & ML
│   └── flink-ml-workers/
│       ├── stream_processor.py     # Kafka consumer/producer (Flink-equivalent MVP)
│       ├── flink-jobs/             # PyFlink job definitions (not yet wired to cluster)
│       └── ml-service/             # FastAPI sklearn inference microservice
│
├── 3-serving-api/                  # End-use applications
│   ├── aggregator-backend/         # Accommodation search (MVP sample data)
│   ├── trading-bot/                # Consumes processed_stream for buy/sell signals
│   ├── dashboard/                  # ES-backed metrics overview
│   ├── marketplace/                # Data product catalog & orders
│   ├── auditing-service/           # Compliance audit log
│   └── shared/feedback_client.py   # Sends metrics → AI Orchestrator
│
├── 4-platform-api/                 # Multi-tenant subscription gateway
│   └── main.py                     # Tenants, scrape jobs, plan enforcement
│
├── 5-ui/                           # Control portal (React + BFF API)
│   ├── portal-api/main.py          # Aggregates health, jobs, pipeline, logs
│   ├── portal-web/                 # React dashboard (Vite + Tailwind)
│   │   ├── src/components/Layout.tsx      # Burger sidebar, collapse
│   │   ├── src/components/DetailDrawer.tsx # Service/job logs & health
│   │   └── src/pages/              # Overview, Ingestion, Stream, AI, Apps, Tenants
│   └── Dockerfile                  # Multi-stage build → port 8030
│
├── config/
│   ├── business/                   # metrics.yaml, verticals.yaml, governance.yaml
│   ├── subscriptions/plans.yaml    # starter / pro / enterprise feature flags
│   ├── mlops/agent_governance.yaml
│   ├── finops/budgets.yaml
│   └── security/compliance.yaml
│
├── schemas/avro/                   # RawEvent & ProcessedEvent Avro schemas
├── infra/
│   ├── kafka-connect/              # Postgres & ES sink connector JSON configs
│   ├── terraform/                  # AWS MSK skeleton (not applied by default)
│   └── gitops/argocd/              # ArgoCD Application manifest
│
├── scripts/
│   ├── init-postgres.sql           # DB schema (tenants, events, signals, audit)
│   ├── register-connectors.sh      # Registers Kafka Connect sinks
│   ├── register-schemas.sh         # Registers Avro schemas
│   ├── start-local.sh              # Infra Docker + apps + pipeline (host)
│   ├── start-apps.sh               # Platform API, orchestrator, portal
│   ├── start-pipeline.sh           # Crawlee worker + stream processor
│   ├── stop-local.sh               # Stop host processes
│   ├── status-local.sh             # Process & infra status
│   ├── pipeline-test.sh            # E2E scrape pipeline test
│   └── install-local-deps.sh       # Host Python dependencies
│
├── docker-compose.yml              # Full local stack definition
├── Makefile                        # up, down, health, tenant-create, orchestrate, …
├── .env.example
└── requirements.txt                # Shared Python dependencies (reference)
```

---

## Running & Using Each Layer

### Layer 0 — AI Intelligence (`0-ai-intelligence/`)

**Purpose:** Coordinates the agent swarm, translates business goals into scraping/processing actions, and pushes jobs to bridges.

**Run:** Started automatically as `ai-orchestrator` (port 8000).

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Agent availability check |
| `POST /orchestrate` | Full cycle: Strategy → Discovery → Processing → Config → Bridges |
| `POST /feedback` | Apps report metrics; feeds Strategy Agent on next cycle |
| `POST /agents/scrape/plan` | Natural language → Crawlee job parameters |
| `POST /agents/discovery/push-targets` | Inject dynamic scraping targets |

```bash
# Full orchestration with bridge execution
curl -X POST http://localhost:8000/orchestrate \
  -H "Content-Type: application/json" \
  -d '{"business_goals":["maximize_revenue"],"run_bridges":true}'

# Push a custom REST source for discovery
curl -X POST http://localhost:8000/agents/discovery/push-targets \
  -H "Content-Type: application/json" \
  -d '[{"source_id":"custom_api","type":"rest","url":"https://api.example.com/data","vertical":"financial_markets"}]'
```

**Agents:**

| Agent | Role |
|-------|------|
| Strategy | Reads KPIs + app feedback → data gaps |
| Discovery | Values sources, proposes scraping targets |
| Processing | Chooses Flink vs ML vs simple aggregation |
| Config | Generates Terraform/K8s YAML (GitOps output) |
| Scrape Planner | Maps user requirements → Crawlee selectors, depth, proxy tier |

Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in `.env` for LLM-enhanced decisions. Without keys, agents use deterministic rule-based fallbacks.

---

### Layer 5 — Control Portal (`5-ui/`)

**Purpose:** Unified web UI to visualize, operate, and inspect the entire platform.

**URL:** http://localhost:8030

| Page | What you see |
|------|----------------|
| Overview | Service health, live pipeline flow (6 steps), clickable pipeline diagram, crawl chart |
| Ingestion | Scraper cards, Crawlee job table (click row → job details + logs) |
| Stream Compute | Kafka topics, Connect sinks, Avro schemas, stream processor status |
| AI Intelligence | Agent cards, orchestration runner, bridge details |
| Applications | Trading signals, marketplace, dashboard KPIs (click for detail) |
| Tenants | Create tenants, submit scrapes, subscription plans |

**UI features:**

- Responsive **burger menu** sidebar (mobile slide-in + desktop collapse)
- **Hover-rich navigation** with subtitles and live “services up” badge
- **Detail drawer** on click — Info / Health / Logs tabs
- **Live logs** from host workers via `GET /api/logs/{name}`
- **Pipeline status** via `GET /api/pipeline`
- Polls backend every 5 seconds

```bash
make portal                    # print URL
make start-local               # runs portal on host (dev)
docker compose up -d ui-portal # portal in Docker (full stack)
cd 5-ui/portal-web && npm run build   # rebuild static assets
```

---

### Layer 1 — Ingestion Edge (`1-ingestion-edge/`)

**Purpose:** Collect raw data from the web and APIs, publish `RawEvent` messages to Kafka.

#### Crawlee Workers (`crawlee-service/`)

Production-grade crawling via [Crawlee for Python](https://crawlee.dev/python/):

- HTML pages via `BeautifulSoupCrawler`
- PDFs and JSON via document fetcher
- Proxy rotation and session pools
- Horizontally scalable via Redis job queue

Jobs are queued by the Platform API (via Scrape Planner) or the Scraper Bridge. Scale workers:

```bash
docker compose up -d --scale crawlee-worker=10
```

Configure proxies in `1-ingestion-edge/crawlee-service/config/proxies.yaml` or set `CRAWLEE_PROXY_URL` in `.env`.

#### REST / WebSocket / Selenium Scrapers (`scrapers/`)

Long-running Python processes poll YAML-defined sources and dynamic Redis job queues:

| Scraper | Config | Notes |
|---------|--------|-------|
| `scraper-rest` | `config/rest.yaml` | HTTP polling |
| `scraper-websocket` | `config/websocket.yaml` | Live WebSocket feeds |
| `scraper-selenium` | `config/selenium.yaml` | Headless Chrome + Playwright (Docker image includes Chromium) |

Edit source URLs and intervals in the YAML configs, then restart the corresponding container.

#### Airflow (`airflow-dags/`)

**URL:** http://localhost:8080 (admin / admin)

The `parent_orchestrator` DAG loads vertical config from `config/business/verticals.yaml`, triggers ingestion/processing steps, and validates pipeline health (health check is currently a stub).

Trigger manually from the Airflow UI or via CLI inside the container.

---

### Layer 2 — Stream Compute (`2-stream-compute/`)

**Purpose:** Transform raw events into enriched, prediction-ready `ProcessedEvent` records.

| Component | Port | Description |
|-----------|------|-------------|
| `stream-processor` | — | Kafka loop: `raw_stream` → rolling stats + signals → `processed_stream` |
| `flink-jobmanager` | 8082 | Flink 1.18 dashboard (jobs in `flink-jobs/` not auto-submitted) |
| `ml-service` | 8090 | FastAPI + sklearn SGDRegressor inference |

```bash
# ML inference example
curl -X POST http://localhost:8090/infer \
  -H "Content-Type: application/json" \
  -d '{"model_id":"price_momentum","features":{"price":42000.5,"momentum":0.02}}'
```

The stream processor applies in-memory rolling windows (Flink-equivalent MVP). Native PyFlink jobs exist in `flink-jobs/raw_to_processed.py` but require a custom Flink image build to run on the cluster.

---

### Layer 3 — Serving API (`3-serving-api/`)

**Purpose:** Domain applications that consume processed data and send feedback to the orchestrator.

| App | Port | Key Endpoints | Data Source |
|-----|------|---------------|-------------|
| Aggregator | 8010 | `GET /search?location=Paris` | Sample data (MVP) |
| Trading Bot | 8011 | `GET /signals`, `GET /stats` | Kafka `processed_stream` |
| Auditing | 8012 | `POST /audit`, `GET /audit` | In-memory log |
| Dashboard | 8013 | `GET /metrics/overview` | Elasticsearch |
| Marketplace | 8014 | `GET /products`, `POST /orders` | `governance.yaml` catalog |

All apps call `POST /feedback` on the orchestrator at startup and during key actions, closing the AI feedback loop.

```bash
curl http://localhost:8011/signals      # Latest trading signals
curl http://localhost:8014/products     # Data product catalog
curl "http://localhost:8010/search?location=London&max_price=200"
```

---

### Layer 4 — Platform API (`4-platform-api/`)

**Purpose:** Public-facing multi-tenant gateway. Handles subscriptions, API keys, scrape job submission, and plan enforcement.

**URL:** http://localhost:8020

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /health` | — | Health check |
| `GET /features` | — | List subscription plans |
| `POST /tenants` | — | Create tenant → returns `api_key` |
| `GET /tenants/me` | `X-API-Key` | Current tenant info + features |
| `GET /usage` | `X-API-Key` | Daily scrape quota usage |
| `POST /scrape` | `X-API-Key` | Submit natural-language scrape job |
| `GET /scrape/{job_id}` | `X-API-Key` | Job status |

```bash
# Create tenant
curl -X POST http://localhost:8020/tenants \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo Corp","plan":"pro","email":"demo@example.com"}'

# Submit scrape (AI picks Crawlee parameters)
curl -X POST http://localhost:8020/scrape \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"requirement":"Scrape article titles from https://news.ycombinator.com","max_pages":20}'

# Check job status
curl -H "X-API-Key: YOUR_KEY" http://localhost:8020/scrape/JOB_ID
```

**Subscription tiers** (see `config/subscriptions/plans.yaml`):

| Feature | Starter | Pro | Enterprise |
|---------|---------|-----|------------|
| AI Scrape Planner | ✓ | ✓ | ✓ |
| Crawlee + proxy | — | ✓ | ✓ premium |
| Dedicated Kafka topic | — | ✓ | ✓ |
| AI agents (full swarm) | planner only | partial | all |
| Daily scrape quota | 50 | 500 | 10,000 |

---

### Infrastructure (`infra/`)

| Path | Purpose | How to use |
|------|---------|------------|
| `kafka-connect/` | Sink connector configs | `make connectors` after stack is up |
| `terraform/` | AWS MSK + EKS skeleton | Copy `terraform.tfvars.example`, then `terraform init && plan` |
| `gitops/argocd/` | ArgoCD Application manifest | Deploy to a K8s cluster with ArgoCD installed |

Config Bridge writes generated manifests to the `gitops-output` Docker volume. Set `GITOPS_DRY_RUN=false` in `.env` to apply changes (default is dry-run).

---

## Configuration Reference

| File | Controls |
|------|----------|
| `.env` | LLM keys, Kafka/Redis/Postgres URLs, proxy, FinOps budgets |
| `config/business/metrics.yaml` | KPIs the Strategy Agent optimizes |
| `config/business/verticals.yaml` | Industry verticals, seed sources, reference pipelines |
| `config/business/governance.yaml` | Data quality rules, marketplace product catalog |
| `config/subscriptions/plans.yaml` | Tenant plan limits and feature flags |
| `config/finops/budgets.yaml` | Daily cost caps for scraping, compute, LLM |
| `config/security/compliance.yaml` | RBAC, PII handling, encryption baseline |
| `config/mlops/agent_governance.yaml` | Agent versioning and drift detection rules |
| `schemas/avro/*.avsc` | Kafka event schemas (RawEvent, ProcessedEvent) |

---

## Data Flow

1. **Ingestion:** Scrapers or Crawlee workers publish `RawEvent` (Avro via Schema Registry when `USE_AVRO=true`) to Kafka `raw_stream`.
2. **Processing:** `stream-processor` consumes `raw_stream`, computes rolling features and simple buy/sell signals, publishes `ProcessedEvent` to `processed_stream`.
3. **Persistence:** Kafka Connect sinks `processed_stream` to PostgreSQL (`processed_events` table) and Elasticsearch (`processed-events` index). Run `make connectors` to register sinks.
4. **Consumption:** Trading Bot subscribes to `processed_stream` live; Dashboard queries Elasticsearch; Aggregator/Marketplace use Postgres or static catalogs.
5. **Feedback loop:** Serving apps POST metrics to the AI Orchestrator → Strategy Agent identifies data gaps → Discovery/Scrape Planner queue new ingestion jobs.

---

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Platform API | http://localhost:8020 | API key via `X-API-Key` |
| AI Orchestrator | http://localhost:8000 | — |
| Airflow | http://localhost:8080 | admin / admin |
| Flink Dashboard | http://localhost:8082 | — |
| Schema Registry | http://localhost:8081 | — |
| Kafka Connect | http://localhost:8083 | — |
| ML Service | http://localhost:8090 | — |
| Aggregator | http://localhost:8010 | — |
| Trading Bot | http://localhost:8011 | — |
| Auditing | http://localhost:8012 | — |
| Dashboard | http://localhost:8013 | — |
| Marketplace | http://localhost:8014 | — |
| **UI Portal** | **http://localhost:8030** | — |
| Kafka (host) | localhost:29092 | — |
| PostgreSQL | localhost:**5433** | admin / adminpassword |
| OpenSearch | http://localhost:9200 | no auth (dev) |
| Redis | localhost:**6380** | — |

> **Note:** Inside Docker Compose, services use internal hostnames (`postgres:5432`, `redis:6379`, `elasticsearch:9200`). Host-mapped ports differ for local dev to avoid conflicts.

### Host processes (local dev via `make start-local`)

| Process | Port | Log file |
|---------|------|----------|
| platform-api | 8020 | `/tmp/speedflow-platform-api.log` |
| ai-orchestrator | 8000 | `/tmp/speedflow-orchestrator.log` |
| ui-portal (portal-api) | 8030 | `/tmp/speedflow-portal.log` |
| crawlee-worker | — | `/tmp/speedflow-crawlee-worker.log` |
| stream-processor | — | `/tmp/speedflow-stream-processor.log` |

PID files: `/tmp/speedflow-pids/*.pid` — check with `make status`.

---

## What Still Needs Implementation

These areas exist as scaffolding or MVP stubs and require further work before production use.

### Ingestion & Scraping

| Gap | Current State | Needed |
|-----|---------------|--------|
| Airflow child DAGs | Parent DAG logs sources only | Actual DAG triggers for each scraper type |
| Per-tenant Kafka topics | Prefix stored on tenant; partial wiring | Auto-create topics + ACLs on tenant provisioning |

### Stream Processing

| Gap | Current State | Needed |
|-----|---------------|--------|
| Flink jobs | PyFlink script exists; not submitted | Custom Flink Docker image with PyFlink + job submission |
| Stream processor state | In-memory rolling window | Flink state backend or RocksDB for fault tolerance |
| ML service | sklearn SGDRegressor MVP | GPU/CUDA models, model registry, A/B routing |
| Processing Agent → ML | Bridge queues config | End-to-end: agent config → live model hot-swap |

### Platform & Multi-Tenancy

| Gap | Current State | Needed |
|-----|---------------|--------|
| Billing / metering | Plan prices in YAML only | Usage tracking, invoicing integration |
| Auth beyond API keys | Single header auth | OAuth2, RBAC, tenant admin UI |

### Serving Applications

| Gap | Current State | Needed |
|-----|---------------|--------|
| Aggregator | Hard-coded sample hotels | Query Postgres/ES for live scraped accommodation data |
| Dashboard | Basic ES count + mock KPIs | Full analytics UI, time-series charts |
| Marketplace | In-memory orders | Postgres persistence, payment gateway, API key delivery |
| Auditing | In-memory log | Postgres `audit_log` table writes, retention policies |
| Trading Bot | Simple momentum signals | Risk management, order execution, backtesting |

### Infrastructure & Production

| Gap | Current State | Needed |
|-----|---------------|--------|
| Elasticsearch | Security disabled | Enable xpack security, TLS, index lifecycle management |
| Terraform | MSK skeleton | Full EKS + MSK + RDS module, env-specific tfvars |
| GitOps / Config Agent | Dry-run to volume | Git push + ArgoCD sync to real cluster |
| Observability | Log-only | Prometheus metrics, Grafana dashboards, distributed tracing |
| Secrets management | Plain `.env` | Vault or cloud secret manager integration |

### AI Layer

| Gap | Current State | Needed |
|-----|---------------|--------|
| Agent governance | YAML rules defined | Automated drift detection, agent version rollback |
| FinOps budgets | Static YAML caps | Runtime budget tracking and throttling |
| LLM cost control | Optional keys | Token metering, caching, fallback model routing |
| Feedback persistence | Passed per orchestrate call | Store feedback in Postgres for historical analysis |

---

## What Still Needs Implementation

These areas exist as scaffolding, partial wiring, or MVP stubs. Items marked **Phase 2** are mandatory next steps (see [Next Phases](#next-phases--mandatory-todo-list)).

### Ingestion & Scraping

| Gap | Current State | Needed | Phase |
|-----|---------------|--------|-------|
| Full Docker scrapers | REST/WS/Selenium images built but not in local-dev path | Run all scraper containers under `make up`; validate YAML sources | 2 |
| Airflow child DAGs | Parent DAG logs sources only | DAGs that enqueue scraper jobs and monitor Kafka lag | 3 |
| Per-tenant Kafka topics | Pro/Enterprise flag in plans; worker uses `raw_stream` by default | Auto-create `raw_stream_{tenant_id}` + consumer routing when `dedicated_kafka_topic` | 3 |
| Playwright in host worker | BeautifulSoup/fallback on host | `playwright install chromium` in `install-local-deps` or Docker-only crawls | 2 |

### Stream Processing & Persistence

| Gap | Current State | Needed | Phase |
|-----|---------------|--------|-------|
| Kafka Connect running | Custom image + configs exist | Start Connect container; `make connectors`; verify Postgres + OpenSearch sinks | 2 |
| Events in OpenSearch | Stream processor publishes to Kafka | Connect ES sink or app-level indexer; Dashboard reads live counts | 2 |
| Flink jobs | PyFlink script exists; not submitted | Custom Flink image; submit `raw_to_processed.py`; retire in-memory processor for stateful workloads | 3 |
| Stream processor state | In-memory rolling window on host | Flink state backend or RocksDB for fault tolerance | 3 |
| ML service | sklearn MVP in Docker | GPU models, model registry, Processing Agent hot-swap | 3 |

### Platform & Multi-Tenancy

| Gap | Current State | Needed | Phase |
|-----|---------------|--------|-------|
| Full `make up` validation | Local path works; full stack intermittent | CI/build cache; pre-pull images; document single-command prod-like dev | 2 |
| Billing / metering | Plan prices in YAML | Usage tracking, invoicing integration | 4 |
| Auth beyond API keys | `X-API-Key` header | OAuth2, RBAC, tenant admin roles in UI | 4 |

### Serving Applications

| Gap | Current State | Needed | Phase |
|-----|---------------|--------|-------|
| All serving apps up | 8010–8014 down in local dev | Include in `make up`; portal shows green health | 2 |
| Aggregator | Hard-coded sample hotels | Query Postgres/ES for live accommodation data | 3 |
| Dashboard | Mock KPIs when ES empty | Real ES aggregations, time-series charts in UI | 3 |
| Marketplace | In-memory orders | Postgres persistence, payment gateway, API key delivery | 4 |
| Auditing | In-memory log | Writes to `audit_log` table, retention policies | 3 |
| Trading Bot | Simple momentum signals | Risk rules, backtesting; consume live `processed_stream` in Docker | 2 |

### Infrastructure & Production

| Gap | Current State | Needed | Phase |
|-----|---------------|--------|-------|
| OpenSearch security | Disabled for dev | Enable security plugin, TLS, ILM policies | 4 |
| Terraform | MSK skeleton | Full EKS + MSK + RDS modules, env tfvars | 4 |
| GitOps / Config Agent | Writes to `gitops-output/` | Git push + ArgoCD sync to real cluster | 4 |
| Observability | Logs only (+ UI log tail) | Prometheus metrics, Grafana dashboards, OpenTelemetry | 3 |
| Secrets | Plain `.env` | Vault or cloud secret manager | 4 |

### AI Layer

| Gap | Current State | Needed | Phase |
|-----|---------------|--------|-------|
| Agent governance | YAML rules defined | Drift detection, agent version rollback | 4 |
| FinOps budgets | Static YAML caps | Runtime budget tracking and throttling | 4 |
| LLM cost control | Optional keys + rule fallback | Token metering, caching, model routing | 3 |
| Feedback persistence | Per orchestrate call | Store feedback in Postgres for historical analysis | 3 |

---

## Next Phases — Mandatory TODO List

All items below **must** be completed in order within each phase before moving to the next. Check boxes track progress.

### Phase 2 — Full stack parity (next sprint) **REQUIRED**

Goal: One command (`make up`) runs everything; data persists to DB + search; all UI services green.

- [ ] **2.1** Stabilize `make up` — fix Docker build/pull failures; add image pre-pull script or CI cache
- [ ] **2.2** Start **Kafka Connect** container; run `make connectors`; verify JDBC sink → `processed_events` in Postgres
- [ ] **2.3** Verify **OpenSearch sink** indexes events; Dashboard :8013 returns non-zero `events_indexed`
- [ ] **2.4** Run **all serving apps** (8010–8014) in Compose; `make health` all green
- [ ] **2.5** Run **crawlee-worker**, **stream-processor**, **scrapers** in Docker (not only host); scrape jobs complete without host workers
- [ ] **2.6** Run **ui-portal** in Docker with internal service URLs; parity with host portal
- [ ] **2.7** **Trading bot** consumes `processed_stream` in Docker and exposes live signals in UI
- [ ] **2.8** Add **`kafka-init`** to `start-local` reliably (topics always exist on fresh start)
- [ ] **2.9** Document and test **Path B** end-to-end in README quick start (tenant → scrape → Connect → dashboard)
- [ ] **2.10** Portal: show Docker container logs (not only host `/tmp` logs) when running full stack

### Phase 3 — Production-grade data plane **REQUIRED**

Goal: Replace MVPs with durable, observable, vertically integrated pipelines.

- [ ] **3.1** Submit **PyFlink** job `raw_to_processed.py` to Flink cluster; validate stateful windows
- [ ] **3.2** **Airflow child DAGs** — trigger scrapers, monitor lag, alert on failures
- [ ] **3.3** **Per-tenant Kafka topics** — create on tenant provision; stream processor multi-topic consume
- [ ] **3.4** **Aggregator** — live accommodation data from ingested events (not sample JSON)
- [ ] **3.5** **Dashboard** — ES-backed charts; wire to portal Applications page
- [ ] **3.6** **Auditing service** — persist to Postgres `audit_log`
- [ ] **3.7** **ML model registry** — version models; Processing Agent triggers hot reload
- [ ] **3.8** **LLM feedback store** — Postgres table for orchestrator feedback history
- [ ] **3.9** **Observability** — Prometheus exporters on Platform API, workers, Kafka lag; Grafana dashboard
- [ ] **3.10** **REST/WebSocket scrapers** — validate scheduled ingestion from YAML into `raw_stream`

### Phase 4 — Enterprise & cloud **REQUIRED**

Goal: Secure multi-tenant SaaS deployable on AWS/K8s with billing and compliance.

- [ ] **4.1** Apply **Terraform** modules (MSK, EKS, RDS, ElastiCache); environment-specific tfvars
- [ ] **4.2** **ArgoCD GitOps** — Config Agent pushes manifests; automated sync
- [ ] **4.3** **Security hardening** — Kafka ACLs, mTLS, OpenSearch auth, PII redaction per `compliance.yaml`
- [ ] **4.4** **OAuth2 / RBAC** — replace API-key-only auth for tenant admins
- [ ] **4.5** **Marketplace v2** — Stripe (or similar), usage-based pricing, automated API key delivery
- [ ] **4.6** **Billing & metering** — scrape/compute/LLM usage → invoices
- [ ] **4.7** **FinOps agent loop** — Strategy Agent throttles scrape/compute/LLM from real spend
- [ ] **4.8** **Agent governance** — automated drift detection and rollback per `agent_governance.yaml`
- [ ] **4.9** **Secrets management** — Vault or AWS Secrets Manager (no plain `.env` in prod)
- [ ] **4.10** **Multi-region / DR** — Kafka mirroring, tenant data residency controls

### Phase 5 — Product expansion (after Phase 4)

- [ ] **5.1** Self-serve tenant portal — billing, usage analytics, plan upgrades in UI
- [ ] **5.2** Vertical plug-in framework — new industries beyond gaming, finance, accommodation
- [ ] **5.3** Trading bot — backtesting UI, risk management, optional broker integration
- [ ] **5.4** Marketplace data products — tenant-published datasets with revenue share
- [ ] **5.5** Mobile-responsive portal PWA + API rate-limit dashboard

---

## Completed Roadmap (Archive)

Near-term items finished in the first implementation sprint:

1. ~~**Wire Kafka Connect properly**~~ — Custom Connect image with JDBC + Elasticsearch connectors (`infra/kafka-connect/Dockerfile`); register via `make connectors`.
2. ~~**Real Selenium/Playwright**~~ — Headless Chromium in scraper image; Selenium WebDriver + Playwright engines.
3. ~~**Tenant quota middleware**~~ — Daily scrape limits, feature flags, `GET /usage` on Platform API.
4. ~~**Crawlee job status API**~~ — Live progress (`pages_crawled`, `progress_pct`, errors) synced to Redis + `scrape_jobs` table.
5. ~~**Avro on the wire**~~ — Schema Registry registration (`make schemas`); Confluent Avro serializers (`USE_AVRO=true`).
6. ~~**Control portal UI**~~ — `5-ui/` dashboard at http://localhost:8030 with burger sidebar, detail drawer, live logs.
7. ~~**Local dev pipeline**~~ — `make start-local`, `make start-pipeline`, `make pipeline-test` (scrape → Kafka → processed_stream).
8. ~~**Portal BFF APIs**~~ — `/api/pipeline`, `/api/logs/{name}`, graceful degradation when services down.

---

## Development Tips

- **Local dev (fastest):** `make start-local` → `make pipeline-test` → http://localhost:8030
- **Minimal restart (host):** `make stop-local && make start-local`
- **Minimal restart (Docker):** `docker compose restart platform-api ai-orchestrator`
- **Rebuild one service:** `docker compose up -d --build <service>`
- **Single-service logs:** `docker compose logs -f crawlee-worker` or `tail -f /tmp/speedflow-crawlee-worker.log`
- **DB shell:** `PGPASSWORD=adminpassword psql -h 127.0.0.1 -p 5433 -U admin -d platform_db`
- **Kafka consume:** `docker exec platform-kafka kafka-console-consumer --bootstrap-server kafka:9092 --topic processed_stream --from-beginning`
- **Reset volumes:** `docker compose down -v` (destroys all persisted data)
- **UI rebuild:** `cd 5-ui/portal-web && npm run build` then restart portal

---

## License

See repository license file (if present). This project is under active development; APIs and schemas may change.
