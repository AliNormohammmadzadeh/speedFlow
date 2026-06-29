#!/bin/bash
# End-to-end test: tenant → scrape job → crawlee → raw_stream → processed_stream
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DOCKER_HOST="${DOCKER_HOST:-unix:///var/run/docker.sock}"

API="${PLATFORM_API_URL:-http://127.0.0.1:8020}"
KAFKA="${KAFKA_BOOTSTRAP_SERVERS:-localhost:29092}"

echo "==> Creating starter tenant..."
TENANT=$(curl -sf -X POST "$API/tenants" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Pipeline Test","plan":"starter","email":"pipeline@test.local"}')
API_KEY=$(echo "$TENANT" | python3 -c "import sys,json; print(json.load(sys.stdin)['api_key'])")
TENANT_ID=$(echo "$TENANT" | python3 -c "import sys,json; print(json.load(sys.stdin)['tenant_id'])")
echo "    tenant=$TENANT_ID"

echo "==> Submitting scrape job (httpbin, max 2 pages)..."
JOB=$(curl -sf -X POST "$API/scrape" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"requirement":"Scrape page titles from https://httpbin.org/html","max_pages":2}')
JOB_ID=$(echo "$JOB" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
echo "    job_id=$JOB_ID"

echo "==> Waiting for job completion (up to 90s)..."
for i in $(seq 1 45); do
  STATUS=$(PGPASSWORD=adminpassword psql -h 127.0.0.1 -p 5433 -U admin -d platform_db -tAc \
    "SELECT status FROM scrape_jobs WHERE job_id='$JOB_ID'" 2>/dev/null || echo "unknown")
  PAGES=$(PGPASSWORD=adminpassword psql -h 127.0.0.1 -p 5433 -U admin -d platform_db -tAc \
    "SELECT pages_crawled FROM scrape_jobs WHERE job_id='$JOB_ID'" 2>/dev/null || echo "0")
  echo "    [$i] status=$STATUS pages=$PAGES"
  if [ "$STATUS" = "completed" ]; then
    break
  fi
  if [ "$STATUS" = "failed" ]; then
    echo "Job failed — see /tmp/speedflow-crawlee-worker.log"
    exit 1
  fi
  sleep 2
done

if [ "$STATUS" != "completed" ]; then
  echo "Job did not complete in time"
  exit 1
fi

echo "==> Checking Kafka processed_stream..."
COUNT=$(docker compose -f "$ROOT/docker-compose.yml" exec -T kafka \
  kafka-console-consumer --bootstrap-server kafka:9092 \
  --topic processed_stream --from-beginning --timeout-ms 8000 2>/dev/null | wc -l || echo 0)
echo "    processed_stream messages: $COUNT"

if [ "${COUNT:-0}" -lt 1 ]; then
  echo "No processed events found — check /tmp/speedflow-stream-processor.log"
  exit 1
fi

echo ""
echo "Pipeline OK: scrape → crawlee → raw_stream → processed_stream"
echo "View job in UI: http://localhost:8030/ingestion"
