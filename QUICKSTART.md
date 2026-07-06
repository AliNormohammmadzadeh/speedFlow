# SpeedFlow — Quick Start

Get the whole platform running with a single command, then explore it in the
control portal (including the new **Pipeline Canvas** — an interactive, real-time
React Flow visualization of the data pipeline).

> For the full architecture, per-layer docs and the Docker-only path, see
> [`README.md`](./README.md).

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Docker + Docker Compose v2 | Runs infra: Postgres, Redis, Kafka, Schema Registry, OpenSearch |
| Python 3.10+ | Runs the API, orchestrator and pipeline workers on the host |
| Node.js 18+ / npm | Builds the React control portal |
| 8 GB+ RAM | Comfortable headroom for the infra containers |

No API keys are required — the AI agents fall back to deterministic, rule-based
logic when `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` are absent.

---

## Run it (one command)

```bash
./run.sh
```

That script is idempotent and will:

1. Start the Docker daemon (best-effort) and create `.env` from `.env.example`.
2. Install host Python dependencies.
3. Install portal UI dependencies and build the static bundle.
4. Bring up infra in Docker and start the API, orchestrator, portal, pipeline
   workers and serving apps on the host.

When it finishes, open the portal:

| Service | URL |
|---------|-----|
| **Control Portal** | http://localhost:8030 |
| **Pipeline Canvas** | http://localhost:8030/canvas |
| Platform API | http://localhost:8020 |
| AI Orchestrator | http://localhost:8000 |

Stop the host processes (infra keeps running in Docker):

```bash
./run.sh stop        # equivalent to: make stop-local
```

---

## Verify it works

Run the built-in end-to-end pipeline test (creates a tenant, submits a scrape,
and confirms events reach Kafka `processed_stream`):

```bash
make pipeline-test
```

Or do it by hand from the portal **Tenants** page: create a tenant, copy the API
key into the *Submit Scrape Job* form, and submit a scrape of
`https://example.com`. Then watch the flow light up on the **Pipeline Canvas**.

---

## The Pipeline Canvas

`http://localhost:8030/canvas` renders the platform as an interactive graph:

- **Auto-layout** (left → right) via `dagre` — no manual dragging.
- **Custom Bento-card nodes** with a type icon, live health badge, and a metric
  sparkline.
- **Animated edges** whose particle speed/thickness reflects data volume.
- **MiniMap** + **Controls**, a dotted background, live health polling every 5s.

See [`5-ui/portal-web/README.md`](./5-ui/portal-web/README.md) for the UI dev
workflow (hot-reload dev server, component layout, etc.).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Docker is not running` | Start Docker Desktop / the daemon, then re-run `./run.sh`. |
| Portal shows some services *down* | Expected in local mode — only the core pipeline + trading/marketplace run on the host. See `README.md`. |
| Ports already in use | `make stop-local` then re-run. Host ports: API `8020`, portal `8030`, Postgres `5433`, Redis `6380`, Kafka `29092`. |
