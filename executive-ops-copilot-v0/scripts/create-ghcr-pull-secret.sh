#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-desk-ai}"
SECRET_NAME="${SECRET_NAME:-ghcr-pull-secret}"
GHCR_SERVER="${GHCR_SERVER:-ghcr.io}"
KUBECTL="${KUBECTL:-kubectl}"

if [[ -z "${GHCR_USERNAME:-}" ]]; then
  echo "GHCR_USERNAME is required." >&2
  exit 1
fi

if [[ -z "${GHCR_TOKEN:-}" ]]; then
  echo "GHCR_TOKEN is required. Use a GitHub token with read:packages for private GHCR images." >&2
  exit 1
fi

"$KUBECTL" create namespace "$NAMESPACE" --dry-run=client -o yaml | "$KUBECTL" apply -f -
"$KUBECTL" -n "$NAMESPACE" create secret docker-registry "$SECRET_NAME" \
  --docker-server="$GHCR_SERVER" \
  --docker-username="$GHCR_USERNAME" \
  --docker-password="$GHCR_TOKEN" \
  --dry-run=client \
  -o yaml | "$KUBECTL" apply -f -

echo "Created or updated image pull secret $NAMESPACE/$SECRET_NAME for $GHCR_SERVER."
