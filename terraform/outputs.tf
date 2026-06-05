output "instance_id" {
  description = "EC2 instance id."
  value       = aws_instance.web.id
}

output "public_ip" {
  description = "Stable public IP (Elastic IP) shared by all 6 domains."
  value       = aws_eip.web.public_ip
}
