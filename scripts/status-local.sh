#!/bin/bash
# Show SpeedFlow host processes and Docker infra status
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DOCKER_HOST="${DOCKER_HOST:-unix:///var/run/docker.sock}"

echo "=== Host processes (SpeedFlow) ==="
printf "%-20s %-8s %-8s %s\n" "SERVICE" "PID" "PORT" "STATUS"
for entry in \
  "platform-api:8020" \
  "orchestrator:8000" \
  "portal:8030" \
  "crawlee-worker:-" \
  "stream-processor:-"; do
  name="${entry%%:*}"
  port="${entry##*:}"
  pidfile="/tmp/speedflow-pids/$name.pid"
  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    printf "%-20s %-8s %-8s %s\n" "$name" "$(cat "$pidfile")" "$port" "running"
  else
    printf "%-20s %-8s %-8s %s\n" "$name" "-" "$port" "stopped"
  fi
done

echo ""
echo "=== Docker infrastructure ==="
docker compose -f "$ROOT/docker-compose.yml" ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null | head -20

echo ""
echo "=== Quick health ==="
curl -sf http://127.0.0.1:8020/health >/dev/null && echo "platform-api: OK" || echo "platform-api: DOWN"
curl -sf http://127.0.0.1:8000/health >/dev/null && echo "orchestrator: OK" || echo "orchestrator: DOWN"
curl -sf http://127.0.0.1:8030/ >/dev/null && echo "portal: OK" || echo "portal: DOWN"
redis-cli -p 6380 ping 2>/dev/null | grep -q PONG && echo "redis: OK" || echo "redis: DOWN"
curl -sf http://127.0.0.1:8081/subjects >/dev/null && echo "schema-registry: OK" || echo "schema-registry: DOWN"
