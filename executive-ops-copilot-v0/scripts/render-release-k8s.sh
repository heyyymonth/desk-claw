#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: render-release-k8s.sh <git-sha|git-<sha>> [output-file]

Renders Kubernetes manifests with immutable backend and frontend image tags.
The SHA must be a 7-40 character git hex SHA, with or without the git- prefix.
Set K8S_BASE_DIR=infra/k8s-overlays/private-ghcr to render the private GHCR pull-secret overlay.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S_BASE_DIR="${K8S_BASE_DIR:-$ROOT_DIR/infra/k8s}"
KUBECTL="${KUBECTL:-kubectl}"

if [[ "$K8S_BASE_DIR" != /* ]]; then
  K8S_BASE_DIR="$ROOT_DIR/$K8S_BASE_DIR"
fi

if [[ "$K8S_BASE_DIR" == "$ROOT_DIR/infra/"* ]]; then
  K8S_RESOURCE_PATH="../${K8S_BASE_DIR#"$ROOT_DIR/infra/"}"
else
  echo "K8S_BASE_DIR must resolve under $ROOT_DIR/infra so the release overlay can reference it safely." >&2
  exit 1
fi

RAW_TAG="$1"
OUTPUT_FILE="${2:-}"
SHA="${RAW_TAG#git-}"
SHA="$(printf '%s' "$SHA" | tr '[:upper:]' '[:lower:]')"

if ! [[ "$SHA" =~ ^[0-9a-f]{7,40}$ ]]; then
  echo "Release image tag must be a 7-40 character git SHA, with or without the git- prefix." >&2
  exit 1
fi

RELEASE_TAG="git-$SHA"
TMP_DIR="$(mktemp -d "$ROOT_DIR/infra/.release.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

cat > "$TMP_DIR/kustomization.yaml" <<YAML
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - $K8S_RESOURCE_PATH
images:
  - name: ghcr.io/heyyymonth/desk-ai-backend
    newName: ghcr.io/heyyymonth/desk-ai-backend
    newTag: $RELEASE_TAG
  - name: ghcr.io/heyyymonth/desk-ai-frontend
    newName: ghcr.io/heyyymonth/desk-ai-frontend
    newTag: $RELEASE_TAG
YAML

if [[ -n "$OUTPUT_FILE" ]]; then
  "$KUBECTL" kustomize --load-restrictor LoadRestrictionsNone "$TMP_DIR" > "$OUTPUT_FILE"
  echo "Rendered release manifests to $OUTPUT_FILE with image tag $RELEASE_TAG."
else
  "$KUBECTL" kustomize --load-restrictor LoadRestrictionsNone "$TMP_DIR"
fi
