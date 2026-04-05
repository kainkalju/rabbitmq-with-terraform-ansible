# Latest Ubuntu 24.04 LTS arm64 AMI published by Canonical
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-arm64-server-*"]
  }

  filter {
    name   = "architecture"
    values = ["arm64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

# Look up the existing self-referencing RabbitMQ SG by name.
# Attaching this SG to the test client grants it port 5672 access
# to all cluster nodes — no new ingress rules required.
data "aws_security_group" "rabbitmq" {
  name   = "rabbitmq"
  vpc_id = var.vpc_id
}

data "aws_security_group" "ssh_enabled" {
  name   = "ssh-enabled"
  vpc_id = var.vpc_id
}

data "aws_security_group" "from_home" {
  name   = "from-home"
  vpc_id = var.vpc_id
}

data "aws_security_group" "ping" {
  name   = "ping"
  vpc_id = var.vpc_id
}
