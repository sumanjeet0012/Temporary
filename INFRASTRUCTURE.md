# GitHub Actions Self-Hosted Runner on AWS — Infrastructure Guide

> This document explains every resource created by this Terraform project, why each one exists,
> how the pieces connect, known gotchas, and what (if anything) you still need to do manually.

---

## Table of Contents

1. [What problem are we solving?](#1-what-problem-are-we-solving)
2. [Architecture overview](#2-architecture-overview)
3. [Every AWS resource — what it is and why it exists](#3-every-aws-resource--what-it-is-and-why-it-exists)
4. [The Lambda function — deep dive](#4-the-lambda-function--deep-dive)
5. [The runner loop — how EC2 instances keep picking up jobs](#5-the-runner-loop--how-ec2-instances-keep-picking-up-jobs)
6. [Why two config files? `.env` vs `terraform.tfvars`](#6-why-two-config-files-env-vs-terraformtfvars)
7. [Why `terraform destroy` sometimes gets stuck](#7-why-terraform-destroy-sometimes-gets-stuck)
8. [What you must do manually (and why Terraform can't do it)](#8-what-you-must-do-manually-and-why-terraform-cant-do-it)
9. [The PAT problem — why secrets are painful here](#9-the-pat-problem--why-secrets-are-painful-here)
10. [Day-to-day commands](#10-day-to-day-commands)
11. [Things to improve in the future](#11-things-to-improve-in-the-future)

---

## 1. What problem are we solving?

The `py-libp2p` repository runs a CI matrix of **25 Linux jobs** (4 Python versions × 6 tox
environments + 1 docs job) plus **12 Windows jobs** every time a PR is opened or a push hits
`main`. GitHub's free-tier hosted runners are slow and have limited concurrency. Running on
self-hosted EC2 instances gives:

- **Faster execution** — you choose the instance type and size
- **Pre-installed dependencies** — `libgmp-dev`, `rustc`, `cargo`, Docker, etc. are baked in
  at boot so jobs don't waste time installing them
- **Full parallelism** — 10+ runners can all run simultaneously instead of queuing

---

## 2. Architecture overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Your machine                                                   │
│  terraform apply  ──────────────────────────────────────────►  │
└────────────────────────────────┬────────────────────────────────┘
                                 │ creates
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  AWS (eu-north-1)                                               │
│                                                                 │
│  EventBridge (every 15 min)                                     │
│       │ triggers                                                │
│       ▼                                                         │
│  Lambda (token-refresher)  ──writes──►  SSM Parameter Store    │
│                                              │                  │
│                                              │ read at boot     │
│                                              ▼                  │
│  Auto Scaling Group  ──launches──►  EC2 instances (×10)        │
│       │                                  │                      │
│       │ uses                             │ registers as         │
│       ▼                                  ▼                      │
│  Launch Template               GitHub Actions Runner            │
│                                (picks up CI jobs in a loop)     │
└─────────────────────────────────────────────────────────────────┘
                                 │ sends jobs to
                                 ▼
                        GitHub (py-libp2p repo)
```

**Flow in plain English:**
1. Terraform creates everything in AWS
2. A Lambda function calls the GitHub API and stores a runner registration token in SSM
3. EC2 instances boot, read that token from SSM, and register themselves as GitHub Actions runners
4. GitHub dispatches CI jobs to these runners
5. Each runner runs one job, then immediately re-registers and waits for the next one
6. EventBridge triggers the Lambda every 15 minutes to keep the SSM token fresh (tokens expire in 1 hour)

---

## 3. Every AWS resource — what it is and why it exists

### 3.1 IAM Role for EC2 — `tf-github-runner-role`

**What:** An AWS Identity role that EC2 instances assume automatically at boot.

**Why:** EC2 instances need permission to read from SSM Parameter Store (to fetch the runner
registration token). Without this role, the instance would have no AWS credentials and the
`aws ssm get-parameter` call in `user_data.sh` would fail with "Access Denied".

**Policies attached:**
| Policy | Why |
|---|---|
| `AmazonSSMReadOnlyAccess` | Read the registration token from SSM |
| `AmazonSSMManagedInstanceCore` | Allows AWS Systems Manager to connect to the instance (useful for debugging without SSH) |

---

### 3.2 IAM Instance Profile — `tf-github-runner-profile`

**What:** A wrapper around the IAM role that allows it to be attached to an EC2 instance.

**Why:** EC2 doesn't attach IAM roles directly — it needs an "instance profile" container.
This is an AWS quirk. The role and the profile are always created as a pair.

---

### 3.3 IAM Role for Lambda — `tf-token-refresher-role`

**What:** An AWS Identity role that the Lambda function assumes when it runs.

**Why:** The Lambda needs two permissions:
1. Call the GitHub API (no AWS permission needed — it's just HTTPS)
2. Write the token to SSM Parameter Store (needs `AmazonSSMFullAccess`)

It also gets `AWSLambdaBasicExecutionRole` so it can write logs to CloudWatch.

---

### 3.4 SSM Parameter Store — `/tf-github-runner/registration-token`

**What:** AWS's encrypted secret storage. Stores the GitHub runner registration token as a
`SecureString` (encrypted at rest using AWS KMS).

**Why:** EC2 instances need a GitHub registration token to join as runners. But:
- Tokens expire after **1 hour**
- You can't bake the token into the AMI or Launch Template (it would be stale by the time
  the instance boots)
- You can't pass it as a Terraform variable (Terraform runs once; instances boot continuously)

SSM solves this: the Lambda refreshes the token every 15 minutes, and each EC2 instance
reads the current token from SSM when it needs to re-register.

**Important:** Terraform creates this parameter with `value = "placeholder"`. The Lambda
overwrites it with a real token immediately after being created (via `null_resource.initial_token_refresh`).
The `lifecycle { ignore_changes = [value] }` block tells Terraform to never touch the value
again after creation — otherwise every `terraform apply` would reset it back to "placeholder".

---

### 3.5 Security Group — `tf-github-runner-sg`

**What:** A firewall rule for the EC2 instances.

**Why:** AWS blocks all traffic by default. The runners need:
- **Inbound port 22** — SSH access for debugging (you can restrict `ssh_allowed_cidr` to your IP)
- **All outbound** — runners need to reach GitHub, download packages, pull Docker images, etc.

---

### 3.6 Launch Template — `tf-github-runner-lt`

**What:** A blueprint that defines exactly how each EC2 instance should be configured when
the Auto Scaling Group creates one.

**Why:** Instead of manually configuring each instance, the Launch Template stores:
- Which AMI (Ubuntu 22.04) to use
- Instance type (`t3.medium`)
- Which IAM profile to attach
- The `user_data.sh` script (runs at first boot)
- Storage: 30 GB gp3 EBS volume
- Network settings (public IP, security group)
- IMDSv2 enforced (secure metadata access)

The `user_data.sh` is embedded here as base64. Every new instance launched by the ASG
automatically runs this script on first boot.

---

### 3.7 Auto Scaling Group (ASG) — `tf-github-runner-asg`

**What:** Manages a fleet of EC2 instances. Ensures the right number are always running.

**Why:** Instead of manually launching 10 EC2 instances, the ASG:
- Keeps exactly `asg_desired` (currently 10) instances running at all times
- Replaces instances that crash or are terminated
- Can scale up/down based on demand (not configured here yet)
- Spreads instances across multiple Availability Zones for resilience

**Settings:**
| Setting | Value | Why |
|---|---|---|
| `min_size` | 1 | Always keep at least 1 runner alive |
| `max_size` | 25 | Hard cap — matches the 25-job CI matrix |
| `desired_capacity` | 10 | Run 10 in parallel by default |
| `termination_policies` | OldestInstance | Predictable scale-in behaviour |
| `wait_for_capacity_timeout` | 10 min | Give instances time to boot and become healthy |

---

### 3.8 Lambda Function — `tf-token-refresher`

See [Section 4](#4-the-lambda-function--deep-dive) for a full explanation.

---

### 3.9 EventBridge Rule — `tf-github-runner-token-refresh`

**What:** A scheduled trigger (like a cron job) that runs every 15 minutes.

**Why:** GitHub runner registration tokens expire after **1 hour**. If an EC2 instance tries
to register with a token older than 1 hour, it gets a 401 error and fails to join.

By refreshing every 15 minutes, there is always a token in SSM that is at most 15 minutes
old — well within the 1-hour expiry window.

---

### 3.10 `null_resource.initial_token_refresh`

**What:** Not a real AWS resource. It's a Terraform mechanism to run a shell command
(`local-exec`) on your machine during `terraform apply`.

**Why:** When infrastructure is first created, the SSM parameter has `value = "placeholder"`.
The EC2 instances would boot, try to read the token, get "placeholder", and fail. This
`null_resource` invokes the Lambda immediately after it's created so SSM has a real token
before any EC2 instance boots.

**Why not use `data.aws_lambda_invocation`?** (The original approach)
The original code used a Terraform `data` source to invoke the Lambda. Data sources are
evaluated during **both `plan` and `apply`** — meaning if the Lambda ever failed (bad PAT,
network issue), `terraform plan` would fail, and most critically, **`terraform destroy`
would also fail**, leaving you unable to clean up your AWS resources. The `null_resource`
approach only runs during `apply`, never during `plan` or `destroy`.

---

## 4. The Lambda function — deep dive

**File:** `lambda_function.py`
**AWS name:** `tf-token-refresher`

### What it does

```
GitHub API  ◄──── Lambda calls POST /orgs/{org}/actions/runners/registration-token
                  using your GitHub PAT
                        │
                        │ gets back a token like "AABBCC...XYZ" (expires in 1 hour)
                        ▼
                  Lambda writes token to SSM Parameter Store
                        │
                        ▼
                  EC2 instances read token from SSM at registration time
```

### Is it created by Terraform?

**Yes.** `aws_lambda_function.token_refresher` in `main.tf` creates it. The Python code is
in `lambda_function.py` — Terraform zips it automatically using `data.archive_file.lambda_zip`
and uploads the zip to Lambda.

### Is it destroyed by Terraform?

**Yes.** `terraform destroy` deletes the Lambda function, its IAM role, the EventBridge rule,
and the SSM parameter. Everything is fully managed.

### Why does it store the token in SSM instead of passing it directly?

Because the Lambda runs on a schedule (every 15 min) and EC2 instances boot on demand at
unpredictable times. There's no direct connection between them — SSM acts as the shared
"mailbox" where the Lambda drops a fresh token and instances pick it up when needed.

### What happens if the Lambda fails?

- If it fails during the **initial seed** (`null_resource`): EC2 instances will boot and find
  "placeholder" in SSM. The runner loop in `user_data.sh` handles this gracefully — it retries
  every 30 seconds until a real token appears.
- If it fails on a **scheduled run**: The existing token in SSM remains valid until it expires
  (1 hour). The next scheduled run (15 min later) will try again.

---

## 5. The runner loop — how EC2 instances keep picking up jobs

**File:** `user_data.sh`

This script runs **once at first boot** on every EC2 instance. Here's what it does:

### Boot sequence

```
Instance boots
      │
      ▼
user_data.sh runs (once, as root)
      │
      ├── Install: curl, jq, docker, git, rustc, cargo, libgmp-dev, AWS CLI
      │
      ├── Fetch registration token from SSM
      │
      ├── Create 'runner' Linux user
      │
      ├── Download GitHub Actions runner binary (v2.323.0)
      │
      ├── Write /home/runner/runner-loop.sh
      │
      └── Install + start systemd service 'github-runner'
                │
                ▼
          runner-loop.sh runs forever (as a service)
                │
                ▼
          ┌─────────────────────────────────┐
          │  while true:                    │
          │    1. Fetch fresh token from SSM│
          │    2. config.sh --ephemeral     │  ← registers with GitHub
          │    3. run.sh                    │  ← picks up ONE job, runs it
          │    4. sleep 2                   │
          │    5. go back to step 1         │
          └─────────────────────────────────┘
```

### Why `--ephemeral`?

The `--ephemeral` flag tells the runner to **deregister from GitHub after completing one job**.
This is a security best practice — each job gets a clean environment with no leftover files,
environment variables, or credentials from the previous job.

### Why the loop?

Without the loop (the original broken design), the runner would:
1. Register with GitHub ✅
2. Run one job ✅
3. Deregister (ephemeral) ✅
4. **Exit and never pick up another job** ❌

The loop re-registers the runner after every job, so each EC2 instance can handle unlimited
jobs sequentially without the ASG needing to replace it.

### Why is it a systemd service?

If the runner crashes for any reason, systemd automatically restarts it (`Restart=always`).
The service also starts automatically if the instance reboots.

---

## 6. Why two config files? `.env` vs `terraform.tfvars`

This is confusing but there's a good reason for both.

### `terraform.tfvars` — Terraform's native config file

Terraform automatically reads this file when you run `terraform apply`. It sets variable
values for the Terraform run.

**Problem:** It contains your GitHub PAT in plain text. If you accidentally commit this file
to Git, your PAT is exposed. GitHub's secret scanning will detect it and **automatically
revoke the token** (this is exactly what happened during our debugging session).

**Current state:** The PAT line has been cleared — it now reads a placeholder. You should
never put your real PAT back here.

### `.env` — The secrets file

This file holds the real secrets. It is **never read by Terraform automatically** — you must
explicitly load it before running Terraform:

```bash
set -a && source .env && set +a
terraform apply
```

The `set -a` exports every variable in `.env` as a shell environment variable. Terraform
automatically picks up any environment variable prefixed with `TF_VAR_` — so
`TF_VAR_github_pat` in `.env` becomes `var.github_pat` inside Terraform.

### Why not just use `.env` for everything?

`terraform.tfvars` is convenient for non-secret values (region, instance type, ASG sizes).
You can see and edit them without thinking about secrets. The `.env` file is only for secrets.

### Summary

| File | Contains | Read by Terraform | Commit to Git? |
|---|---|---|---|
| `terraform.tfvars` | Non-secret config | Automatically | ✅ Safe (no secrets) |
| `.env` | Secrets (PAT) | Only if you `source` it first | ❌ Never |
| `variables.tf` | Variable definitions & defaults | Automatically | ✅ Safe |

---

## 7. Why `terraform destroy` sometimes gets stuck

There are three known causes:

### Cause 1 — Security Group still in use by running EC2 instances

The ASG creates EC2 instances that reference the Security Group. When Terraform tries to
delete the Security Group, AWS refuses because instances are still using it.

**Fix in our code:** The ASG has `depends_on = [aws_security_group.github_runner]`. This
tells Terraform to destroy the ASG (which terminates all instances) **before** attempting
to destroy the Security Group. The ASG destroy scales instances to 0 first, waits for them
to terminate, then removes the ASG.

**Why it can still hang:** If an EC2 instance is mid-boot or mid-job, it may take several
minutes to terminate. Terraform waits up to 10 minutes (`wait_for_capacity_timeout`).

### Cause 2 — Lambda invocation blocking plan/destroy (the original bug)

The original code used `data.aws_lambda_invocation` which Terraform evaluates during
**every** operation including `plan` and `destroy`. If the Lambda failed (e.g. bad PAT),
Terraform would refuse to even start the destroy. This has been fixed — we now use
`null_resource` with `local-exec` which only runs during `apply`.

### Cause 3 — IAM role detachment timing

AWS sometimes takes 10–30 seconds to fully detach IAM policies before the role itself can
be deleted. Terraform usually handles this with automatic retries, but occasionally it times
out. If this happens, just run `terraform destroy` again — it picks up where it left off.

---

## 8. What you must do manually (and why Terraform can't do it)

### ✅ Things Terraform handles automatically

- Creating all AWS resources
- Seeding the SSM token (via `null_resource` + Lambda)
- Keeping the token fresh (via EventBridge every 15 min)
- Registering runners with GitHub (via `user_data.sh`)
- Destroying everything cleanly

### ⚠️ Things you must do manually

#### 1. Create the GitHub organization `py-libp2p-runners`

**Why Terraform can't do it:** The GitHub Terraform provider can manage repositories and
teams, but creating a new GitHub organization requires a logged-in browser session — GitHub
does not expose this via API.

**What you need:** Go to https://github.com/organizations/plan and create the org manually.

#### 2. Create the runner group `ec2-runners` in the GitHub org

**Why Terraform can't do it (easily):** You'd need to add the GitHub Terraform provider and
authenticate it with a PAT. Currently not configured.

**What you need:**
1. Go to `https://github.com/organizations/py-libp2p-runners/settings/actions/runner-groups`
2. Click "New runner group"
3. Name it `ec2-runners`
4. Set repository access to the `py-libp2p` repo

#### 3. Generate and manage the GitHub PAT

**Why Terraform can't do it:** GitHub PATs are created through GitHub's web UI or API with
user authentication. They cannot be created by Terraform without a chicken-and-egg problem
(you need a PAT to authenticate Terraform, but Terraform would need to create the PAT).

**What you need:**
1. Go to https://github.com/settings/tokens/new
2. Select scope: `admin:org`
3. Copy the token into `.env` as `TF_VAR_github_pat=ghp_...`
4. Always run Terraform with: `set -a && source .env && set +a && terraform apply`

#### 4. Fork or add `py-libp2p` repo to the `py-libp2p-runners` org

The workflow file (`tox.yml`) must exist in a repo that belongs to the org where your
runners are registered. Either fork `libp2p/py-libp2p` into `py-libp2p-runners`, or
configure the runner group to allow access to the external repo.

---

## 9. The PAT problem — why secrets are painful here

A GitHub PAT is the bridge between AWS and GitHub. Here's why it causes problems:

### The exposure risk

If the PAT appears in any file that gets committed to a public Git repository, GitHub's
secret scanning bot detects it within seconds and **automatically revokes it**. This happened
during our setup — the PAT was in `terraform.tfvars` which was visible in the workspace.

### The Terraform state risk

Terraform stores the state of all resources in `terraform.tfstate`. Any sensitive variable
passed to Terraform (like `var.github_pat`) **gets written into the state file in plain text**.
The state file should never be committed to Git either.

### The Lambda environment variable risk

The PAT is stored as a Lambda environment variable. While it's encrypted at rest in AWS,
anyone with access to the Lambda console can see it. For production, consider storing the
PAT in AWS Secrets Manager instead and having the Lambda fetch it at runtime.

### Best practice going forward

```bash
# Never put the PAT in any file that touches Git.
# Always pass it via environment variable:
export TF_VAR_github_pat="ghp_yourtoken"
terraform apply

# Or load from .env (which is in .gitignore):
set -a && source .env && set +a
terraform apply
```

---

## 10. Day-to-day commands

### Deploy / update infrastructure
```bash
cd "github-runner-terraform-v2"
set -a && source .env && set +a
terraform init    # only needed first time or after provider changes
terraform apply
```

### Destroy everything
```bash
set -a && source .env && set +a
terraform destroy
```

### Check runner status on GitHub
Go to: `https://github.com/organizations/py-libp2p-runners/settings/actions/runners`

### SSH into a runner instance (for debugging)
```bash
# Get instance IPs from AWS console or:
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=tf-github-runner-asg" \
  --query "Reservations[].Instances[].PublicIpAddress" \
  --region eu-north-1 \
  --output text

ssh -i your-key.pem ubuntu@<instance-ip>

# Check runner loop logs:
sudo journalctl -u github-runner -f
```

### Manually trigger Lambda (force token refresh)
```bash
aws lambda invoke \
  --function-name tf-token-refresher \
  --region eu-north-1 \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/response.json && cat /tmp/response.json
```

### Scale runners up or down without destroying
```bash
# Edit .env: TF_VAR_asg_desired=5
set -a && source .env && set +a
terraform apply   # only ASG desired_capacity changes, nothing else recreated
```

---

## 11. Things to improve in the future

| Improvement | Why | Effort |
|---|---|---|
| Store PAT in AWS Secrets Manager | More secure than Lambda env var; easy to rotate | Medium |
| Add CloudWatch metric for queue depth | Auto-scale ASG based on pending GitHub jobs | High |
| Use GitHub's OIDC instead of PAT | No long-lived secret needed at all | High |
| Add `.gitignore` entry for `terraform.tfstate` | Prevent state file (contains secrets) from being committed | Low |
| Restrict SSH CIDR to your IP | `0.0.0.0/0` allows anyone to attempt SSH | Low |
| Use a custom AMI with deps pre-baked | Avoid 3–5 min install time on every boot | Medium |
