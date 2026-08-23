#!/bin/bash
# Test Novada proxy connectivity and scrape Thunderpick via Pro tenant.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

API="${PLATFORM_API_URL:-http://127.0.0.1:8020}"
TARGET_URL="${1:-https://thunderpick.io/esports/dota-2/the-international-2026/9947/iron-wing-vs-team-spirit/2499230}"

if [ -z "${CRAWLEE_PROXY_URL:-}" ]; then
  echo "CRAWLEE_PROXY_URL is not set in .env"
  exit 1
fi

echo "==> Testing proxy with ipinfo.novada.pro..."
PROXY_HOSTPORT=$(python3 - <<'PY'
import os
from urllib.parse import urlparse
u = urlparse(os.environ["CRAWLEE_PROXY_URL"])
print(f"{u.hostname}:{u.port}")
PY
)
PROXY_AUTH=$(python3 - <<'PY'
import os
from urllib.parse import urlparse
u = urlparse(os.environ["CRAWLEE_PROXY_URL"])
print(f"{u.username}:{u.password}")
PY
)
curl -sf -x "$PROXY_HOSTPORT" -U "$PROXY_AUTH" ipinfo.novada.pro | head -c 200
echo ""
echo "    proxy OK"

echo "==> Creating pro tenant..."
TENANT=$(curl -sf -X POST "$API/tenants" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Proxy Scrape Test","plan":"pro","email":"proxy-test@demo.local"}')
API_KEY=$(echo "$TENANT" | python3 -c "import sys,json; print(json.load(sys.stdin)['api_key'])")
TENANT_ID=$(echo "$TENANT" | python3 -c "import sys,json; print(json.load(sys.stdin)['tenant_id'])")
echo "    tenant=$TENANT_ID"

echo "==> Submitting Thunderpick scrape (Playwright + proxy)..."
JOB=$(curl -sf -X POST "$API/scrape" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "$(python3 - <<PY
import json
print(json.dumps({
    "requirement": "Scrape match odds and team names from Thunderpick esports page via proxy",
    "url": "$TARGET_URL",
    "max_pages": 1,
    "crawler_engine": "crawlee_playwright",
    "use_proxy": True,
    "vertical": "esports",
}))
PY
)")
JOB_ID=$(echo "$JOB" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
echo "$JOB" | python3 -m json.tool | head -30
echo "    job_id=$JOB_ID"

echo "==> Waiting for job completion (up to 120s)..."
for i in $(seq 1 60); do
  ROW=$(PGPASSWORD=adminpassword psql -h 127.0.0.1 -p 5433 -U admin -d platform_db -tAc \
    "SELECT status || '|' || COALESCE(pages_crawled::text,'0') || '|' || COALESCE(error_message,'') FROM scrape_jobs WHERE job_id='$JOB_ID'" 2>/dev/null || echo "unknown|0|")
  STATUS="${ROW%%|*}"
  REST="${ROW#*|}"
  PAGES="${REST%%|*}"
  ERR="${REST#*|}"
  echo "    [$i] status=$STATUS pages=$PAGES"
  if [ "$STATUS" = "completed" ]; then
    echo ""
    echo "Proxy scrape OK: job=$JOB_ID pages=$PAGES"
    echo "View: http://localhost:8030/ingestion/jobs/$JOB_ID"
    exit 0
  fi
  if [ "$STATUS" = "failed" ]; then
    echo "Job failed: $ERR"
    echo "See /tmp/speedflow-crawlee-worker.log"
    exit 1
  fi
  sleep 2
done

echo "Job did not complete in time — see /tmp/speedflow-crawlee-worker.log"
exit 1
