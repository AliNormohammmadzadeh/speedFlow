provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "speedflow"
      ManagedBy   = "terraform"
      Environment = var.environment
    }
  }
}

# Kubernetes provider targets the EKS cluster created by the eks module.
provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_ca_certificate)
  token                  = var.eks_auth_token
}
