resource "aws_key_pair" "rabbitmq" {
  key_name   = "rabbitmq-key"
  public_key = file(pathexpand(var.ssh_public_key_path))

  tags = {
    Name = "rabbitmq-key"
  }
}
