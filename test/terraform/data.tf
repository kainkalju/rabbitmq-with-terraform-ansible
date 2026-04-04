# Look up the existing self-referencing RabbitMQ SG by name.
# Attaching this SG to the test client grants it port 5672 access
# to all cluster nodes — no new ingress rules required.
data "aws_security_group" "rabbitmq" {
  name   = "rabbitmq"
  vpc_id = var.vpc_id
}
