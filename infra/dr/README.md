# Multi-region & Disaster Recovery (Phase 4.10)

## Kafka mirroring
- `infra/dr/mm2.properties` configures MirrorMaker 2 to replicate `raw_stream*`,
  `processed_stream`, and `feedback_metrics` from the primary region (`us`) to the
  DR region (`eu`) using `IdentityReplicationPolicy` (stable topic names for clean
  failover). Flip `eu->us.enabled = true` for active-active.
- Deploy MM2 as a Kafka Connect cluster in each region (or `connect-mirror-maker`).
- RDS uses cross-region read replicas / automated backups; ElastiCache uses
  Multi-AZ (`infra/terraform/modules/{rds,elasticache}`).

## Tenant data residency
- Each tenant has a `region` (`tenants.region`). Region is validated at creation
  against `ALLOWED_REGIONS` (platform API) and returned in `TenantResponse` and
  `GET /residency`.
- Residency intent: a tenant's raw/processed data is produced to and consumed from
  its home-region cluster; MM2 replicates only for DR, not for serving cross-region
  reads, so data stays in-region under normal operation.
- `GET /residency` exposes the allowed regions and their cluster bootstrap
  endpoints so producers/consumers can be pinned to the tenant's region.

## Failover runbook (summary)
1. Promote the DR region MSK + RDS replica.
2. Repoint `KAFKA_BOOTSTRAP_SERVERS` / DB endpoints (via secrets provider) to DR.
3. ArgoCD syncs the platform workloads to the DR EKS cluster.
