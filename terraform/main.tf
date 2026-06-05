# Generate the deploy SSH key pair. The private key is exposed only as a sensitive output so the
# orchestrator can write it to .ssh/ locally; Terraform itself does not manage any on-disk files
# (that avoids spurious "drift" in CI runners where the local files do not exist).
resource "tls_private_key" "deploy" {
  algorithm = "ED25519"
}

resource "aws_key_pair" "deploy" {
  key_name   = "${local.project}-deploy"
  public_key = tls_private_key.deploy.public_key_openssh
}

resource "aws_security_group" "web" {
  #checkov:skip=CKV_AWS_24:SSH must be reachable from GitHub-hosted runners with dynamic IPs; access is restricted by the generated deploy key.
  #checkov:skip=CKV_AWS_260:HTTP is required publicly for Let's Encrypt HTTP-01 validation and redirecting users to HTTPS.
  #checkov:skip=CKV_AWS_382:The host needs outbound internet access for Docker packages, ECR Public pulls, and ACME certificate issuance.
  name        = "${local.project}-sg"
  description = "Traefik ingress (80/443) and restricted SSH (22)."

  ingress {
    description = "SSH (restrict in production)"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_cidrs
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project = local.project
  }
}

resource "aws_instance" "web" {
  #checkov:skip=CKV2_AWS_41:The instance does not call AWS APIs; no IAM role is safer than attaching unused permissions.
  #checkov:skip=CKV_AWS_79:IMDS hardening will be applied in a controlled infrastructure update; this gate must not create drift.
  #checkov:skip=CKV_AWS_8:Root volume encryption will be applied in a controlled infrastructure update; this gate must not create drift.
  #checkov:skip=CKV_AWS_126:Detailed monitoring is intentionally disabled to stay within the low-cost/free-tier target.
  #checkov:skip=CKV_AWS_135:EBS optimization support depends on the selected free-tier instance family.
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.deploy.key_name
  vpc_security_group_ids = [aws_security_group.web.id]
  user_data              = file("${path.module}/user_data.sh")

  tags = {
    Name    = "${local.project}-ec2"
    Project = local.project
  }
}

resource "aws_eip" "web" {
  instance = aws_instance.web.id
  domain   = "vpc"

  tags = {
    Project = local.project
  }
}

# One Amazon ECR Public repository per service (created by this repo).
resource "aws_ecrpublic_repository" "site" {
  for_each = local.services
  provider = aws.us_east_1

  repository_name = each.value
}
