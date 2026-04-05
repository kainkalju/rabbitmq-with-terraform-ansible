variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-north-1"
}

# Ubuntu 24.04 LTS arm64 in eu-north-1
# Verify with: aws ec2 describe-images --owners 099720109477 \
#   --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-arm64-server-*" \
#   --query "sort_by(Images,&CreationDate)[-1].ImageId" --region eu-north-1
variable "ami_id" {
  description = "Ubuntu 24.04 LTS arm64 AMI ID for eu-north-1"
  type        = string
  default     = "ami-0ccc95acfa22096b2"
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

# Existing security groups to attach
variable "sg_ssh_enabled" {
  description = "SG ID: ssh-enabled"
  type        = string
  default     = "sg-064d9ecc1338dad4e"
}

variable "sg_from_home" {
  description = "SG ID: from-home"
  type        = string
  default     = "sg-0207690533a7d530d"
}

variable "sg_ping" {
  description = "SG ID: ping"
  type        = string
  default     = "sg-05d597352554aae74"
}

variable "ssh_public_key_path" {
  description = "Path to SSH public key to upload as AWS key pair"
  type        = string
  default     = "~/.ssh/rabbitmq_ed25519.pub"
}
