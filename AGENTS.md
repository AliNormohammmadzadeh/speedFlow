# AGENTS.md

## Cursor Cloud specific instructions

SpeedFlow is a layered monorepo (one product, 6 numbered layers). The reliable dev path is
**Path A** in `README.md`: infra in Docker, the API/orchestrator/portal + pipeline workers on the
host. Standard commands live in the `Makefile` and `README.md` — use those rather than duplicating.
The cloud VM update script already refreshes host Python deps and `5-ui/portal-web` node deps; do not
re-run dependency installs unless something is missing.

### Starting the stack (per session)
- **Docker must be started manually each session** — it is NOT started by the update script.
  Run `sudo dockerd > /tmp/dockerd.log 2>&1 &` (a tmux session is convenient) then
  `sudo chmod 666 /var/run/docker.sock`. The daemon config persists in the snapshot:
  `/etc/docker/daemon.json` uses `fuse-overlayfs` with the containerd snapshotter disabled
  (required for Docker 29 in this VM), and `iptables` is set to legacy mode.
- **Build the UI before starting the portal:** `npm --prefix 5-ui/portal-web run build`. `portal-api`
  serves `5-ui/portal-web/dist`, which is gitignored and NOT produced by the update script.
- First run only: `cp .env.example .env` (LLM keys optional — agents fall back to rule-based mode).
- Then `make start-local` (infra + host apps + pipeline). Verify with `make status`, then run a
  scrape (see Testing). Open the portal at http://localhost:8030. Use `make stop-local` to stop
  host processes; infra keeps running in Docker.

### Non-obvious caveats
- **confluent-kafka extras:** `requirements.txt` pins only `confluent-kafka>=2.3.0`, but the
  schema-registry Avro client also needs the `avro,schemaregistry` extras plus `authlib`/`attrs`.
  The update script installs `confluent-kafka[avro,schemaregistry]` + `authlib`. If pipeline workers
  crash with `ModuleNotFoundError: authlib`/`attrs`/`fastavro`, reinstall those.
- **Host worker uses a fallback crawler:** the crawlee worker logs `Crawlee not installed — fallback
  HTTP crawler will be used` even when `crawlee` is importable (Playwright browsers are not installed
  on the host). This is expected; the scrape→Kafka pipeline still works for static pages.
- **Plan routing:** `starter` tenants publish to `raw_stream` (which the stream processor consumes →
  `processed_stream`). `pro`/`enterprise` tenants get a **dedicated** topic (`raw_stream_<tenant>`),
  which the default host stream processor does NOT consume — use a `starter` tenant to see events
  land in `processed_stream`.
- **Shifted host ports:** Postgres `5433`, Redis `6380`, Kafka `29092` (Docker-internal ports differ:
  5432/6379/9092). `psql` and `redis-cli` are installed for the host scripts.
- **Expected "down/degraded" services:** in Path A the serving apps (8010–8014), Flink, ML service,
 Kafka Connect, and Airflow are not started, so the portal shows them down/degraded — this is normal.
- **Phase 5 Trading & Marketplace UI need serving apps on host:** the portal **Trading** page and the
 **Applications → Publish/Sell Datasets** widget call the trading bot (:8011) and marketplace (:8014).
 In Path A run `make start-serving` to start them on the host (stopped by `make stop-local`). The
 trading-bot Kafka consumer uses `localhost:29092`; if Kafka isn't reachable it logs and retries —
 backtesting/risk/broker endpoints still work without live signals.
- Host process logs are at `/tmp/speedflow-*.log`; PID files in `/tmp/speedflow-pids/`.

### Testing
- There are **no unit tests or linters** configured. The only automated check is the end-to-end
  `make pipeline-test` (starter tenant → scrape → `raw_stream` → `processed_stream`). Note it targets
  `https://httpbin.org/html`, which is sometimes rate-limited (503); if so the pipeline is still
  healthy — re-run, or submit a scrape against a reliable URL (e.g. `https://example.com`) via the
  Platform API and confirm an event appears on `processed_stream`.
