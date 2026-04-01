resource "aws_instance" "rabbitmq" {
  for_each = var.nodes

  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = each.value
  key_name                    = aws_key_pair.rabbitmq.key_name
  associate_public_ip_address = true
  iam_instance_profile        = "AmazonSSMManagedInstanceProfile"

  vpc_security_group_ids = [
    var.sg_ssh_enabled,
    var.sg_from_home,
    var.sg_ping,
    aws_security_group.rabbitmq.id,
  ]

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 20
    delete_on_termination = true
  }

  tags = {
    Name    = each.key
    Role    = "rabbitmq"
    Cluster = "rabbitmq-cluster"
  }
}
