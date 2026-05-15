#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S_DIR="$ROOT_DIR/infra/k8s"
RENDERED_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-rendered.yaml"
KUBECTL="${KUBECTL:-kubectl}"

"$KUBECTL" kustomize "$K8S_DIR" > "$RENDERED_MANIFEST"

if command -v ruby >/dev/null 2>&1; then
  ruby -e 'require "yaml"; YAML.load_stream(File.read(ARGV.fetch(0)))' "$RENDERED_MANIFEST"
else
  echo "Ruby is not installed; skipping YAML stream parse." >&2
fi

if command -v kubeconform >/dev/null 2>&1; then
  kubeconform -strict -summary -ignore-missing-schemas "$RENDERED_MANIFEST"
else
  echo "kubeconform is not installed; skipping offline Kubernetes schema validation." >&2
fi

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
