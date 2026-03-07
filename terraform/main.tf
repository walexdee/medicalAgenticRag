terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  # Remote state — uncomment and fill in your S3 bucket name before running
  # terraform init in production. State is stored locally until then.
  #
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"   # <-- replace with your bucket
  #   key            = "medical-rag/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "terraform-state-lock"          # optional: state locking
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.app_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Fetch the current AWS account ID and region for use in ARNs
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Availability zones in the chosen region
data "aws_availability_zones" "available" {
  state = "available"
}
