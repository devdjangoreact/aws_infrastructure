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

variable "ssh_allowed_cidrs" {
  description = "CIDR ranges allowed to reach SSH (22). Restrict to CI/bastion ranges in production."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token with DNS edit on the managed zones."
  type        = string
  sensitive   = true
}
