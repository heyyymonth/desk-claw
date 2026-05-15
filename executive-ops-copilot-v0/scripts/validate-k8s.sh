#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S_DIR="$ROOT_DIR/infra/k8s"
RENDERED_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-rendered.yaml"
RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-release-rendered.yaml"
KUBECTL="${KUBECTL:-kubectl}"

parse_yaml() {
  local manifest="$1"
  if command -v ruby >/dev/null 2>&1; then
    ruby -e 'require "yaml"; YAML.load_stream(File.read(ARGV.fetch(0)))' "$manifest"
  else
    echo "Ruby is not installed; skipping YAML stream parse." >&2
  fi
}

validate_schema() {
  local manifest="$1"
  if command -v kubeconform >/dev/null 2>&1; then
    kubeconform -strict -summary -ignore-missing-schemas "$manifest"
  else
    echo "kubeconform is not installed; skipping offline Kubernetes schema validation." >&2
  fi
}

check_common_invariants() {
  local manifest="$1"
  if grep -q "ghcr.io/OWNER" "$manifest"; then
    echo "Rendered manifests still contain placeholder GHCR image names." >&2
    exit 1
  fi

  if grep -q "type: LoadBalancer" "$manifest"; then
    echo "Rendered manifests expose a LoadBalancer service; public traffic should enter through Ingress." >&2
    exit 1
  fi

  grep -q "kind: Ingress" "$manifest" || {
    echo "Rendered manifests do not include an Ingress." >&2
    exit 1
  }

  grep -q "name: desk-ai-secrets" "$manifest" || {
    echo "Rendered manifests do not reference the runtime secret contract." >&2
    exit 1
  }

  grep -q "kind: NetworkPolicy" "$manifest" || {
    echo "Rendered manifests do not include NetworkPolicy resources." >&2
    exit 1
  }

  grep -q "name: backend-ingress" "$manifest" || {
    echo "Rendered manifests do not include the backend ingress policy." >&2
    exit 1
  }

  grep -q "name: ollama-ingress" "$manifest" || {
    echo "Rendered manifests do not include the Ollama ingress policy." >&2
    exit 1
  }
}

validate_manifest() {
  local manifest="$1"
  parse_yaml "$manifest"
  validate_schema "$manifest"
  check_common_invariants "$manifest"
}

"$KUBECTL" kustomize "$K8S_DIR" > "$RENDERED_MANIFEST"
validate_manifest "$RENDERED_MANIFEST"

"$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$RELEASE_MANIFEST"
validate_manifest "$RELEASE_MANIFEST"

grep -q "ghcr.io/heyyymonth/desk-ai-backend:git-deadbee" "$RELEASE_MANIFEST" || {
  echo "Release manifests do not use the requested immutable backend image tag." >&2
  exit 1
}

grep -q "ghcr.io/heyyymonth/desk-ai-frontend:git-deadbee" "$RELEASE_MANIFEST" || {
  echo "Release manifests do not use the requested immutable frontend image tag." >&2
  exit 1
}

if grep -q "ghcr.io/heyyymonth/desk-ai-.*:latest" "$RELEASE_MANIFEST"; then
  echo "Release manifests still contain mutable latest application image tags." >&2
  exit 1
fi

echo "Kubernetes manifests rendered and validated successfully."
