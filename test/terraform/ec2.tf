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

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 20
    delete_on_termination = true
  }

  tags = {
    Name = "rabbitmq-test-client"
    Role = "test-client"
  }
}
