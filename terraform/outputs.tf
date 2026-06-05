output "instance_id" {
  description = "EC2 instance id."
  value       = aws_instance.web.id
}

output "public_ip" {
  description = "Stable public IP (Elastic IP) shared by all 6 domains."
  value       = aws_eip.web.public_ip
}

output "ecr_repository_uris" {
  description = "ECR Public repository URIs (public.ecr.aws/<alias>/<service>)."
  value       = { for k, r in aws_ecrpublic_repository.site : k => r.repository_uri }
}

output "ssh_private_key_path" {
  description = "Local path to the generated deploy private key (git-ignored)."
  value       = local_sensitive_file.deploy_private_key.filename
}
