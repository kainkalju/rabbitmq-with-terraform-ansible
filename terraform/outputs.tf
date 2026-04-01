output "public_ips" {
  description = "Public IPs of RabbitMQ nodes"
  value = {
    for name, instance in aws_instance.rabbitmq :
    name => instance.public_ip
  }
}

output "private_ips" {
  description = "Private IPs of RabbitMQ nodes (used for clustering)"
  value = {
    for name, instance in aws_instance.rabbitmq :
    name => instance.private_ip
  }
}

output "instance_ids" {
  description = "EC2 instance IDs"
  value = {
    for name, instance in aws_instance.rabbitmq :
    name => instance.id
  }
}
