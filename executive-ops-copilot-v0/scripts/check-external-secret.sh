#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: check-external-secret.sh [external-secret-name]

Verifies that the External Secrets Operator ExternalSecret is ready and maps the expected remote secret properties.

Environment:
  NAMESPACE=desk-ai
  TARGET_SECRET_NAME=desk-ai-secrets
  SECRET_STORE_NAME=<optional expected store name>
  SECRET_STORE_KIND=<optional expected ClusterSecretStore or SecretStore>
  REMOTE_SECRET_KEY=<optional expected provider secret key/name>
  REQUIRED_KEYS="ADMIN_API_KEY ACTOR_AUTH_TOKEN"
  ADMIN_API_KEY_PROPERTY=ADMIN_API_KEY
  ACTOR_AUTH_TOKEN_PROPERTY=ACTOR_AUTH_TOKEN
  INCLUDE_DATABASE_URL=false
  DATABASE_URL_PROPERTY=DATABASE_URL
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
TARGET_SECRET_NAME="${TARGET_SECRET_NAME:-desk-ai-secrets}"
EXTERNAL_SECRET_NAME="${1:-$TARGET_SECRET_NAME}"
SECRET_STORE_NAME="${SECRET_STORE_NAME:-}"
SECRET_STORE_KIND="${SECRET_STORE_KIND:-}"
REMOTE_SECRET_KEY="${REMOTE_SECRET_KEY:-}"
REQUIRED_KEYS="${REQUIRED_KEYS:-ADMIN_API_KEY ACTOR_AUTH_TOKEN}"
ADMIN_API_KEY_PROPERTY="${ADMIN_API_KEY_PROPERTY:-ADMIN_API_KEY}"
ACTOR_AUTH_TOKEN_PROPERTY="${ACTOR_AUTH_TOKEN_PROPERTY:-ACTOR_AUTH_TOKEN}"
INCLUDE_DATABASE_URL="${INCLUDE_DATABASE_URL:-false}"
DATABASE_URL_PROPERTY="${DATABASE_URL_PROPERTY:-DATABASE_URL}"
KUBECTL="${KUBECTL:-kubectl}"

validate_dns_label() {
  local value="$1"
  local label="$2"
  if ! [[ "$value" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]]; then
    echo "$label must be a valid Kubernetes DNS label." >&2
    exit 1
  fi
}

validate_secret_key() {
  local value="$1"
  local label="$2"
  if ! [[ "$value" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "$label must be a valid Secret data key and environment variable name." >&2
    exit 1
  fi
}

validate_dns_label "$NAMESPACE" "NAMESPACE"
validate_dns_label "$TARGET_SECRET_NAME" "TARGET_SECRET_NAME"
validate_dns_label "$EXTERNAL_SECRET_NAME" "external-secret-name"

if [[ -n "$SECRET_STORE_NAME" ]]; then
  validate_dns_label "$SECRET_STORE_NAME" "SECRET_STORE_NAME"
fi

case "$SECRET_STORE_KIND" in
  "" | ClusterSecretStore | SecretStore) ;;
  *)
    echo "SECRET_STORE_KIND must be ClusterSecretStore or SecretStore when set." >&2
    exit 1
    ;;
esac

if [[ -n "$REMOTE_SECRET_KEY" && "$REMOTE_SECRET_KEY" =~ [[:space:]] ]]; then
  echo "REMOTE_SECRET_KEY must not contain whitespace." >&2
  exit 1
fi

validate_secret_key "$ADMIN_API_KEY_PROPERTY" "ADMIN_API_KEY_PROPERTY"
validate_secret_key "$ACTOR_AUTH_TOKEN_PROPERTY" "ACTOR_AUTH_TOKEN_PROPERTY"
validate_secret_key "$DATABASE_URL_PROPERTY" "DATABASE_URL_PROPERTY"

case "$INCLUDE_DATABASE_URL" in
  true | false) ;;
  *)
    echo "INCLUDE_DATABASE_URL must be true or false." >&2
    exit 1
    ;;
