variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-north-1"
}

variable "instance_type" {
  description = "EC2 instance type (ARM64/Graviton3)"
  type        = string
  default     = "t4g.small"
}

variable "spot_max_price" {
  description = "Maximum hourly Spot price in USD (on-demand t4g.small eu-north-1 is ~$0.0188)"
  default     = "0.0172"
}

variable "vpc_id" {
  description = "Existing default VPC ID"
  type        = string
  default     = "vpc-0f47c76ebce94dc7b"
}

variable "subnet_id" {
  description = "eu-north-1a — same AZ as rabbitmq-1 for lowest latency"
  default     = "subnet-01c51fde23794b3af"
}

variable "ssh_public_key_path" {
  description = "Path to SSH public key to upload as AWS key pair"
  type        = string
  default     = "~/.ssh/rabbitmq_ed25519.pub"
}
