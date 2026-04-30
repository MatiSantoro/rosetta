#!/usr/bin/env bash
# build-layers.sh — Build Lambda layer dependencies locally before deploying.
#
# Must be run once after cloning, and again if layer requirements change.
# Requires: Python 3.x, pip, curl, unzip
#
# Usage:
#   bash scripts/build-layers.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAYERS_DIR="$REPO_ROOT/backend/layers"

echo "=== Building Lambda layers ==="
echo "Repo root: $REPO_ROOT"
echo ""

# ── 1. cfn-lint Python layer ─────────────────────────────────────────────────
CFNLINT_DIR="$LAYERS_DIR/python-deps/python"
echo "[1/2] cfn-lint layer → $CFNLINT_DIR"

rm -rf "$CFNLINT_DIR"
mkdir -p "$CFNLINT_DIR"

pip install cfn-lint \
  --platform manylinux2014_aarch64 \
  --python-version 313 \
  --target "$CFNLINT_DIR" \
  --only-binary=:all: \
  --quiet

# Remove packages already present in the Lambda runtime to stay under 250 MB
echo "  Trimming runtime-provided packages (boto3, botocore, urllib3)..."
for pkg in boto3 botocore s3transfer urllib3; do
  find "$CFNLINT_DIR" -maxdepth 1 -name "${pkg}*" -exec rm -rf {} + 2>/dev/null || true
done
find "$CFNLINT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

SIZE=$(du -sh "$CFNLINT_DIR" 2>/dev/null | cut -f1)
echo "  Done — layer size: $SIZE"

# ── 2. Terraform binary layer ─────────────────────────────────────────────────
TF_VERSION="1.12.2"
TF_BIN_DIR="$LAYERS_DIR/terraform-bin/bin"
TF_BIN="$TF_BIN_DIR/terraform"
TF_ZIP="/tmp/terraform_${TF_VERSION}_linux_arm64.zip"
TF_URL="https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_arm64.zip"

echo ""
echo "[2/2] Terraform $TF_VERSION binary layer → $TF_BIN"

rm -rf "$TF_BIN_DIR"
mkdir -p "$TF_BIN_DIR"

echo "  Downloading $TF_URL ..."
curl -fsSL "$TF_URL" -o "$TF_ZIP"

echo "  Extracting..."
unzip -q "$TF_ZIP" terraform -d "$TF_BIN_DIR"
chmod +x "$TF_BIN"
rm -f "$TF_ZIP"

SIZE=$(du -sh "$TF_BIN" 2>/dev/null | cut -f1)
echo "  Done — binary size: $SIZE"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== All layers built successfully ==="
echo "You can now run terraform apply in infra/envs/dev or infra/envs/prod."
