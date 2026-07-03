aws_region  = "eu-west-1"
environment = "dev"

vpc_id             = "vpc-xxxxxxxx"
vpc_cidr           = "10.0.0.0/16"
private_subnet_ids = ["subnet-aaa", "subnet-bbb", "subnet-ccc"]

kafka_broker_instance_type = "kafka.t3.small"
kafka_broker_count         = 3

eks_kubernetes_version  = "1.29"
eks_node_instance_types = ["t3.large"]
eks_node_desired_size   = 2

rds_instance_class    = "db.t3.medium"
rds_allocated_storage = 50
rds_multi_az          = false

redis_node_type       = "cache.t3.small"
redis_num_cache_nodes = 1
