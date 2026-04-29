# Rosetta

Translate infrastructure-as-code between formats: Terraform ↔ AWS CDK (TypeScript / Python / Java / C# / Go) ↔ CloudFormation ↔ SAM.

A web app where a signed-in user uploads a zip of IaC source code, picks a source language and a target language, and downloads a zipped, validated translation. Runs in a single AWS region, deployed with Terraform, frontend on AWS Amplify Hosting, LLM work via Amazon Bedrock (Claude).

## Repo layout

```
infra/        Terraform IaC (single region: us-east-1)
  bootstrap/  One-time apply that creates the tfstate bucket + DDB lock table
  envs/dev/   Dev environment composition
  modules/    Reusable modules (storage, auth, api, lambda, ...)
backend/      Lambda handlers + shared libraries (next turn)
frontend/     Vite + React + TypeScript SPA (next turn)
```

## Prerequisites

- AWS account with admin credentials configured (`aws configure`)
- Terraform 1.10+ (`use_lockfile` S3-native locking was introduced in 1.10)
- A Google Cloud OAuth 2.0 client (Web application) for Cognito federation
  - Authorized redirect URI will be the Cognito Hosted UI URL (output by Terraform)

## First-time setup

Five steps, in order. Run from the `Rosetta/` repo root.

```bash
# Capture your AWS account ID once for reuse below.
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# 1. Bootstrap the remote-state backend (one-time, uses LOCAL state).
#    Creates rosetta-tfstate-<ACCOUNT_ID> bucket (versioned + encrypted).
#    State locking uses S3-native locking (use_lockfile=true) — no DynamoDB needed.
cd infra/bootstrap
terraform init
terraform apply -var="tfstate_bucket_suffix=${ACCOUNT_ID}"
cd ../..

# 2. Point the dev environment at the bucket created in step 1.
#    Replace CHANGE_ME with your account ID in infra/envs/dev/backend.tf.
sed -i "s/rosetta-tfstate-239248123204/rosetta-tfstate-${ACCOUNT_ID}/" \
  infra/envs/dev/backend.tf

# 3. Create the Google OAuth secret in SSM (one-time, manual).
#    Get the client ID + secret from Google Cloud Console > Credentials.
aws ssm put-parameter \
  --name "/rosetta/dev/google_oauth_client_secret" \
  --type SecureString \
  --value "<paste-google-client-secret>" \
  --region us-east-1

# 4. Configure the dev tfvars: paste the Google client ID, set frontend URLs.
cd infra/envs/dev
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars in your editor

# 5. Apply the dev environment.
terraform init
terraform apply
```

After step 5, Terraform outputs the Cognito Hosted UI domain. Copy it back to
the Google Cloud Console as an **Authorized redirect URI**:
`https://<domain>/oauth2/idpresponse`.

## Status

Foundation only — see `C:\Users\matis\.claude\plans\build-a-web-application-iridescent-biscuit.md` for the full plan.
Currently implemented: directory scaffold, Terraform bootstrap, dev env composition, **storage** module, **auth** module.
Pending: Lambda layers, CRUD Lambdas, API Gateway, Step Functions, frontend, observability.
