#!/bin/bash
# Path B (make up) binds the same host ports as Path A (make start-local).
# Stop host apps/pipeline workers before docker compose claims those ports.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

PORTS=(8000 8020 8010 8011 8012 8013 8014 8030)

echo "==> Stopping Path A host processes (if any)..."
bash "$ROOT/scripts/stop-local.sh" 2>/dev/null || true
sleep 1

busy=()
for port in "${PORTS[@]}"; do
  if ss -tlnH "sport = :$port" 2>/dev/null | grep -q .; then
    busy+=("$port")
  fi
done

if [ "${#busy[@]}" -gt 0 ]; then
  echo "ERROR: Port(s) still in use: ${busy[*]}" >&2
  echo "       Path B (make up) cannot bind these ports while another process holds them." >&2
  echo "       Stop the conflicting process, or run: make stop-local" >&2
  for port in "${busy[@]}"; do
    echo "       :$port -> $(ss -tlnpH "sport = :$port" 2>/dev/null || true)" >&2
  done
  exit 1
fi
