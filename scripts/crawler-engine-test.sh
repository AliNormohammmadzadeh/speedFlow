#!/usr/bin/env bash
# Test both crawl engines: fallback (HTTP) and crawlee (BeautifulSoup).
# Optional third case: crawlee_playwright when Chromium is installed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

API="${PLATFORM_API_URL:-http://localhost:8020}"
KEY="${SCRAPE_API_KEY:-}"

if [[ -z "$KEY" ]]; then
  KEY=$(curl -sf "$API/tenants" -H "X-API-Key: sf_demo" 2>/dev/null | python3 -c "
import sys, json
try:
  d=json.load(sys.stdin)
  print(d[0]['api_key'] if d else '')
except Exception:
  print('')
" 2>/dev/null || true)
fi

if [[ -z "$KEY" ]]; then
  echo "Creating starter test tenant..."
  RESP=$(curl -sf -X POST "$API/tenants" -H "Content-Type: application/json" \
    -d '{"name":"Engine Test Co","plan":"pro","email":"engine-test@demo.local"}')
  KEY=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['api_key'])")
fi

submit() {
  local engine="$1" req="$2"
  curl -sf -X POST "$API/scrape" \
    -H "X-API-Key: $KEY" \
    -H "Content-Type: application/json" \
    -d "{\"requirement\":\"$req\",\"url\":\"https://example.com\",\"max_pages\":1,\"crawler_engine\":\"$engine\"}"
}

wait_job() {
  local jid="$1"
  for _ in $(seq 1 45); do
    ROW=$(curl -sf "$API/scrape/$jid" -H "X-API-Key: $KEY")
    STATUS=$(echo "$ROW" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))")
    PAGES=$(echo "$ROW" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('pages_crawled',0))")
    ENGINE=$(echo "$ROW" | python3 -c "import sys,json; d=json.load(sys.stdin); p=d.get('plan') or {}; print(p.get('crawler_engine','?'))")
    if [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]]; then
      echo "  status=$STATUS pages=$PAGES planned_engine=$ENGINE"
      [[ "$STATUS" == "completed" && "$PAGES" -gt 0 ]]
      return
    fi
    sleep 2
  done
  echo "  TIMEOUT waiting for $jid"
  return 1
}

echo "==> Crawler engine matrix (API=$API)"
PASS=0
FAIL=0

for ENGINE in fallback crawlee; do
  echo "-- engine=$ENGINE"
  JOB=$(submit "$ENGINE" "Scrape the main heading from example.com")
  JID=$(echo "$JOB" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
  echo "  job_id=$JID"
  if wait_job "$JID"; then PASS=$((PASS+1)); echo "  PASS"; else FAIL=$((FAIL+1)); echo "  FAIL"; fi
done

PW=$(python3 -c "
from pathlib import Path
print('yes' if any((Path.home()/'.cache'/'ms-playwright').glob('chromium-*')) else 'no')
" 2>/dev/null || echo no)

if [[ "$PW" == "yes" ]]; then
  echo "-- engine=crawlee_playwright"
  JOB=$(submit "crawlee_playwright" "Scrape the JavaScript-rendered page title from https://example.com")
  JID=$(echo "$JOB" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
  echo "  job_id=$JID"
  if wait_job "$JID"; then PASS=$((PASS+1)); echo "  PASS"; else FAIL=$((FAIL+1)); echo "  FAIL"; fi
else
  echo "-- engine=crawlee_playwright SKIPPED (run: bash scripts/install-local-deps.sh)"
fi

echo "==> Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]
