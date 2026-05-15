#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: render-release-k8s.sh <git-sha|git-<sha>> [output-file]

Renders Kubernetes manifests with immutable backend and frontend image tags.
The SHA must be a 7-40 character git hex SHA, with or without the git- prefix.
Set K8S_BASE_DIR=infra/k8s-overlays/private-ghcr to render the private GHCR pull-secret overlay.
Set PUBLIC_HOST=desk-ai.example.com to patch the frontend Ingress host and TLS host.
Set TLS_SECRET_NAME=desk-ai-tls to patch the frontend Ingress TLS Secret name.
Set TLS_MODE=cert-manager|precreated-secret|provider-managed to choose how Ingress TLS is issued.
Set TLS_CLUSTER_ISSUER=letsencrypt-prod when TLS_MODE=cert-manager.
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
PUBLIC_HOST="${PUBLIC_HOST:-}"
TLS_SECRET_NAME="${TLS_SECRET_NAME:-desk-ai-tls}"
TLS_MODE="${TLS_MODE:-cert-manager}"
TLS_CLUSTER_ISSUER="${TLS_CLUSTER_ISSUER:-letsencrypt-prod}"

if [[ "$K8S_BASE_DIR" != /* ]]; then
  K8S_BASE_DIR="$ROOT_DIR/$K8S_BASE_DIR"
fi

if [[ "$K8S_BASE_DIR" == "$ROOT_DIR/infra/"* ]]; then
  K8S_RESOURCE_PATH="../${K8S_BASE_DIR#"$ROOT_DIR/infra/"}"
else
  echo "K8S_BASE_DIR must resolve under $ROOT_DIR/infra so the release overlay can reference it safely." >&2
  exit 1
fi

case "$TLS_MODE" in
  cert-manager | precreated-secret | provider-managed) ;;
  *)
    echo "TLS_MODE must be one of: cert-manager, precreated-secret, provider-managed." >&2
    exit 1
    ;;
esac

if ! [[ "$TLS_SECRET_NAME" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]]; then
  echo "TLS_SECRET_NAME must be a valid Kubernetes DNS label." >&2
  exit 1
fi

if [[ "$TLS_MODE" == "cert-manager" ]] && ! [[ "$TLS_CLUSTER_ISSUER" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$ ]]; then
  echo "TLS_CLUSTER_ISSUER must be a valid Kubernetes DNS subdomain name." >&2
  exit 1
fi

if [[ -n "$PUBLIC_HOST" ]]; then
  PUBLIC_HOST="$(printf '%s' "${PUBLIC_HOST%.}" | tr '[:upper:]' '[:lower:]')"
  if [[ "$PUBLIC_HOST" =~ ^https?:// || "$PUBLIC_HOST" == */* || "$PUBLIC_HOST" == *:* ]]; then
    echo "PUBLIC_HOST must be a DNS hostname only, without scheme, path, or port." >&2
    exit 1
  fi
  if ! [[ "$PUBLIC_HOST" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$ ]]; then
    echo "PUBLIC_HOST must be a valid lower-case DNS hostname with at least one dot." >&2
    exit 1
  fi
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

if [[ -n "$PUBLIC_HOST" ]]; then
  cat >> "$TMP_DIR/kustomization.yaml" <<YAML
patches:
  - target:
      kind: Ingress
      name: frontend
      namespace: desk-ai
    patch: |-
      - op: replace
        path: /spec/rules/0/host
        value: $PUBLIC_HOST
      - op: replace
        path: /spec/tls/0/hosts/0
        value: $PUBLIC_HOST
      - op: replace
        path: /spec/tls/0/secretName
        value: $TLS_SECRET_NAME
YAML

  if [[ "$TLS_MODE" == "cert-manager" ]]; then
    cat >> "$TMP_DIR/kustomization.yaml" <<YAML
      - op: replace
        path: /metadata/annotations/cert-manager.io~1cluster-issuer
        value: $TLS_CLUSTER_ISSUER
YAML
  else
    cat >> "$TMP_DIR/kustomization.yaml" <<YAML
      - op: remove
        path: /metadata/annotations/cert-manager.io~1cluster-issuer
YAML
  fi
fi

if [[ -n "$OUTPUT_FILE" ]]; then
  "$KUBECTL" kustomize --load-restrictor LoadRestrictionsNone "$TMP_DIR" > "$OUTPUT_FILE"
  echo "Rendered release manifests to $OUTPUT_FILE with image tag $RELEASE_TAG."
else
  "$KUBECTL" kustomize --load-restrictor LoadRestrictionsNone "$TMP_DIR"
fi
