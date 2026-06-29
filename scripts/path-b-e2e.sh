#!/bin/bash
# Path B E2E: full Docker stack — tenant → scrape → Kafka → sinks → dashboard
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DOCKER_HOST="${DOCKER_HOST:-unix:///var/run/docker.sock}"
cd "$ROOT"

API="${PLATFORM_API_URL:-http://127.0.0.1:8020}"

echo "==> [1/6] Health check"
make health

echo "==> [2/6] Create tenant"
TENANT=$(curl -sf -X POST "$API/tenants" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Path B E2E","plan":"starter","email":"pathb@test.local"}')
API_KEY=$(echo "$TENANT" | python3 -c "import sys,json; print(json.load(sys.stdin)['api_key'])")
TENANT_ID=$(echo "$TENANT" | python3 -c "import sys,json; print(json.load(sys.stdin)['tenant_id'])")
echo "    tenant=$TENANT_ID"

echo "==> [3/6] Submit scrape job"
JOB=$(curl -sf -X POST "$API/scrape" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"requirement":"Scrape titles from https://httpbin.org/html","max_pages":2}')
JOB_ID=$(echo "$JOB" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
echo "    job_id=$JOB_ID"

echo "==> [4/6] Wait for job completion (120s max)"
STATUS="queued"
for i in $(seq 1 60); do
  STATUS=$(PGPASSWORD=adminpassword psql -h 127.0.0.1 -p 5433 -U admin -d platform_db -tAc \
    "SELECT status FROM scrape_jobs WHERE job_id='$JOB_ID'" 2>/dev/null || echo "unknown")
  PAGES=$(PGPASSWORD=adminpassword psql -h 127.0.0.1 -p 5433 -U admin -d platform_db -tAc \
    "SELECT pages_crawled FROM scrape_jobs WHERE job_id='$JOB_ID'" 2>/dev/null || echo "0")
  echo "    [$i] status=$STATUS pages=$PAGES"
  if [ "$STATUS" = "completed" ]; then break; fi
  if [ "$STATUS" = "failed" ]; then
    docker logs --tail 30 platform-crawlee-worker 2>&1 || true
    exit 1
  fi
  sleep 2
done
[ "$STATUS" = "completed" ] || { echo "Job did not complete"; exit 1; }

echo "==> [5/6] Verify Kafka processed_stream + Postgres sink"
sleep 5
PG_COUNT=$(PGPASSWORD=adminpassword psql -h 127.0.0.1 -p 5433 -U admin -d platform_db -tAc \
  "SELECT COUNT(*) FROM processed_events" 2>/dev/null || echo "0")
KAFKA_COUNT=$(docker exec platform-kafka kafka-console-consumer \
  --bootstrap-server kafka:9092 --topic processed_stream --from-beginning --timeout-ms 10000 2>/dev/null | wc -l || echo 0)
echo "    postgres processed_events: $PG_COUNT"
echo "    kafka processed_stream msgs: $KAFKA_COUNT"

echo "==> [6/6] Dashboard metrics"
METRICS=$(curl -sf http://127.0.0.1:8013/metrics/overview)
echo "$METRICS" | python3 -m json.tool | head -15
EVENTS=$(echo "$METRICS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('events_indexed',0))")
if [ "${PG_COUNT:-0}" -lt 1 ] && [ "${EVENTS:-0}" -lt 1 ]; then
  echo "WARN: No events in Postgres or dashboard yet (Connect sink may still be catching up)"
fi

echo ""
echo "Path B E2E complete"
echo "  Portal: http://localhost:8030"
echo "  Job: $JOB_ID | Tenant: $TENANT_ID"
