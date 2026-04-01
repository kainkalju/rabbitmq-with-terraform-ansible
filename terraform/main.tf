terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local state — upgrade to S3+DynamoDB for team use
  backend "local" {}
}

provider "aws" {
  region = var.region
}
