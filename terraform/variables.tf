# ============================================================
# Variables — this is the ONLY file you ever need to edit
# ============================================================

variable "aws_region" {
  description = "AWS region to deploy runners in"
  type        = string
  default     = "eu-north-1"
}

variable "github_org" {
  description = "GitHub organization name"
  type        = string
  default     = "py-libp2p-runners"
}

variable "github_pat" {
  description = "GitHub Personal Access Token with admin:org scope"
  type        = string
  sensitive   = true
}

variable "runner_group" {
  description = "GitHub Actions runner group name (must exist in your GitHub org)"
  type        = string
  default     = "ec2-runners"
}

variable "runner_version" {
  description = "GitHub Actions runner version"
  type        = string
  default     = "2.314.1"
}

variable "ami_id" {
  description = "Ubuntu 22.04 LTS AMI ID for eu-north-1"
  type        = string
  default     = "ami-09a9858973b288bdd"
}

variable "instance_type" {
  description = "EC2 instance type for runners"
  type        = string
  default     = "t3.medium"
}

variable "subnet_ids" {
  description = "List of subnet IDs for the Auto Scaling Group. Leave empty to use default VPC subnets."
  type        = list(string)
  default     = []
}

variable "asg_min" {
  description = "Minimum number of runner instances"
  type        = number
  default     = 1
}

variable "asg_max" {
  description = "Maximum number of runner instances"
  type        = number
  default     = 5
}

variable "asg_desired" {
  description = "Desired number of runner instances at any time"
  type        = number
  default     = 1
}

variable "prefix" {
  description = "Prefix for all AWS resource names. Change this to avoid conflicts with existing resources."
  type        = string
  default     = "tf"
}

variable "ssh_key_name" {
  description = "Name of an existing EC2 Key Pair for SSH access. Leave empty to disable SSH (use SSM Session Manager instead)."
  type        = string
  default     = ""
}

variable "ssh_allowed_cidr" {
  description = "CIDR block allowed to SSH into runners. Restrict to your IP for security (e.g. \"1.2.3.4/32\")."
  type        = string
  default     = "0.0.0.0/0"
}

# ============================================================
# Derived locals — names for every resource, built from prefix
# All resource names in main.tf use these locals, never hardcoded strings
# ============================================================

locals {
  ec2_iam_role_name        = "${var.prefix}-github-runner-role"
  ec2_iam_profile_name     = "${var.prefix}-github-runner-profile"
  lambda_iam_role_name     = "${var.prefix}-token-refresher-role"
  lambda_function_name     = "${var.prefix}-token-refresher"
  ssm_parameter_name       = "/${var.prefix}-github-runner/registration-token"
  security_group_name      = "${var.prefix}-github-runner-sg"
  launch_template_name     = "${var.prefix}-github-runner-template"
  asg_name                 = "${var.prefix}-github-runner-asg"
  eventbridge_rule_name    = "${var.prefix}-github-runner-token-refresh"
}
