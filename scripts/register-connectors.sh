#!/bin/sh
# Register Kafka Connect sink connectors after Connect is healthy
set -eu

CONNECT_URL="${KAFKA_CONNECT_URL:-http://localhost:8083}"
CONNECTOR_DIR="${CONNECTOR_DIR:-/connectors}"

wait_for_connect() {
  echo "Waiting for Kafka Connect at $CONNECT_URL..."
  i=1
  while [ "$i" -le 40 ]; do
    if curl -sf "$CONNECT_URL/connectors" >/dev/null 2>&1; then
      echo "Kafka Connect is ready"
      return 0
    fi
    sleep 5
    i=$((i + 1))
  done
  echo "Kafka Connect not ready"
  return 1
}

register_connector() {
  name=$1
  config_file=$2
  echo "Registering connector: $name"
  curl -sf -X PUT "$CONNECT_URL/connectors/$name/config" \
    -H "Content-Type: application/json" \
    -d @"$config_file" || echo "Failed to register $name"
}

wait_for_connect || exit 1

# Postgres JDBC sink: processed_stream -> processed_events table.
register_connector "postgres-sink" "$CONNECTOR_DIR/postgres-sink.json"

# OpenSearch indexing is handled app-side by the stream processor
# (the Confluent Elasticsearch sink rejects OpenSearch's version banner).
# Set REGISTER_ES_SINK=true to also try the Connect Elasticsearch sink.
if [ "${REGISTER_ES_SINK:-false}" = "true" ]; then
  register_connector "elasticsearch-sink" "$CONNECTOR_DIR/elasticsearch-sink.json"
fi

echo "Connectors registered"
