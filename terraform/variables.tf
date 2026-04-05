variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-north-1"
}

variable "instance_type" {
  description = "EC2 instance type (ARM64/Graviton3)"
  type        = string
  default     = "t4g.medium"
}

variable "spot_max_price" {
  description = "Maximum hourly Spot price in USD (on-demand t4g.medium eu-north-1 is ~$0.035)"
  default     = "0.035"
}

variable "vpc_id" {
  description = "Existing default VPC ID"
  type        = string
  default     = "vpc-0f47c76ebce94dc7b"
}

# One subnet per AZ — node index matches subnet index
variable "nodes" {
  description = "Map of node name to subnet ID (one per AZ)"
  type        = map(string)
  default = {
    "rabbitmq-1" = "subnet-01c51fde23794b3af" # eu-north-1a
    "rabbitmq-2" = "subnet-0103f2f2ecf770362" # eu-north-1b
    "rabbitmq-3" = "subnet-02ec638de5f418bf7" # eu-north-1c
  }
}

variable "ssh_public_key_path" {
  description = "Path to SSH public key to upload as AWS key pair"
  type        = string
  default     = "~/.ssh/rabbitmq_ed25519.pub"
}
