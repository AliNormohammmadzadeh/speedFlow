#!/bin/bash
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p /tmp/speedflow-pids

start_svc() {
  local name=$1 port=$2
  shift 2
  if [ -f "/tmp/speedflow-pids/$name.pid" ] && kill -0 "$(cat /tmp/speedflow-pids/$name.pid)" 2>/dev/null; then
    echo "$name already running"
    return
  fi
  setsid bash -c "$*" > /tmp/speedflow-$name.log 2>&1 &
  echo $! > "/tmp/speedflow-pids/$name.pid"
  echo "Started $name on :$port"
}

start_svc platform-api 8020 \
  "cd '$ROOT/4-platform-api' && POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 REDIS_URL=redis://127.0.0.1:6380 PLANS_CONFIG='$ROOT/config/subscriptions/plans.yaml' AI_ORCHESTRATOR_URL=http://127.0.0.1:8000 exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8020"

start_svc orchestrator 8000 \
  "cd '$ROOT/0-ai-intelligence' && PYTHONPATH='$ROOT/0-ai-intelligence' REDIS_URL=redis://127.0.0.1:6380 GITOPS_REPO_PATH='$ROOT/gitops-output' exec python3 -m uvicorn orchestrator.main:app --host 0.0.0.0 --port 8000"

start_svc portal 8030 \
  "cd '$ROOT/5-ui/portal-api' && PORTAL_STATIC_DIR='$ROOT/5-ui/portal-web/dist' POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 REDIS_URL=redis://127.0.0.1:6380 PLATFORM_API_URL=http://127.0.0.1:8020 AI_ORCHESTRATOR_URL=http://127.0.0.1:8000 AGGREGATOR_URL=http://127.0.0.1:8010 TRADING_BOT_URL=http://127.0.0.1:8011 AUDITING_URL=http://127.0.0.1:8012 DASHBOARD_URL=http://127.0.0.1:8013 MARKETPLACE_URL=http://127.0.0.1:8014 ML_SERVICE_URL=http://127.0.0.1:8090 KAFKA_CONNECT_URL=http://127.0.0.1:8083 ELASTICSEARCH_URL=http://127.0.0.1:9200 FLINK_URL=http://127.0.0.1:8082 SCHEMA_REGISTRY_URL=http://127.0.0.1:8081 exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8030"

sleep 4
curl -sf http://127.0.0.1:8020/health && echo "  platform-api OK"
curl -sf http://127.0.0.1:8000/health && echo "  orchestrator OK"
curl -sf http://127.0.0.1:8030/ >/dev/null && echo "  portal UI OK"
