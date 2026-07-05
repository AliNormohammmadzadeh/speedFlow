#!/bin/bash
# Start serving-layer apps on the host for local dev (Path A).
# These back the portal's Phase 5 features (Trading backtesting/broker, Marketplace datasets).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p /tmp/speedflow-pids

export KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-localhost:29092}"
export SCHEMA_REGISTRY_URL="${SCHEMA_REGISTRY_URL:-http://127.0.0.1:8081}"
export POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
export POSTGRES_PORT="${POSTGRES_PORT:-5433}"
export POSTGRES_USER="${POSTGRES_USER:-admin}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-adminpassword}"
export POSTGRES_DB="${POSTGRES_DB:-platform_db}"
export USE_AVRO="${USE_AVRO:-true}"
export AI_ORCHESTRATOR_URL="${AI_ORCHESTRATOR_URL:-http://127.0.0.1:8000}"

start_svc() {
  local name=$1 port=$2
  shift 2
  if [ -f "/tmp/speedflow-pids/$name.pid" ] && kill -0 "$(cat "/tmp/speedflow-pids/$name.pid")" 2>/dev/null; then
    echo "$name already running (pid $(cat /tmp/speedflow-pids/$name.pid))"
    return
  fi
  setsid bash -c "$*" > "/tmp/speedflow-$name.log" 2>&1 &
  echo $! > "/tmp/speedflow-pids/$name.pid"
  echo "Started $name on :$port (pid $!)"
}

# Trading bot (:8011) — live signals + backtesting + risk + mock broker.
start_svc trading-bot 8011 \
  "cd '$ROOT/3-serving-api/trading-bot' && \
   KAFKA_BOOTSTRAP_SERVERS='$KAFKA_BOOTSTRAP_SERVERS' SCHEMA_REGISTRY_URL='$SCHEMA_REGISTRY_URL' \
   USE_AVRO='$USE_AVRO' AI_ORCHESTRATOR_URL='$AI_ORCHESTRATOR_URL' \
   exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8011"

# Marketplace (:8014) — data products + tenant-published datasets + revenue share.
start_svc marketplace 8014 \
  "cd '$ROOT/3-serving-api/marketplace' && \
   POSTGRES_HOST='$POSTGRES_HOST' POSTGRES_PORT='$POSTGRES_PORT' POSTGRES_USER='$POSTGRES_USER' \
   POSTGRES_PASSWORD='$POSTGRES_PASSWORD' POSTGRES_DB='$POSTGRES_DB' \
   AI_ORCHESTRATOR_URL='$AI_ORCHESTRATOR_URL' \
   exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8014"

sleep 4
curl -sf http://127.0.0.1:8011/health >/dev/null && echo "  trading-bot OK" || echo "  trading-bot starting…"
curl -sf http://127.0.0.1:8014/health >/dev/null && echo "  marketplace OK" || echo "  marketplace starting…"
echo "Logs: /tmp/speedflow-trading-bot.log, /tmp/speedflow-marketplace.log"
