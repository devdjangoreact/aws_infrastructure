# Latest Ubuntu 22.04 LTS AMI (Canonical) for the chosen region - no hardcoded AMI id.
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Look up each managed zone by domain name - no hardcoded zone ids.
data "cloudflare_zone" "site" {
  for_each = local.services

  filter = {
    name = each.key
  }
}
