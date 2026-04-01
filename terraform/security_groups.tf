resource "aws_security_group" "rabbitmq" {
  name        = "rabbitmq"
  description = "RabbitMQ inter-node communication (self-referencing)"
  vpc_id      = var.vpc_id

  tags = {
    Name = "rabbitmq"
  }
}

# Erlang epmd — node discovery
resource "aws_vpc_security_group_ingress_rule" "epmd" {
  security_group_id            = aws_security_group.rabbitmq.id
  referenced_security_group_id = aws_security_group.rabbitmq.id
  from_port                    = 4369
  to_port                      = 4369
  ip_protocol                  = "tcp"
  description                  = "Erlang epmd (inter-node)"
}

# AMQP — inter-node messaging
resource "aws_vpc_security_group_ingress_rule" "amqp" {
  security_group_id            = aws_security_group.rabbitmq.id
  referenced_security_group_id = aws_security_group.rabbitmq.id
  from_port                    = 5672
  to_port                      = 5672
  ip_protocol                  = "tcp"
  description                  = "AMQP inter-node"
}

# Erlang distribution — inter-node RPC
resource "aws_vpc_security_group_ingress_rule" "erlang_dist" {
  security_group_id            = aws_security_group.rabbitmq.id
  referenced_security_group_id = aws_security_group.rabbitmq.id
  from_port                    = 25672
  to_port                      = 25672
  ip_protocol                  = "tcp"
  description                  = "Erlang distribution (inter-node)"
}

# CLI tools port range
resource "aws_vpc_security_group_ingress_rule" "cli_tools" {
  security_group_id            = aws_security_group.rabbitmq.id
  referenced_security_group_id = aws_security_group.rabbitmq.id
  from_port                    = 35672
  to_port                      = 35682
  ip_protocol                  = "tcp"
  description                  = "CLI tools (inter-node)"
}

# Allow all egress
resource "aws_vpc_security_group_egress_rule" "all_egress" {
  security_group_id = aws_security_group.rabbitmq.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "All egress"
}
