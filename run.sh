#!/usr/bin/env bash
# SpeedFlow — one-command local bring-up.
#
# Starts infrastructure (Postgres, Redis, Kafka, Schema Registry, OpenSearch) in
# Docker, installs host dependencies, builds the control-portal UI, and runs the
# platform API, AI orchestrator, portal, pipeline workers and serving apps on the
# host. Idempotent: safe to re-run.
#
#   ./run.sh          # bring everything up
#   ./run.sh stop     # stop the host processes (infra keeps running in Docker)
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ "${1:-}" = "stop" ]; then
  make stop-local
  exit 0
fi

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }

# 1. Make sure the Docker daemon is reachable (best-effort auto-start on Linux VMs).
if ! docker info >/dev/null 2>&1; then
  if command -v dockerd >/dev/null 2>&1; then
    step "Starting Docker daemon"
    sudo dockerd >/tmp/dockerd.log 2>&1 &
    for _ in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 1; done
    sudo chmod 666 /var/run/docker.sock 2>/dev/null || true
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running. Please start Docker Desktop / the Docker daemon and re-run." >&2
    exit 1
  fi
fi

# 2. Config file.
if [ ! -f .env ]; then
  step "Creating .env from .env.example"
  cp .env.example .env
fi

# 3. Host Python dependencies for the API, orchestrator and pipeline workers.
step "Installing host Python dependencies"
python3 -m pip install -q \
  -r requirements.txt \
  -r 1-ingestion-edge/crawlee-service/requirements.txt \
  -r 2-stream-compute/flink-ml-workers/requirements-processor.txt \
  authlib

# 4. Control-portal UI (dependencies + production build served by portal-api).
step "Building control portal UI"
npm --prefix 5-ui/portal-web install --no-audit --no-fund
npm --prefix 5-ui/portal-web run build

# 5. Infra (Docker) + apps + pipeline workers + serving apps (host).
step "Starting infrastructure + host services"
make start-local
make start-serving

cat <<'EOF'

SpeedFlow is up.

  Control Portal      http://localhost:8030
  Pipeline Canvas     http://localhost:8030/canvas
  Platform API        http://localhost:8020
  AI Orchestrator     http://localhost:8000

Verify the end-to-end pipeline:  make pipeline-test
Stop host processes:             ./run.sh stop   (or: make stop-local)
EOF
