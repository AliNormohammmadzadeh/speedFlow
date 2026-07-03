aws_region  = "eu-west-1"
environment = "prod"

vpc_id             = "vpc-prodxxxx"
vpc_cidr           = "10.1.0.0/16"
private_subnet_ids = ["subnet-p-aaa", "subnet-p-bbb", "subnet-p-ccc"]

kafka_broker_instance_type = "kafka.m5.large"
kafka_broker_count         = 3

eks_kubernetes_version  = "1.29"
eks_node_instance_types = ["m5.large"]
eks_node_desired_size   = 4

rds_instance_class    = "db.m5.large"
rds_allocated_storage = 200
rds_multi_az          = true

redis_node_type       = "cache.m5.large"
redis_num_cache_nodes = 2
