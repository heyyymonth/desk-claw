#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: render-cert-manager-issuer.sh <cluster-issuer-name> [output-file]

Renders a cert-manager ClusterIssuer for ACME HTTP-01 issuance.

Environment:
  ACME_EMAIL=<required operator email>
  ACME_ENV=staging|prod              default: staging
  ACME_SERVER=<override URL>          default: Let's Encrypt server for ACME_ENV
  ACME_PRIVATE_KEY_SECRET_NAME=<name> default: <cluster-issuer-name>-account-key
  INGRESS_CLASS_NAME=nginx            default: nginx
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

ISSUER_NAME="$1"
OUTPUT_FILE="${2:-}"
ACME_EMAIL="${ACME_EMAIL:-}"
ACME_ENV="${ACME_ENV:-staging}"
INGRESS_CLASS_NAME="${INGRESS_CLASS_NAME:-nginx}"
ACME_PRIVATE_KEY_SECRET_NAME="${ACME_PRIVATE_KEY_SECRET_NAME:-$ISSUER_NAME-account-key}"

if ! [[ "$ISSUER_NAME" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$ ]]; then
  echo "ClusterIssuer name must be a valid Kubernetes DNS subdomain name." >&2
  exit 1
fi

if [[ -z "$ACME_EMAIL" || "$ACME_EMAIL" =~ [[:space:]] || "$ACME_EMAIL" != *@*.* ]]; then
  echo "ACME_EMAIL must be set to a valid operator email address." >&2
  exit 1
fi

case "$ACME_ENV" in
  staging)
    DEFAULT_ACME_SERVER="https://acme-staging-v02.api.letsencrypt.org/directory"
    ;;
  prod)
    DEFAULT_ACME_SERVER="https://acme-v02.api.letsencrypt.org/directory"
    ;;
  *)
    echo "ACME_ENV must be either staging or prod." >&2
    exit 1
    ;;
esac

ACME_SERVER="${ACME_SERVER:-$DEFAULT_ACME_SERVER}"

if ! [[ "$ACME_SERVER" =~ ^https://[^[:space:]]+$ ]]; then
  echo "ACME_SERVER must be an https URL." >&2
  exit 1
fi

if ! [[ "$ACME_PRIVATE_KEY_SECRET_NAME" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]]; then
  echo "ACME_PRIVATE_KEY_SECRET_NAME must be a valid Kubernetes DNS label." >&2
  exit 1
fi

if ! [[ "$INGRESS_CLASS_NAME" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]]; then
  echo "INGRESS_CLASS_NAME must be a valid Kubernetes DNS label." >&2
  exit 1
fi

render() {
  cat <<YAML
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: $ISSUER_NAME
spec:
  acme:
    email: $ACME_EMAIL
    server: $ACME_SERVER
    privateKeySecretRef:
      name: $ACME_PRIVATE_KEY_SECRET_NAME
    solvers:
      - http01:
          ingress:
            ingressClassName: $INGRESS_CLASS_NAME
YAML
}

if [[ -n "$OUTPUT_FILE" ]]; then
  render > "$OUTPUT_FILE"
  echo "Rendered cert-manager ClusterIssuer to $OUTPUT_FILE."
else
  render
fi
