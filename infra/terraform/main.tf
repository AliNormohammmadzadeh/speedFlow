terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "eu-west-1"
}

variable "environment" {
  default = "dev"
}

variable "kafka_partitions" {
  default = 3
}

variable "flink_parallelism" {
  default = 4
}

variable "scraper_replicas" {
  default = 1
}

# MSK Kafka cluster (scalable by Config Agent)
resource "aws_msk_cluster" "speedflow" {
  cluster_name           = "speedflow-kafka-${var.environment}"
  kafka_version          = "3.5.1"
  number_of_broker_nodes = 3

  broker_node_group_info {
    instance_type  = "kafka.m5.large"
    client_subnets = var.private_subnet_ids
    security_groups = [aws_security_group.kafka.id]

    storage_info {
      ebs_storage_info {
        volume_size = 100
      }
    }
  }

  tags = {
    Project     = "speedflow"
    ManagedBy   = "terraform"
    Environment = var.environment
  }
}

resource "aws_security_group" "kafka" {
  name        = "speedflow-kafka-${var.environment}"
  description = "SpeedFlow Kafka security group"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 9092
    to_port     = 9092
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

variable "vpc_id" {
  description = "VPC ID for SpeedFlow deployment"
  type        = string
  default     = ""
}

variable "vpc_cidr" {
  default = "10.0.0.0/16"
}

variable "private_subnet_ids" {
  type    = list(string)
  default = []
}

output "kafka_bootstrap_brokers" {
  value = aws_msk_cluster.speedflow.bootstrap_brokers
}

output "kafka_partitions" {
  value = var.kafka_partitions
}
