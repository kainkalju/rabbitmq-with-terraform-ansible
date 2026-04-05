resource "aws_instance" "test_client" {
  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  key_name                    = "rabbitmq-key"
  associate_public_ip_address = true

  vpc_security_group_ids = [
    var.sg_ssh_enabled,
    var.sg_from_home,
    var.sg_ping,
    data.aws_security_group.rabbitmq.id,
  ]

  # Hibernate requires an encrypted root volume
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 20
    encrypted             = true
    delete_on_termination = true
  }

  instance_market_options {
    market_type = "spot"
    spot_options {
      instance_interruption_behavior = "hibernate"
      spot_instance_type             = "persistent"
      max_price                      = var.spot_max_price
      valid_until                    = timeadd(timestamp(), "24h")
    }
  }

  tags = {
    Name = "rabbitmq-test-client"
    Role = "test-client"
  }
}
