#!/bin/bash
REGISTRY="${SCHEMA_REGISTRY_URL:-http://localhost:8081}"
SCHEMA_DIR="${SCHEMA_DIR:-$(cd "$(dirname "$0")/.." && pwd)/schemas/avro}"

wait_for_registry() {
  echo "Waiting for Schema Registry at $REGISTRY..."
  for i in $(seq 1 30); do
    if curl -sf "$REGISTRY/subjects" > /dev/null 2>&1; then
      echo "Schema Registry is ready"
      return 0
    fi
    sleep 3
  done
  return 1
}

register_schema() {
  local subject=$1
  local file=$2
  echo "Registering $subject"
  python3 - <<PY
import json, urllib.request
schema = json.dumps(json.load(open("$file")))
body = json.dumps({"schema": schema}).encode()
req = urllib.request.Request(
    "$REGISTRY/subjects/$subject/versions",
    data=body,
    headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print("Registered", "$subject", resp.read().decode())
except Exception as e:
    print("Skip $subject:", e)
PY
}

wait_for_registry || exit 1
register_schema "raw_stream-value" "$SCHEMA_DIR/raw_event.avsc"
register_schema "processed_stream-value" "$SCHEMA_DIR/processed_event.avsc"
echo "Done"
