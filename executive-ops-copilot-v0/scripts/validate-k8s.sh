#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S_DIR="$ROOT_DIR/infra/k8s"
RENDERED_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-rendered.yaml"
KUBECTL="${KUBECTL:-kubectl}"

"$KUBECTL" kustomize "$K8S_DIR" > "$RENDERED_MANIFEST"
"$KUBECTL" apply --dry-run=client --validate=false -k "$K8S_DIR" >/dev/null

if grep -q "ghcr.io/OWNER" "$RENDERED_MANIFEST"; then
  echo "Rendered manifests still contain placeholder GHCR image names." >&2
  exit 1
fi

if grep -q "type: LoadBalancer" "$RENDERED_MANIFEST"; then
  echo "Rendered manifests expose a LoadBalancer service; public traffic should enter through Ingress." >&2
  exit 1
fi

grep -q "kind: Ingress" "$RENDERED_MANIFEST" || {
  echo "Rendered manifests do not include an Ingress." >&2
  exit 1
}

grep -q "name: desk-ai-secrets" "$RENDERED_MANIFEST" || {
  echo "Rendered manifests do not reference the runtime secret contract." >&2
  exit 1
}

echo "Kubernetes manifests rendered and validated successfully."
