#!/bin/bash
# Wait for core SpeedFlow services after docker compose up
set -euo pipefail
export DOCKER_HOST="${DOCKER_HOST:-unix:///var/run/docker.sock}"

wait_http() {
  local url=$1 label=$2 max=${3:-60}
  echo -n "  waiting $label"
  for i in $(seq 1 "$max"); do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo " OK"
      return 0
    fi
    echo -n "."
    sleep 2
  done
  echo " TIMEOUT"
  return 1
}

echo "==> Waiting for SpeedFlow stack..."
wait_http http://127.0.0.1:8020/health "platform-api" 90
wait_http http://127.0.0.1:8000/health "orchestrator" 90
wait_http http://127.0.0.1:8010/health "aggregator" 60
wait_http http://127.0.0.1:8011/health "trading-bot" 60
wait_http http://127.0.0.1:8012/health "auditing" 60
wait_http http://127.0.0.1:8013/health "dashboard" 60
wait_http http://127.0.0.1:8014/health "marketplace" 60
wait_http http://127.0.0.1:8030/ "portal" 90
wait_http http://127.0.0.1:8083/connectors "kafka-connect" 120
echo "==> Stack ready"
