output "kafka_bootstrap_brokers" {
  description = "MSK TLS bootstrap brokers"
  value       = module.msk.bootstrap_brokers_tls
}

output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "rds_endpoint" {
  value = module.rds.endpoint
}

output "redis_endpoint" {
  value = module.elasticache.primary_endpoint
}
