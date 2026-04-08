# ============================================================
# GitHub Actions Self-Hosted Runner on AWS EC2
# All names come from variables.tf — never hardcoded here
# ============================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.3.0"
}

provider "aws" {
  region = var.aws_region
}

# ============================================================
# 0. Default VPC / Subnet fallback
# Used when var.subnet_ids is left empty
# ============================================================

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

locals {
  resolved_subnet_ids = length(var.subnet_ids) > 0 ? var.subnet_ids : data.aws_subnets.default.ids
}

# ============================================================
# 1. IAM Role for EC2 instances
# ============================================================

resource "aws_iam_role" "github_runner" {
  name = local.ec2_iam_role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_read" {
  role       = aws_iam_role.github_runner.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess"
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.github_runner.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "github_runner" {
  name = local.ec2_iam_profile_name
  role = aws_iam_role.github_runner.name
}

# ============================================================
# 2. IAM Role for Lambda (token refresher)
# ============================================================

resource "aws_iam_role" "lambda_role" {
  name = local.lambda_iam_role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_ssm" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMFullAccess"
}

# ============================================================
# 3. SSM Parameter Store
# ============================================================

resource "aws_ssm_parameter" "runner_token" {
  name  = local.ssm_parameter_name
  type  = "SecureString"
  value = "placeholder"

  lifecycle {
    ignore_changes = [value]
  }
}

# ============================================================
# 4. Security Group
# ============================================================

resource "aws_security_group" "github_runner" {
  name        = local.security_group_name
  description = "GitHub Actions runner - allow all inbound and outbound"

  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all inbound traffic"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = {
    Name = local.security_group_name
  }
}

# ============================================================
# 5. Launch Template
# ============================================================

resource "aws_launch_template" "github_runner" {
  name          = local.launch_template_name
  image_id      = var.ami_id
  instance_type = var.instance_type

  iam_instance_profile {
    name = aws_iam_instance_profile.github_runner.name
  }

  key_name = var.ssh_key_name != "" ? var.ssh_key_name : null

  network_interfaces {
    associate_public_ip_address = true
    security_groups             = [aws_security_group.github_runner.id]
  }

  block_device_mappings {
    device_name = "/dev/sda1"
    ebs {
      volume_size           = 30
      volume_type           = "gp3"
      delete_on_termination = true
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    runner_version = var.runner_version
    org_name       = var.github_org
    runner_group   = var.runner_group
    aws_region     = var.aws_region
    ssm_param_name = local.ssm_parameter_name
  }))

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = local.launch_template_name
    }
  }
}

# ============================================================
# 6. Auto Scaling Group
# ============================================================

resource "aws_autoscaling_group" "github_runner" {
  name                = local.asg_name
  min_size            = var.asg_min
  max_size            = var.asg_max
  desired_capacity    = var.asg_desired
  vpc_zone_identifier = local.resolved_subnet_ids

  launch_template {
    id      = aws_launch_template.github_runner.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = local.asg_name
    propagate_at_launch = true
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 0
    }
  }
}

# ============================================================
# 7. Lambda Function (token refresher)
# ============================================================

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda_function.py"
  output_path = "${path.module}/lambda_function.zip"
}

resource "aws_lambda_function" "token_refresher" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = local.lambda_function_name
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      GITHUB_PAT   = var.github_pat
      GITHUB_ORG   = var.github_org
      AWS_REGION_  = var.aws_region
      SSM_PARAM    = local.ssm_parameter_name
    }
  }
}

# ============================================================
# 8. EventBridge rule — runs Lambda every 30 minutes
# ============================================================

resource "aws_cloudwatch_event_rule" "every_30_minutes" {
  name                = local.eventbridge_rule_name
  description         = "Refresh GitHub runner token every 30 minutes"
  schedule_expression = "rate(30 minutes)"
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.every_30_minutes.name
  target_id = "RefreshToken"
  arn       = aws_lambda_function.token_refresher.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.token_refresher.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.every_30_minutes.arn
}
