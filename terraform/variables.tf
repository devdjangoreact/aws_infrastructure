variable "aws_region" {
  description = "AWS region. ECR Public API requires us-east-1."
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type (free-tier eligible)."
  type        = string
  default     = "t2.micro"
}

variable "ami_id" {
  description = "Ubuntu 22.04 LTS AMI id for the chosen region."
  type        = string
}

variable "ssh_public_key" {
  description = "Contents of the project deploy public key (.ssh/project_key.pub)."
  type        = string
}

variable "ssh_allowed_cidrs" {
  description = "CIDR ranges allowed to reach SSH (22). Restrict to CI/bastion ranges."
  type        = list(string)
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token with DNS edit on the managed zones."
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_ids" {
  description = "Map of managed domain => Cloudflare zone id."
  type        = map(string)
}
