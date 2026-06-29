# AGENTS.md

## Cursor Cloud specific instructions

SpeedFlow is a layered monorepo (one product, 6 numbered layers). The reliable dev path is
**Path A** in `README.md`: infra in Docker, the API/orchestrator/portal + pipeline workers on the
host. Standard commands live in the `Makefile` and `README.md` — use those rather than duplicating.
The cloud VM update script already refreshes Python deps (`pip ... --break-system-packages`) and
`5-ui/portal-web` node deps; do not re-run dependency installs unless something is missing.

### Starting the stack (per session)
- **Docker must be started manually each session** — it is NOT started by the update script.
  Run `sudo dockerd > /tmp/dockerd.log 2>&1 &` then `sudo chmod 666 /var/run/docker.sock`.
  Docker 29 is configured for `fuse-overlayfs` with the containerd snapshotter disabled
  (`/etc/docker/daemon.json`); `iptables` is set to legacy mode. These configs persist in the snapshot.
- **Build the UI before starting the portal:** `npm --prefix 5-ui/portal-web run build`. `portal-api`
  serves `5-ui/portal-web/dist`, which is gitignored and not produced by the update script.
- First run only: `cp .env.example .env` (LLM keys optional — agents fall back to rule-based mode).
- Then `make start-local` (infra + host apps + pipeline), verify with `make pipeline-test`, open the
  portal at http://localhost:8030. Use `make status` / `make stop-local` to manage host processes.

### Non-obvious caveats
- **confluent-kafka extras:** `requirements.txt` pins only `confluent-kafka>=2.3.0`, but the modern
  release needs `authlib`, `attrs`, and avro extras for its schema-registry client. The update script
  installs `confluent-kafka[avro,schemaregistry]` + `authlib`. If pipeline workers crash with
  `ModuleNotFoundError: authlib` / `attrs`, reinstall those.
- **Host worker uses a fallback crawler:** the crawlee worker logs `Crawlee not installed — fallback
  HTTP crawler will be used`. This is expected on the host and the scrape→Kafka pipeline still works
  for static pages (e.g. httpbin).
- **Shifted host ports:** Postgres `5433`, Redis `6380`, Kafka `29092` (Docker-internal ports differ).
  `psql` and `redis-cli` are installed for the host scripts.
- **Expected "down/degraded" services:** in Path A the serving apps (8010–8014), Flink, ML service,
  Kafka Connect, and Airflow are not started, so the portal shows them down/degraded — this is normal.
- Host process logs are at `/tmp/speedflow-*.log`; PID files in `/tmp/speedflow-pids/`.

### Testing
- There are **no unit tests or linters** configured. The only automated check is the end-to-end
  `make pipeline-test` (tenant → scrape → `raw_stream` → `processed_stream`).
