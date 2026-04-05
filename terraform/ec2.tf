resource "aws_instance" "rabbitmq" {
  for_each = var.nodes

  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = each.value
  key_name                    = aws_key_pair.rabbitmq.key_name
  associate_public_ip_address = true
  iam_instance_profile        = "AmazonSSMManagedInstanceProfile"

  vpc_security_group_ids = [
    data.aws_security_group.ssh_enabled.id,
    data.aws_security_group.from_home.id,
    data.aws_security_group.ping.id,
    aws_security_group.rabbitmq.id,
  ]

  # Hibernate requires an encrypted root volume
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 20
    encrypted             = true
    delete_on_termination = true
  }

  # # Remove this block if you need On-Demand instances
  # instance_market_options {
  #   market_type = "spot"
  #   spot_options {
  #     instance_interruption_behavior = "hibernate"
  #     spot_instance_type             = "persistent"
  #     max_price                      = var.spot_max_price
  #     valid_until                    = timeadd(timestamp(), "24h")
  #   }
  # }

  tags = {
    Name    = each.key
    Role    = "rabbitmq"
    Cluster = "rabbitmq-cluster"
  }
}
