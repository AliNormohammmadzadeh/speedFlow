#!/bin/bash
# Start SpeedFlow locally (infra in Docker + apps on host)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export DOCKER_HOST="${DOCKER_HOST:-unix:///var/run/docker.sock}"

echo "==> Starting infrastructure (Docker)..."
docker compose up -d postgres redis elasticsearch kafka schema-registry 2>&1 | tail -5

echo "==> Waiting for Kafka to be healthy..."
for i in $(seq 1 30); do
  state=$(docker inspect -f '{{.State.Health.Status}}' platform-kafka 2>/dev/null || echo "starting")
  [ "$state" = "healthy" ] && break
  sleep 2
done

echo "==> Ensuring Kafka topics exist (kafka-init)..."
docker compose run --rm kafka-init 2>&1 | tail -3

echo "==> Registering Avro schemas..."
docker compose up schema-init 2>&1 | tail -3

echo "==> Waiting for Postgres..."
for i in $(seq 1 30); do
  PGPASSWORD=adminpassword psql -h 127.0.0.1 -p 5433 -U admin -d platform_db -c 'SELECT 1' >/dev/null 2>&1 && break
  sleep 2
done

bash "$ROOT/scripts/stop-local.sh" 2>/dev/null || true
sleep 1

bash "$ROOT/scripts/start-apps.sh"
bash "$ROOT/scripts/start-pipeline.sh"
echo ""
echo "Portal: http://localhost:8030"
echo "Logs: /tmp/speedflow-*.log"
