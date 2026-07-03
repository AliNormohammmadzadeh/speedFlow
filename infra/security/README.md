# SpeedFlow Security Hardening (Phase 4.3)

Implements the controls declared in `config/security/compliance.yaml`.

## PII redaction (implemented + enforced)
- `2-stream-compute/flink-ml-workers/pii.py` scans and redacts `redact_fields`
  (`email, phone, ssn, credit_card`) plus value-pattern matches from event
  payloads **before** they are written to Kafka `processed_stream`, Postgres, and
  OpenSearch.
- Applied in `stream_processor.process_event()`; each processed event records
  `pii_redacted` (count). Toggle via `PII_REDACTION_ENABLED` / `REDACT_FIELDS` /
  `PII_BLOCK_ON_DETECT`.

## Kafka ACLs + mTLS/SASL (config)
- MSK is provisioned with `encryption_in_transit.client_broker = TLS` and
  `client_authentication` (SASL/SCRAM + TLS/mTLS) in
  `infra/terraform/modules/msk/main.tf`.
- `infra/security/kafka-acls.sh` applies least-privilege ACLs per service
  principal (producers → `raw_stream*`, stream processor → consume `raw_stream*` /
  produce `processed_stream`, Connect/trading-bot → consume `processed_stream`).
- Enforce deny-by-default with broker `allow.everyone.if.no.acl.found=false`.

## OpenSearch authentication
- Local dev disables the security plugin (`plugins.security.disabled=true`) per
  `compliance.yaml.local_dev_overrides`.
- For prod, enable the security plugin (remove the override), provision users/roles,
  and set `ELASTICSEARCH_URL` credentials for the stream processor + dashboard.
  See `docker-compose.opensearch-secure.yml` for a hardened single-node example.

## Encryption at rest
- RDS (`storage_encrypted = true`) and ElastiCache (`at_rest_encryption_enabled`,
  `transit_encryption_enabled`) in the Terraform modules.
