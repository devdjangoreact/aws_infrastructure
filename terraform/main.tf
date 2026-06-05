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
