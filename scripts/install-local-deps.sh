#!/bin/bash
# Install Python deps for host-run pipeline workers (uses same python3 as start-apps.sh)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
PIP="${PIP:-$PY -m pip}"

echo "Installing pipeline deps with $PY ..."
$PIP install -r "$ROOT/1-ingestion-edge/crawlee-service/requirements.txt" \
             -r "$ROOT/2-stream-compute/flink-ml-workers/requirements-processor.txt"

echo "Installing Playwright Chromium for JS crawls (crawlee_playwright) ..."
if $PY -m playwright install chromium 2>/dev/null; then
  echo "Playwright Chromium installed."
else
  echo "WARNING: Playwright Chromium install failed — crawlee_playwright jobs will fall back to Crawlee/HTTP."
fi

$PY -c "import confluent_kafka, crawlee, psycopg2; print('OK')"
$PY -c "
from pathlib import Path
import crawlee
print('crawlee', getattr(crawlee, '__version__', 'ok'))
cache = Path.home() / '.cache' / 'ms-playwright'
print('playwright_browsers', bool(any(cache.glob('chromium-*'))))
"
