#!/bin/bash
# Kafka ACLs for SpeedFlow (task 4.3). Apply against a SASL/mTLS-enabled broker
# (e.g. MSK with SASL_SCRAM or TLS client auth). On MSK, principals are the
# SCRAM usernames or the mTLS certificate CN (User:CN=...).
#
# Usage: BOOTSTRAP=broker:9094 CMD_CONFIG=client.properties bash kafka-acls.sh
set -euo pipefail

BOOTSTRAP="${BOOTSTRAP:-kafka:9092}"
CMD_CONFIG="${CMD_CONFIG:-/opt/kafka/config/client.properties}"
ACL="kafka-acls --bootstrap-server $BOOTSTRAP --command-config $CMD_CONFIG"

# Producers: scrapers + crawlee worker write raw_stream*
for principal in "User:scraper" "User:crawlee-worker"; do
  $ACL --add --allow-principal "$principal" --producer --topic 'raw_stream' --resource-pattern-type prefixed
done

# Stream processor: read raw_stream*, write processed_stream
$ACL --add --allow-principal "User:stream-processor" --consumer --group speedflow-stream-processor --topic 'raw_stream' --resource-pattern-type prefixed
$ACL --add --allow-principal "User:stream-processor" --producer --topic processed_stream

# Kafka Connect sinks: read processed_stream
$ACL --add --allow-principal "User:kafka-connect" --consumer --group platform-connect --topic processed_stream

# Trading bot: read processed_stream
$ACL --add --allow-principal "User:trading-bot" --consumer --group trading-bot --topic processed_stream

echo "ACLs applied. Deny-by-default is enforced by broker setting allow.everyone.if.no.acl.found=false"
