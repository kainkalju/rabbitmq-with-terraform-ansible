variable "region" {
  default = "eu-north-1"
}

variable "ami_id" {
  description = "Ubuntu 24.04 LTS arm64"
  default     = "ami-0ccc95acfa22096b2"
}

variable "instance_type" {
  default = "t4g.small"
}

variable "vpc_id" {
  default = "vpc-0f47c76ebce94dc7b"
}

variable "subnet_id" {
  description = "eu-north-1a — same AZ as rabbitmq-1 for lowest latency"
  default     = "subnet-01c51fde23794b3af"
}

variable "sg_ssh_enabled" {
  default = "sg-064d9ecc1338dad4e"
}

variable "sg_from_home" {
  default = "sg-0207690533a7d530d"
}

variable "sg_ping" {
  default = "sg-05d597352554aae74"
}

variable "ssh_public_key_path" {
  default = "~/.ssh/rabbitmq_ed25519.pub"
}
