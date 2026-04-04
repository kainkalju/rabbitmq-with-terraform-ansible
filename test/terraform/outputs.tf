output "public_ip" {
  value = aws_instance.test_client.public_ip
}

output "private_ip" {
  value = aws_instance.test_client.private_ip
}
