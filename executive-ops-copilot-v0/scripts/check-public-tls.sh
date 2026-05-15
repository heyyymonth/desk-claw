#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: check-public-tls.sh <public-host>

Verifies that Desk AI Ingress TLS is configured and that the public HTTPS certificate validates.

Environment:
  NAMESPACE=desk-ai
  INGRESS_NAME=frontend
  TLS_SECRET_NAME=desk-ai-tls
  KUBECTL=kubectl
  OPENSSL=openssl
  REQUIRE_TLS_SECRET=true
  SKIP_PUBLIC_TLS_PROBE=false
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

NAMESPACE="${NAMESPACE:-desk-ai}"
INGRESS_NAME="${INGRESS_NAME:-frontend}"
TLS_SECRET_NAME="${TLS_SECRET_NAME:-desk-ai-tls}"
KUBECTL="${KUBECTL:-kubectl}"
OPENSSL="${OPENSSL:-openssl}"
REQUIRE_TLS_SECRET="${REQUIRE_TLS_SECRET:-true}"
SKIP_PUBLIC_TLS_PROBE="${SKIP_PUBLIC_TLS_PROBE:-false}"
PUBLIC_HOST="$(printf '%s' "${1%.}" | tr '[:upper:]' '[:lower:]')"

if [[ "$PUBLIC_HOST" =~ ^https?:// || "$PUBLIC_HOST" == */* || "$PUBLIC_HOST" == *:* ]]; then
  echo "Public host must be a DNS hostname only, without scheme, path, or port." >&2
  exit 1
fi

if ! [[ "$PUBLIC_HOST" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$ ]]; then
  echo "Public host must be a valid lower-case DNS hostname with at least one dot." >&2
  exit 1
fi

if ! [[ "$TLS_SECRET_NAME" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]]; then
  echo "TLS_SECRET_NAME must be a valid Kubernetes DNS label." >&2
  exit 1
fi

for binary in "$KUBECTL" ruby; do
  if ! command -v "$binary" >/dev/null 2>&1; then
    echo "Required command is not available: $binary" >&2
    exit 1
  fi
done

if [[ "$SKIP_PUBLIC_TLS_PROBE" != "true" ]] && ! command -v "$OPENSSL" >/dev/null 2>&1; then
  echo "Required command is not available: $OPENSSL" >&2
  exit 1
fi

INGRESS_JSON="$("$KUBECTL" -n "$NAMESPACE" get ingress "$INGRESS_NAME" -o json)"
printf '%s' "$INGRESS_JSON" | ruby -rjson -e '
  host = ARGV.fetch(0)
  secret = ARGV.fetch(1)
  doc = JSON.parse(STDIN.read)
  tls_entries = doc.dig("spec", "tls").to_a
  matching = tls_entries.find do |entry|
    entry.fetch("hosts", []).map { |value| value.downcase.delete_suffix(".") }.include?(host)
  end

  unless matching
    warn "Ingress TLS hosts do not include #{host}."
    exit 1
  end

  if matching["secretName"] != secret
    warn "Ingress TLS host #{host} uses secret #{matching["secretName"].inspect}, expected #{secret.inspect}."
    exit 1
  end
' "$PUBLIC_HOST" "$TLS_SECRET_NAME"

if [[ "$REQUIRE_TLS_SECRET" == "true" ]]; then
  SECRET_JSON="$("$KUBECTL" -n "$NAMESPACE" get secret "$TLS_SECRET_NAME" -o json)"
  printf '%s' "$SECRET_JSON" | ruby -rjson -e '
    secret_name = ARGV.fetch(0)
    doc = JSON.parse(STDIN.read)
    unless doc["type"] == "kubernetes.io/tls"
      warn "Secret #{secret_name} must be type kubernetes.io/tls."
      exit 1
    end

    data = doc["data"] || {}
    unless data["tls.crt"].to_s.length.positive? && data["tls.key"].to_s.length.positive?
      warn "Secret #{secret_name} must contain non-empty tls.crt and tls.key data."
      exit 1
    end
  ' "$TLS_SECRET_NAME"
fi

echo "Ingress TLS config uses host $PUBLIC_HOST and Secret $TLS_SECRET_NAME."

if [[ "$SKIP_PUBLIC_TLS_PROBE" == "true" ]]; then
  echo "Skipped public HTTPS probe because SKIP_PUBLIC_TLS_PROBE=true."
  exit 0
fi

TLS_OUTPUT="$(mktemp)"
trap 'rm -f "$TLS_OUTPUT"' EXIT

if ! "$OPENSSL" s_client -connect "$PUBLIC_HOST:443" -servername "$PUBLIC_HOST" -verify_hostname "$PUBLIC_HOST" -verify_return_error </dev/null >"$TLS_OUTPUT" 2>&1; then
  cat "$TLS_OUTPUT" >&2
  echo "Public HTTPS certificate validation failed for $PUBLIC_HOST." >&2
  exit 1
fi

if ! grep -q "Verify return code: 0 (ok)" "$TLS_OUTPUT"; then
  cat "$TLS_OUTPUT" >&2
  echo "OpenSSL did not report a successful certificate verification for $PUBLIC_HOST." >&2
  exit 1
fi

echo "Public HTTPS certificate validates for $PUBLIC_HOST."
