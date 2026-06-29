#!/bin/bash
# Stop SpeedFlow host processes started by start-apps.sh / start-pipeline.sh
set -euo pipefail

for name in portal platform-api orchestrator crawlee-worker stream-processor; do
  pidfile="/tmp/speedflow-pids/$name.pid"
  if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "Stopped $name (pid $pid)"
    fi
    rm -f "$pidfile"
  fi
done

fuser -k 8020/tcp 8000/tcp 8030/tcp 2>/dev/null || true
echo "Done."
