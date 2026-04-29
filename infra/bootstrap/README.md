# Bootstrap

One-time Terraform run that creates the remote-state backend used by every `envs/*` workspace.

Uses **local state** (no `backend` block here). Once applied, do not destroy this without first migrating every other state file off the bucket.

## Apply

```bash
# Suffix should typically be your AWS account ID, to keep the bucket globally unique.
terraform init
terraform apply -var="tfstate_bucket_suffix=$(aws sts get-caller-identity --query Account --output text)"
```

After this, copy the outputs into `infra/envs/dev/backend.tf` (already wired by default to `rosetta-tfstate-<account>`).
