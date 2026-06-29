#!/bin/bash
# Build SpeedFlow images sequentially (avoids PyPI/Docker Hub parallel timeouts)
set -euo pipefail
export DOCKER_HOST="${DOCKER_HOST:-unix:///var/run/docker.sock}"
cd "$(dirname "$0")/.."

SERVICES=(
  kafka-connect
  stream-processor
  ml-service
  ai-orchestrator
  platform-api
  aggregator-backend
  trading-bot
  auditing-service
  dashboard
  marketplace
  crawlee-worker
  scraper-rest
  scraper-websocket
  scraper-selenium
  ui-portal
)

for svc in "${SERVICES[@]}"; do
  echo "==> Building $svc ..."
  for attempt in 1 2 3; do
    if docker compose build "$svc"; then
      echo "    OK $svc"
      break
    fi
    echo "    retry $attempt for $svc"
    sleep 10
    if [ "$attempt" -eq 3 ]; then
      echo "FAILED: $svc"
      exit 1
    fi
  done
done
echo "==> All images built"
