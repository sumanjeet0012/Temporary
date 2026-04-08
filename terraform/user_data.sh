#!/bin/bash
set -e

RUNNER_VERSION="${runner_version}"
ORG_NAME="${org_name}"
RUNNER_GROUP="${runner_group}"
REGION="${aws_region}"
SSM_PARAM="${ssm_param_name}"
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)

# Install dependencies
apt-get update -y
apt-get install -y curl jq unzip docker.io

# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install

# Fetch registration token from SSM
REG_TOKEN=$(aws ssm get-parameter \
  --name "$SSM_PARAM" \
  --with-decryption \
  --query "Parameter.Value" \
  --output text \
  --region $REGION)

# Create runner user
useradd -m runner
usermod -aG docker runner

# Download and extract runner
mkdir -p /home/runner/actions-runner
cd /home/runner/actions-runner
curl -o runner.tar.gz -L \
  "https://github.com/actions/runner/releases/download/v$${RUNNER_VERSION}/actions-runner-linux-x64-$${RUNNER_VERSION}.tar.gz"
tar xzf runner.tar.gz
chown -R runner:runner /home/runner/actions-runner

# Configure and register with GitHub
sudo -u runner ./config.sh \
  --url "https://github.com/$${ORG_NAME}" \
  --token "$${REG_TOKEN}" \
  --name "ec2-$${INSTANCE_ID}" \
  --runnergroup "$${RUNNER_GROUP}" \
  --labels "ec2,self-hosted,linux,x64" \
  --ephemeral \
  --unattended \
  --replace

# Install and start runner as a system service
./svc.sh install runner
./svc.sh start
