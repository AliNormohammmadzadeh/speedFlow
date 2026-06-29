#!/bin/bash
# Install Python deps for host-run pipeline workers (uses same python3 as start-apps.sh)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
PIP="${PIP:-$PY -m pip}"

echo "Installing pipeline deps with $PY ..."
$PIP install -r "$ROOT/1-ingestion-edge/crawlee-service/requirements.txt" \
             -r "$ROOT/2-stream-compute/flink-ml-workers/requirements-processor.txt"
$PY -c "import confluent_kafka, crawlee, psycopg2; print('OK')"