esac

for binary in "$KUBECTL" ruby; do
  if ! command -v "$binary" >/dev/null 2>&1; then
    echo "Required command is not available: $binary" >&2
    exit 1
  fi
done

if [[ "$INCLUDE_DATABASE_URL" == "true" && " $REQUIRED_KEYS " != *" DATABASE_URL "* ]]; then
  REQUIRED_KEYS="$REQUIRED_KEYS DATABASE_URL"
fi

EXTERNAL_SECRET_JSON="$("$KUBECTL" -n "$NAMESPACE" get externalsecret "$EXTERNAL_SECRET_NAME" -o json)"

export REQUIRED_KEYS ADMIN_API_KEY_PROPERTY ACTOR_AUTH_TOKEN_PROPERTY DATABASE_URL_PROPERTY
printf '%s' "$EXTERNAL_SECRET_JSON" | ruby -rjson -e '
  external_secret_name = ARGV.fetch(0)
  target_secret_name = ARGV.fetch(1)
  expected_store_name = ARGV.fetch(2)
  expected_store_kind = ARGV.fetch(3)
  expected_remote_key = ARGV.fetch(4)
  doc = JSON.parse(STDIN.read)
  spec = doc["spec"] || {}
  errors = []

  target_name = spec.dig("target", "name")
  errors << "ExternalSecret #{external_secret_name} targets #{target_name.inspect}, expected #{target_secret_name.inspect}." unless target_name == target_secret_name

  store = spec["secretStoreRef"] || {}
  if expected_store_name.length.positive? && store["name"] != expected_store_name
    errors << "ExternalSecret #{external_secret_name} uses SecretStore #{store["name"].inspect}, expected #{expected_store_name.inspect}."
  end
  if expected_store_kind.length.positive? && store["kind"] != expected_store_kind
    errors << "ExternalSecret #{external_secret_name} uses SecretStore kind #{store["kind"].inspect}, expected #{expected_store_kind.inspect}."
  end

  required_keys = ENV.fetch("REQUIRED_KEYS").split
  expected_properties = {
    "ADMIN_API_KEY" => ENV.fetch("ADMIN_API_KEY_PROPERTY"),
    "ACTOR_AUTH_TOKEN" => ENV.fetch("ACTOR_AUTH_TOKEN_PROPERTY"),
    "DATABASE_URL" => ENV.fetch("DATABASE_URL_PROPERTY")
  }
  data = spec["data"].to_a

  required_keys.each do |key|
    mapping = data.find { |entry| entry["secretKey"] == key }
    unless mapping
      errors << "ExternalSecret #{external_secret_name} is missing secretKey mapping for #{key}."
      next
    end

    remote = mapping["remoteRef"] || {}
    if expected_remote_key.length.positive? && remote["key"] != expected_remote_key
      errors << "ExternalSecret #{external_secret_name} maps #{key} from remote key #{remote["key"].inspect}, expected #{expected_remote_key.inspect}."
    end

    expected_property = expected_properties[key]
    if expected_property && remote["property"] != expected_property
      errors << "ExternalSecret #{external_secret_name} maps #{key} from property #{remote["property"].inspect}, expected #{expected_property.inspect}."
    end
  end

  ready = doc.dig("status", "conditions").to_a.find { |condition| condition["type"] == "Ready" }
  unless ready && ready["status"] == "True"
    reason = ready&.dig("reason")
    message = ready&.dig("message")
    detail = [reason, message].compact.reject(&:empty?).join(": ")
    errors << "ExternalSecret #{external_secret_name} is not Ready#{detail.empty? ? "" : " (#{detail})"}."
  end

  unless errors.empty?
    warn errors.join("\n")
    exit 1
  end

  puts "ExternalSecret #{external_secret_name} is Ready and maps required key(s): #{required_keys.join(", ")}."
' "$EXTERNAL_SECRET_NAME" "$TARGET_SECRET_NAME" "$SECRET_STORE_NAME" "$SECRET_STORE_KIND" "$REMOTE_SECRET_KEY"
