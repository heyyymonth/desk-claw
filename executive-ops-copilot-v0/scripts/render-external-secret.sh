#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: render-external-secret.sh [output-file]

Renders an External Secrets Operator ExternalSecret that creates desk-ai-secrets.

Environment:
  NAMESPACE=desk-ai
  TARGET_SECRET_NAME=desk-ai-secrets
  SECRET_STORE_NAME=<required SecretStore or ClusterSecretStore name>
  SECRET_STORE_KIND=ClusterSecretStore|SecretStore default: ClusterSecretStore
  REMOTE_SECRET_KEY=<required provider secret key/name>
  ADMIN_API_KEY_PROPERTY=ADMIN_API_KEY
  ACTOR_AUTH_TOKEN_PROPERTY=ACTOR_AUTH_TOKEN
  INCLUDE_DATABASE_URL=false
  DATABASE_URL_PROPERTY=DATABASE_URL
  REFRESH_INTERVAL=1h
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

OUTPUT_FILE="${1:-}"
NAMESPACE="${NAMESPACE:-desk-ai}"
TARGET_SECRET_NAME="${TARGET_SECRET_NAME:-desk-ai-secrets}"
SECRET_STORE_NAME="${SECRET_STORE_NAME:-}"
SECRET_STORE_KIND="${SECRET_STORE_KIND:-ClusterSecretStore}"
REMOTE_SECRET_KEY="${REMOTE_SECRET_KEY:-}"
ADMIN_API_KEY_PROPERTY="${ADMIN_API_KEY_PROPERTY:-ADMIN_API_KEY}"
ACTOR_AUTH_TOKEN_PROPERTY="${ACTOR_AUTH_TOKEN_PROPERTY:-ACTOR_AUTH_TOKEN}"
INCLUDE_DATABASE_URL="${INCLUDE_DATABASE_URL:-false}"
DATABASE_URL_PROPERTY="${DATABASE_URL_PROPERTY:-DATABASE_URL}"
REFRESH_INTERVAL="${REFRESH_INTERVAL:-1h}"

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

if [[ -z "$SECRET_STORE_NAME" ]]; then
  echo "SECRET_STORE_NAME must be set to the provider SecretStore or ClusterSecretStore name." >&2
  exit 1
fi
validate_dns_label "$SECRET_STORE_NAME" "SECRET_STORE_NAME"

case "$SECRET_STORE_KIND" in
  ClusterSecretStore | SecretStore) ;;
  *)
    echo "SECRET_STORE_KIND must be ClusterSecretStore or SecretStore." >&2
    exit 1
    ;;
esac

if [[ -z "$REMOTE_SECRET_KEY" || "$REMOTE_SECRET_KEY" =~ [[:space:]] ]]; then
  echo "REMOTE_SECRET_KEY must be set to a provider secret key/name without whitespace." >&2
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

if ! [[ "$REFRESH_INTERVAL" =~ ^[0-9]+[smhd]$ ]]; then
  echo "REFRESH_INTERVAL must use a simple duration such as 15m, 1h, or 1d." >&2
  exit 1
fi

render() {
  cat <<YAML
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: $TARGET_SECRET_NAME
  namespace: $NAMESPACE
spec:
  refreshInterval: $REFRESH_INTERVAL
  secretStoreRef:
    name: $SECRET_STORE_NAME
    kind: $SECRET_STORE_KIND
  target:
    name: $TARGET_SECRET_NAME
    creationPolicy: Owner
    template:
      type: Opaque
  data:
    - secretKey: ADMIN_API_KEY
      remoteRef:
        key: $REMOTE_SECRET_KEY
        property: $ADMIN_API_KEY_PROPERTY
    - secretKey: ACTOR_AUTH_TOKEN
      remoteRef:
        key: $REMOTE_SECRET_KEY
        property: $ACTOR_AUTH_TOKEN_PROPERTY
YAML
  if [[ "$INCLUDE_DATABASE_URL" == "true" ]]; then
    cat <<YAML
    - secretKey: DATABASE_URL
      remoteRef:
        key: $REMOTE_SECRET_KEY
        property: $DATABASE_URL_PROPERTY
YAML
  fi
}

if [[ -n "$OUTPUT_FILE" ]]; then
  render > "$OUTPUT_FILE"
  echo "Rendered ExternalSecret to $OUTPUT_FILE."
else
  render
fi
