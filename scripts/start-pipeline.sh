#!/bin/bash
# Start scrape → Kafka → stream-processor pipeline workers (host processes)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p /tmp/speedflow-pids

export DOCKER_HOST="${DOCKER_HOST:-unix:///var/run/docker.sock}"
export KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-localhost:29092}"
export SCHEMA_REGISTRY_URL="${SCHEMA_REGISTRY_URL:-http://127.0.0.1:8081}"
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6380}"
export POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
export POSTGRES_PORT="${POSTGRES_PORT:-5433}"
export POSTGRES_USER="${POSTGRES_USER:-admin}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-adminpassword}"
export POSTGRES_DB="${POSTGRES_DB:-platform_db}"
export USE_AVRO="${USE_AVRO:-true}"

start_worker() {
  local name=$1
  shift
  if [ -f "/tmp/speedflow-pids/$name.pid" ] && kill -0 "$(cat "/tmp/speedflow-pids/$name.pid")" 2>/dev/null; then
    echo "$name already running (pid $(cat /tmp/speedflow-pids/$name.pid))"
    return
  fi
  setsid bash -c "$*" > "/tmp/speedflow-$name.log" 2>&1 &
  echo $! > "/tmp/speedflow-pids/$name.pid"
  echo "Started $name (pid $!)"
}

echo "==> Ensuring Kafka topics exist..."
cd "$ROOT"
docker compose run --rm kafka-init 2>&1 | tail -3 || true

echo "==> Registering Avro schemas..."
SCHEMA_REGISTRY_URL="$SCHEMA_REGISTRY_URL" bash "$ROOT/scripts/register-schemas.sh" 2>&1 | tail -5

echo "==> Starting Crawlee worker..."
start_worker crawlee-worker \
  "cd '$ROOT/1-ingestion-edge/crawlee-service' && \
   PYTHONPATH='$ROOT/1-ingestion-edge/crawlee-service:$ROOT/1-ingestion-edge/scrapers' \
   KAFKA_BOOTSTRAP_SERVERS='$KAFKA_BOOTSTRAP_SERVERS' SCHEMA_REGISTRY_URL='$SCHEMA_REGISTRY_URL' \
   REDIS_URL='$REDIS_URL' POSTGRES_HOST='$POSTGRES_HOST' POSTGRES_PORT='$POSTGRES_PORT' \
   POSTGRES_USER='$POSTGRES_USER' POSTGRES_PASSWORD='$POSTGRES_PASSWORD' POSTGRES_DB='$POSTGRES_DB' \
   USE_AVRO='$USE_AVRO' exec python3 worker.py"

echo "==> Starting stream processor..."
start_worker stream-processor \
  "cd '$ROOT/2-stream-compute/flink-ml-workers' && \
   PYTHONPATH='$ROOT/2-stream-compute/flink-ml-workers:$ROOT/1-ingestion-edge/scrapers' \
   KAFKA_BOOTSTRAP_SERVERS='$KAFKA_BOOTSTRAP_SERVERS' SCHEMA_REGISTRY_URL='$SCHEMA_REGISTRY_URL' \
   USE_AVRO='$USE_AVRO' exec python3 stream_processor.py"

sleep 2
echo "==> Pipeline workers ready"
echo "    Logs: /tmp/speedflow-crawlee-worker.log, /tmp/speedflow-stream-processor.log"
