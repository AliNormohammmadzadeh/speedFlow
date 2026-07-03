variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Deployment environment (dev/staging/prod)"
  type        = string
  default     = "dev"
}

variable "vpc_id" {
  description = "VPC ID for SpeedFlow deployment"
  type        = string
  default     = ""
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for MSK/EKS/RDS/ElastiCache"
  type        = list(string)
  default     = []
}

variable "eks_auth_token" {
  description = "Token used by the kubernetes provider (from aws eks get-token)"
  type        = string
  default     = ""
  sensitive   = true
}

# --- MSK ---
variable "kafka_version" {
  type    = string
  default = "3.5.1"
}

variable "kafka_broker_instance_type" {
  type    = string
  default = "kafka.m5.large"
}

variable "kafka_broker_count" {
  type    = number
  default = 3
}

# --- EKS ---
variable "eks_kubernetes_version" {
  type    = string
  default = "1.29"
}

variable "eks_node_instance_types" {
  type    = list(string)
  default = ["m5.large"]
}

variable "eks_node_desired_size" {
  type    = number
  default = 3
}

# --- RDS ---
variable "rds_instance_class" {
  type    = string
  default = "db.m5.large"
}

variable "rds_allocated_storage" {
  type    = number
  default = 100
}

variable "rds_multi_az" {
  type    = bool
  default = false
}

variable "db_username" {
  type    = string
  default = "admin"
}

variable "db_password" {
  description = "RDS master password (inject via TF_VAR_db_password or secret manager)"
  type        = string
  default     = ""
  sensitive   = true
}

# --- ElastiCache ---
variable "redis_node_type" {
  type    = string
  default = "cache.m5.large"
}

variable "redis_num_cache_nodes" {
  type    = number
  default = 2
}
