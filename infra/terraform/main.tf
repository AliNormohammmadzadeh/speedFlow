# SpeedFlow platform infrastructure — composes MSK, EKS, RDS, and ElastiCache
# modules. Each module is environment-parameterized via *.tfvars.

module "msk" {
  source = "./modules/msk"

  environment          = var.environment
  vpc_id               = var.vpc_id
  vpc_cidr             = var.vpc_cidr
  private_subnet_ids   = var.private_subnet_ids
  kafka_version        = var.kafka_version
  broker_instance_type = var.kafka_broker_instance_type
  broker_count         = var.kafka_broker_count
}

module "eks" {
  source = "./modules/eks"

  environment         = var.environment
  vpc_id              = var.vpc_id
  private_subnet_ids  = var.private_subnet_ids
  kubernetes_version  = var.eks_kubernetes_version
  node_instance_types = var.eks_node_instance_types
  node_desired_size   = var.eks_node_desired_size
}

module "rds" {
  source = "./modules/rds"

  environment        = var.environment
  vpc_id             = var.vpc_id
  vpc_cidr           = var.vpc_cidr
  private_subnet_ids = var.private_subnet_ids
  instance_class     = var.rds_instance_class
  allocated_storage  = var.rds_allocated_storage
  multi_az           = var.rds_multi_az
  db_username        = var.db_username
  db_password        = var.db_password
}

module "elasticache" {
  source = "./modules/elasticache"

  environment        = var.environment
  vpc_id             = var.vpc_id
  vpc_cidr           = var.vpc_cidr
  private_subnet_ids = var.private_subnet_ids
  node_type          = var.redis_node_type
  num_cache_nodes    = var.redis_num_cache_nodes
}
