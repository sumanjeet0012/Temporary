# ============================================================
# Outputs — printed after terraform apply completes
# ============================================================

output "asg_name" {
  description = "Auto Scaling Group name"
  value       = aws_autoscaling_group.github_runner.name
}

output "launch_template_id" {
  description = "Launch Template ID"
  value       = aws_launch_template.github_runner.id
}

output "iam_role_name" {
  description = "IAM Role name for EC2 runners"
  value       = aws_iam_role.github_runner.name
}

output "lambda_function_name" {
  description = "Lambda function name for token refresher"
  value       = aws_lambda_function.token_refresher.function_name
}

output "ssm_parameter_name" {
  description = "SSM parameter storing the runner token"
  value       = aws_ssm_parameter.runner_token.name
}

output "security_group_id" {
  description = "Security group ID for runner instances"
  value       = aws_security_group.github_runner.id
}
