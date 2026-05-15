#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: check-runtime-secret.sh [secret-name]

Verifies that the backend runtime Secret exists, contains required keys, and is referenced by the backend deployment.

Environment:
  NAMESPACE=desk-ai
  DEPLOYMENT_NAME=backend
  REQUIRED_KEYS="ADMIN_API_KEY ACTOR_AUTH_TOKEN"
  EXPECT_REQUIRED=true
  KUBECTL=kubectl
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 1 ]]; then
  usage
  exit 1
fi

NAMESPACE="${NAMESPACE:-desk-ai}"
DEPLOYMENT_NAME="${DEPLOYMENT_NAME:-backend}"
SECRET_NAME="${1:-${RUNTIME_SECRET_NAME:-desk-ai-secrets}}"
REQUIRED_KEYS="${REQUIRED_KEYS:-ADMIN_API_KEY ACTOR_AUTH_TOKEN}"
EXPECT_REQUIRED="${EXPECT_REQUIRED:-true}"
KUBECTL="${KUBECTL:-kubectl}"

validate_dns_label() {
  local value="$1"
  local label="$2"
  if ! [[ "$value" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]]; then
    echo "$label must be a valid Kubernetes DNS label." >&2
    exit 1
  fi
}

validate_dns_label "$NAMESPACE" "NAMESPACE"
validate_dns_label "$DEPLOYMENT_NAME" "DEPLOYMENT_NAME"
validate_dns_label "$SECRET_NAME" "secret-name"

case "$EXPECT_REQUIRED" in
  true | false) ;;
  *)
    echo "EXPECT_REQUIRED must be true or false." >&2
    exit 1
    ;;
esac

for binary in "$KUBECTL" ruby; do
  if ! command -v "$binary" >/dev/null 2>&1; then
    echo "Required command is not available: $binary" >&2
    exit 1
  fi
done

SECRET_JSON="$("$KUBECTL" -n "$NAMESPACE" get secret "$SECRET_NAME" -o json)"
DEPLOYMENT_JSON="$("$KUBECTL" -n "$NAMESPACE" get deployment "$DEPLOYMENT_NAME" -o json)"

export REQUIRED_KEYS
printf '%s' "$SECRET_JSON" | ruby -rjson -rbase64 -e '
  secret_name = ARGV.fetch(0)
  doc = JSON.parse(STDIN.read)
  required = ENV.fetch("REQUIRED_KEYS").split

  unless doc["type"] == "Opaque"
    warn "Secret #{secret_name} must be type Opaque."
    exit 1
  end

  data = doc["data"] || {}
  missing = required.select { |key| data[key].to_s.empty? }
  unless missing.empty?
    warn "Secret #{secret_name} is missing required key(s): #{missing.join(", ")}."
    exit 1
  end

  placeholders = []
  required.each do |key|
    value = Base64.decode64(data[key].to_s)
    placeholders << key if value.empty? || value.start_with?("replace-with-")
  end

  unless placeholders.empty?
    warn "Secret #{secret_name} contains placeholder or empty value(s): #{placeholders.join(", ")}."
    exit 1
  end

  puts "Secret #{secret_name} contains required key(s): #{required.join(", ")}."
' "$SECRET_NAME"

printf '%s' "$DEPLOYMENT_JSON" | ruby -rjson -e '
  secret_name = ARGV.fetch(0)
  expect_required = ARGV.fetch(1) == "true"
  deployment_name = ARGV.fetch(2)
  doc = JSON.parse(STDIN.read)
  containers = doc.dig("spec", "template", "spec", "containers").to_a
  backend = containers.find { |container| container["name"] == "backend" } || containers.first
  refs = backend.fetch("envFrom", []).map { |entry| entry["secretRef"] }.compact
  ref = refs.find { |entry| entry["name"] == secret_name }

  unless ref
    warn "Deployment #{deployment_name} does not reference Secret #{secret_name} through envFrom."
    exit 1
  end

  if expect_required && ref["optional"] == true
    warn "Deployment #{deployment_name} references Secret #{secret_name} as optional; production release should require it."
    exit 1
  end

  puts "Deployment #{deployment_name} references Secret #{secret_name} through envFrom."
' "$SECRET_NAME" "$EXPECT_REQUIRED" "$DEPLOYMENT_NAME"
