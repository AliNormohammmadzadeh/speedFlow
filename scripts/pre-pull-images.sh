#!/bin/bash
# Pre-pull base images to reduce make up failures from Docker Hub timeouts
set -euo pipefail
export DOCKER_HOST="${DOCKER_HOST:-unix:///var/run/docker.sock}"

IMAGES=(
  confluentinc/cp-kafka:7.6.0
  confluentinc/cp-schema-registry:7.6.0
  postgres:15
  redis:7-alpine
  opensearchproject/opensearch:2.11.1
  flink:1.18-scala_2.12-java11
  curlimages/curl:8.5.0
  python:3.11-slim
  node:20-alpine
)

echo "==> Pre-pulling ${#IMAGES[@]} base images..."
for img in "${IMAGES[@]}"; do
  echo "  pulling $img"
  docker pull "$img" || echo "  WARN: failed to pull $img (will retry on build)"
done
echo "==> Done"
