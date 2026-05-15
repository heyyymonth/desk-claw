#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: render-release-k8s.sh <git-sha|git-<sha>> [output-file]

Renders Kubernetes manifests with immutable backend and frontend image tags.
The SHA must be a 7-40 character git hex SHA, with or without the git- prefix.
Set K8S_BASE_DIR=infra/k8s-overlays/private-ghcr to render the private GHCR pull-secret overlay.
Set K8S_BASE_DIR=infra/k8s-overlays/ollama-gpu-nvidia for an in-cluster NVIDIA GPU Ollama runtime.
Set K8S_BASE_DIR=infra/k8s-overlays/external-model and MODEL_ENDPOINT_URL=https://ollama.internal.example.com for a private external Ollama-compatible endpoint.
Use infra/k8s-overlays/private-ghcr-ollama-gpu-nvidia or infra/k8s-overlays/private-ghcr-external-model when packages are private and model hosting also needs an overlay.
Set PUBLIC_HOST=desk-ai.example.com to patch the frontend Ingress host and TLS host.
Set TLS_SECRET_NAME=desk-ai-tls to patch the frontend Ingress TLS Secret name.
Set TLS_MODE=cert-manager|precreated-secret|provider-managed to choose how Ingress TLS is issued.
Set TLS_CLUSTER_ISSUER=letsencrypt-prod when TLS_MODE=cert-manager.
Set RUNTIME_SECRET_NAME=desk-ai-secrets to choose the backend runtime Secret.
Set REQUIRE_RUNTIME_SECRET=true for public releases that must fail if runtime secrets are missing.
Set STORAGE_CLASS_NAME=<class> to pin backend-data and ollama-data PVCs to a provider StorageClass.
Set BACKEND_STORAGE_CLASS_NAME or OLLAMA_STORAGE_CLASS_NAME to override one PVC separately.
Set REQUIRE_PUBLIC_ACCESS_CONTROL=true for public releases that must declare an access mode.
Set PUBLIC_ACCESS_MODE=ip-allowlist with PUBLIC_ALLOWED_CIDRS=<cidr,cidr> for nginx ingress CIDR allowlisting.
Set PUBLIC_ACCESS_MODE=provider-gated with PUBLIC_WAF_POLICY_ID, PUBLIC_DDOS_PROTECTION=true, and PUBLIC_IDENTITY_PROVIDER for provider edge controls.
Set REQUIRE_NETWORK_POLICY_ENFORCEMENT=true with NETWORK_POLICY_PROVIDER and NETWORK_POLICY_ENFORCEMENT_CONFIRMED=true once the cluster CNI is verified.
Set FRONTEND_INGRESS_POLICY=enabled with INGRESS_CONTROLLER_NAMESPACE and INGRESS_CONTROLLER_POD_SELECTOR=<key=value,key=value> to isolate frontend ingress to the selected controller.
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
RUNTIME_SECRET_NAME="${RUNTIME_SECRET_NAME:-desk-ai-secrets}"
REQUIRE_RUNTIME_SECRET="${REQUIRE_RUNTIME_SECRET:-false}"
MODEL_ENDPOINT_URL="${MODEL_ENDPOINT_URL:-}"
STORAGE_CLASS_NAME="${STORAGE_CLASS_NAME:-}"
BACKEND_STORAGE_CLASS_NAME="${BACKEND_STORAGE_CLASS_NAME:-$STORAGE_CLASS_NAME}"
OLLAMA_STORAGE_CLASS_NAME="${OLLAMA_STORAGE_CLASS_NAME:-$STORAGE_CLASS_NAME}"
REQUIRE_PUBLIC_ACCESS_CONTROL="${REQUIRE_PUBLIC_ACCESS_CONTROL:-false}"
PUBLIC_ACCESS_MODE="${PUBLIC_ACCESS_MODE:-}"
PUBLIC_ALLOWED_CIDRS="${PUBLIC_ALLOWED_CIDRS:-}"
PUBLIC_WAF_POLICY_ID="${PUBLIC_WAF_POLICY_ID:-}"
PUBLIC_DDOS_PROTECTION="${PUBLIC_DDOS_PROTECTION:-}"
PUBLIC_IDENTITY_PROVIDER="${PUBLIC_IDENTITY_PROVIDER:-}"
REQUIRE_NETWORK_POLICY_ENFORCEMENT="${REQUIRE_NETWORK_POLICY_ENFORCEMENT:-false}"
NETWORK_POLICY_PROVIDER="${NETWORK_POLICY_PROVIDER:-}"
NETWORK_POLICY_ENFORCEMENT_CONFIRMED="${NETWORK_POLICY_ENFORCEMENT_CONFIRMED:-false}"
FRONTEND_INGRESS_POLICY="${FRONTEND_INGRESS_POLICY:-disabled}"
INGRESS_CONTROLLER_NAMESPACE="${INGRESS_CONTROLLER_NAMESPACE:-}"
INGRESS_CONTROLLER_POD_SELECTOR="${INGRESS_CONTROLLER_POD_SELECTOR:-}"

if [[ "$K8S_BASE_DIR" != /* ]]; then
  K8S_BASE_DIR="$ROOT_DIR/$K8S_BASE_DIR"
fi

if [[ "$K8S_BASE_DIR" == "$ROOT_DIR/infra/"* ]]; then
  K8S_RESOURCE_PATH="../${K8S_BASE_DIR#"$ROOT_DIR/infra/"}"
else
  echo "K8S_BASE_DIR must resolve under $ROOT_DIR/infra so the release overlay can reference it safely." >&2
  exit 1
fi

EXTERNAL_MODEL_OVERLAY=false
if [[ "$K8S_BASE_DIR" == "$ROOT_DIR/infra/k8s-overlays/external-model" ]]; then
  EXTERNAL_MODEL_OVERLAY=true
fi
if [[ "$K8S_BASE_DIR" == "$ROOT_DIR/infra/k8s-overlays/private-ghcr-external-model" ]]; then
  EXTERNAL_MODEL_OVERLAY=true
fi

validate_kubernetes_name() {
  local name="$1"
  local label="$2"
  if ! [[ "$name" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$ ]]; then
    echo "$label must be a valid Kubernetes DNS subdomain name." >&2
    exit 1
  fi
}

validate_public_metadata_value() {
  local value="$1"
  local label="$2"
  if ! [[ "$value" =~ ^[A-Za-z0-9._:/=@+-]+$ ]]; then
    echo "$label may only contain letters, numbers, dots, dashes, underscores, slashes, colons, equals, at signs, or plus signs." >&2
    exit 1
  fi
}

validate_cidr_list() {
  local cidrs="$1"
  ruby -ripaddr -e '
    value = ARGV.fetch(0)
    entries = value.split(",").map(&:strip)
    if entries.empty? || entries.any?(&:empty?)
      warn "PUBLIC_ALLOWED_CIDRS must be a comma-separated list of CIDR ranges."
      exit 1
    end
    entries.each do |entry|
      unless entry.include?("/")
        warn "PUBLIC_ALLOWED_CIDRS entry #{entry.inspect} must include a prefix length."
        exit 1
      end
      IPAddr.new(entry)
    rescue ArgumentError
      warn "PUBLIC_ALLOWED_CIDRS entry #{entry.inspect} is not a valid CIDR range."
      exit 1
    end
  ' "$cidrs"
}

validate_kubernetes_label() {
  local value="$1"
  local label="$2"
  if ! [[ "$value" =~ ^[A-Za-z0-9_.:/=,-]+$ ]]; then
    echo "$label may only contain letters, numbers, dots, dashes, underscores, slashes, colons, equals signs, or label separators." >&2
    exit 1
  fi
}

render_match_labels_yaml() {
  local selector="$1"
  local indent="$2"
  ruby -e '
    selector = ARGV.fetch(0)
    indent = Integer(ARGV.fetch(1))
    entries = selector.split(",").map(&:strip)
    if entries.empty? || entries.any?(&:empty?)
      warn "INGRESS_CONTROLLER_POD_SELECTOR must be a comma-separated list of key=value labels."
      exit 1
    end

    entries.each do |entry|
      key, value = entry.split("=", 2)
      if key.to_s.empty? || value.to_s.empty?
        warn "INGRESS_CONTROLLER_POD_SELECTOR entry #{entry.inspect} must use key=value."
        exit 1
      end
      unless key.match?(/\A[A-Za-z0-9_.\/-]+\z/) && value.match?(/\A[A-Za-z0-9_.-]+\z/)
        warn "INGRESS_CONTROLLER_POD_SELECTOR entry #{entry.inspect} contains unsupported label characters."
        exit 1
      end

      escaped = value.gsub("\\", "\\\\\\").gsub("\"", "\\\"")
      puts "#{" " * indent}#{key}: \"#{escaped}\""
    end
  ' "$selector" "$indent"
}

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

if ! [[ "$RUNTIME_SECRET_NAME" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]]; then
  echo "RUNTIME_SECRET_NAME must be a valid Kubernetes DNS label." >&2
  exit 1
fi

if [[ -n "$BACKEND_STORAGE_CLASS_NAME" ]]; then
  validate_kubernetes_name "$BACKEND_STORAGE_CLASS_NAME" "BACKEND_STORAGE_CLASS_NAME"
fi

if [[ -n "$OLLAMA_STORAGE_CLASS_NAME" ]]; then
  validate_kubernetes_name "$OLLAMA_STORAGE_CLASS_NAME" "OLLAMA_STORAGE_CLASS_NAME"
fi

case "$REQUIRE_RUNTIME_SECRET" in
  true | false) ;;
  *)
    echo "REQUIRE_RUNTIME_SECRET must be true or false." >&2
    exit 1
    ;;
esac

case "$REQUIRE_PUBLIC_ACCESS_CONTROL" in
  true | false) ;;
  *)
    echo "REQUIRE_PUBLIC_ACCESS_CONTROL must be true or false." >&2
    exit 1
    ;;
esac

case "$REQUIRE_NETWORK_POLICY_ENFORCEMENT" in
  true | false) ;;
  *)
    echo "REQUIRE_NETWORK_POLICY_ENFORCEMENT must be true or false." >&2
    exit 1
    ;;
esac

case "$NETWORK_POLICY_ENFORCEMENT_CONFIRMED" in
  true | false) ;;
  *)
    echo "NETWORK_POLICY_ENFORCEMENT_CONFIRMED must be true or false." >&2
    exit 1
    ;;
esac

case "$FRONTEND_INGRESS_POLICY" in
  enabled | disabled) ;;
  *)
    echo "FRONTEND_INGRESS_POLICY must be enabled or disabled." >&2
    exit 1
    ;;
esac

if [[ -n "$PUBLIC_ACCESS_MODE" ]]; then
  case "$PUBLIC_ACCESS_MODE" in
    ip-allowlist | provider-gated) ;;
    *)
      echo "PUBLIC_ACCESS_MODE must be one of: ip-allowlist, provider-gated." >&2
      exit 1
      ;;
  esac
fi

if [[ "$REQUIRE_PUBLIC_ACCESS_CONTROL" == "true" && -z "$PUBLIC_ACCESS_MODE" ]]; then
  echo "PUBLIC_ACCESS_MODE must be set when REQUIRE_PUBLIC_ACCESS_CONTROL=true." >&2
  exit 1
fi

if [[ "$PUBLIC_ACCESS_MODE" == "ip-allowlist" ]]; then
  if [[ -z "$PUBLIC_ALLOWED_CIDRS" ]]; then
    echo "PUBLIC_ALLOWED_CIDRS must be set when PUBLIC_ACCESS_MODE=ip-allowlist." >&2
    exit 1
  fi
  validate_cidr_list "$PUBLIC_ALLOWED_CIDRS"
fi

case "$PUBLIC_DDOS_PROTECTION" in
  "" | true | false) ;;
  *)
    echo "PUBLIC_DDOS_PROTECTION must be true or false when set." >&2
    exit 1
    ;;
esac

if [[ -n "$PUBLIC_WAF_POLICY_ID" ]]; then
  validate_public_metadata_value "$PUBLIC_WAF_POLICY_ID" "PUBLIC_WAF_POLICY_ID"
fi

if [[ -n "$PUBLIC_IDENTITY_PROVIDER" ]]; then
  validate_public_metadata_value "$PUBLIC_IDENTITY_PROVIDER" "PUBLIC_IDENTITY_PROVIDER"
fi

if [[ "$PUBLIC_ACCESS_MODE" == "provider-gated" ]]; then
  if [[ -z "$PUBLIC_WAF_POLICY_ID" ]]; then
    echo "PUBLIC_WAF_POLICY_ID must be set when PUBLIC_ACCESS_MODE=provider-gated." >&2
    exit 1
  fi
  if [[ "$PUBLIC_DDOS_PROTECTION" != "true" ]]; then
    echo "PUBLIC_DDOS_PROTECTION=true must be set when PUBLIC_ACCESS_MODE=provider-gated." >&2
    exit 1
  fi
  if [[ -z "$PUBLIC_IDENTITY_PROVIDER" ]]; then
    echo "PUBLIC_IDENTITY_PROVIDER must be set when PUBLIC_ACCESS_MODE=provider-gated." >&2
    exit 1
  fi
fi

if [[ -n "$NETWORK_POLICY_PROVIDER" ]]; then
  validate_public_metadata_value "$NETWORK_POLICY_PROVIDER" "NETWORK_POLICY_PROVIDER"
fi

if [[ "$REQUIRE_NETWORK_POLICY_ENFORCEMENT" == "true" ]]; then
  if [[ -z "$NETWORK_POLICY_PROVIDER" ]]; then
    echo "NETWORK_POLICY_PROVIDER must be set when REQUIRE_NETWORK_POLICY_ENFORCEMENT=true." >&2
    exit 1
  fi
  if [[ "$NETWORK_POLICY_ENFORCEMENT_CONFIRMED" != "true" ]]; then
    echo "NETWORK_POLICY_ENFORCEMENT_CONFIRMED=true must be set when REQUIRE_NETWORK_POLICY_ENFORCEMENT=true." >&2
    exit 1
  fi
fi

if [[ "$FRONTEND_INGRESS_POLICY" == "enabled" ]]; then
  if [[ -z "$INGRESS_CONTROLLER_NAMESPACE" ]]; then
    echo "INGRESS_CONTROLLER_NAMESPACE must be set when FRONTEND_INGRESS_POLICY=enabled." >&2
    exit 1
  fi
  if [[ -z "$INGRESS_CONTROLLER_POD_SELECTOR" ]]; then
    echo "INGRESS_CONTROLLER_POD_SELECTOR must be set when FRONTEND_INGRESS_POLICY=enabled." >&2
    exit 1
  fi
  if ! [[ "$INGRESS_CONTROLLER_NAMESPACE" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]]; then
    echo "INGRESS_CONTROLLER_NAMESPACE must be a valid Kubernetes DNS label." >&2
    exit 1
  fi
  validate_kubernetes_label "$INGRESS_CONTROLLER_POD_SELECTOR" "INGRESS_CONTROLLER_POD_SELECTOR"
  render_match_labels_yaml "$INGRESS_CONTROLLER_POD_SELECTOR" 0 >/dev/null
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

if [[ "$REQUIRE_PUBLIC_ACCESS_CONTROL" == "true" && -z "$PUBLIC_HOST" ]]; then
  echo "PUBLIC_HOST must be set when REQUIRE_PUBLIC_ACCESS_CONTROL=true." >&2
  exit 1
fi

if [[ -n "$MODEL_ENDPOINT_URL" ]]; then
  if ! [[ "$MODEL_ENDPOINT_URL" =~ ^https?://[^[:space:]]+$ ]]; then
    echo "MODEL_ENDPOINT_URL must be an http(s) URL without whitespace." >&2
    exit 1
  fi
fi

if [[ "$EXTERNAL_MODEL_OVERLAY" == "true" && -z "$MODEL_ENDPOINT_URL" ]]; then
  echo "MODEL_ENDPOINT_URL must be set when rendering an external model overlay." >&2
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

EXTRA_RESOURCES=""
if [[ "$FRONTEND_INGRESS_POLICY" == "enabled" ]]; then
  cat > "$TMP_DIR/frontend-ingress-network-policy.yaml" <<YAML
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: frontend-ingress
  namespace: desk-ai
  annotations:
    desk.ai/network-policy-scope: public-ingress
spec:
  podSelector:
    matchLabels:
      app: frontend
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: "$INGRESS_CONTROLLER_NAMESPACE"
          podSelector:
            matchLabels:
$(render_match_labels_yaml "$INGRESS_CONTROLLER_POD_SELECTOR" 14)
      ports:
        - protocol: TCP
          port: 80
YAML
  EXTRA_RESOURCES="  - frontend-ingress-network-policy.yaml"
fi

cat > "$TMP_DIR/kustomization.yaml" <<YAML
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - $K8S_RESOURCE_PATH
$EXTRA_RESOURCES
images:
  - name: ghcr.io/heyyymonth/desk-ai-backend
    newName: ghcr.io/heyyymonth/desk-ai-backend
    newTag: $RELEASE_TAG
  - name: ghcr.io/heyyymonth/desk-ai-frontend
    newName: ghcr.io/heyyymonth/desk-ai-frontend
    newTag: $RELEASE_TAG
YAML

PATCHES_STARTED=false
append_patches_header() {
  if [[ "$PATCHES_STARTED" == "false" ]]; then
    cat >> "$TMP_DIR/kustomization.yaml" <<YAML
patches:
YAML
    PATCHES_STARTED=true
  fi
}

if [[ -n "$PUBLIC_HOST" ]]; then
  append_patches_header
  cat >> "$TMP_DIR/kustomization.yaml" <<YAML
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

if [[ "$REQUIRE_RUNTIME_SECRET" == "true" || "$RUNTIME_SECRET_NAME" != "desk-ai-secrets" ]]; then
  append_patches_header
  cat >> "$TMP_DIR/kustomization.yaml" <<YAML
  - target:
      kind: Deployment
      name: backend
      namespace: desk-ai
    patch: |-
      - op: replace
        path: /spec/template/spec/containers/0/envFrom/1/secretRef/name
        value: $RUNTIME_SECRET_NAME
      - op: replace
        path: /spec/template/spec/containers/0/envFrom/1/secretRef/optional
        value: $([[ "$REQUIRE_RUNTIME_SECRET" == "true" ]] && echo "false" || echo "true")
YAML
fi

if [[ -n "$MODEL_ENDPOINT_URL" ]]; then
  append_patches_header
  cat >> "$TMP_DIR/kustomization.yaml" <<YAML
  - target:
      kind: ConfigMap
      name: desk-ai-config
      namespace: desk-ai
    patch: |-
      - op: replace
        path: /data/OLLAMA_BASE_URL
        value: "$MODEL_ENDPOINT_URL"
YAML
fi

if [[ -n "$BACKEND_STORAGE_CLASS_NAME" ]]; then
  append_patches_header
  cat >> "$TMP_DIR/kustomization.yaml" <<YAML
  - target:
      kind: PersistentVolumeClaim
      name: backend-data
      namespace: desk-ai
    patch: |-
      - op: add
        path: /spec/storageClassName
        value: "$BACKEND_STORAGE_CLASS_NAME"
YAML
fi

if [[ "$EXTERNAL_MODEL_OVERLAY" == "false" && -n "$OLLAMA_STORAGE_CLASS_NAME" ]]; then
  append_patches_header
  cat >> "$TMP_DIR/kustomization.yaml" <<YAML
  - target:
      kind: PersistentVolumeClaim
      name: ollama-data
      namespace: desk-ai
    patch: |-
      - op: add
        path: /spec/storageClassName
        value: "$OLLAMA_STORAGE_CLASS_NAME"
YAML
fi

if [[ -n "$PUBLIC_ACCESS_MODE" ]]; then
  append_patches_header
  cat >> "$TMP_DIR/kustomization.yaml" <<YAML
  - target:
      kind: Ingress
      name: frontend
      namespace: desk-ai
    patch: |-
      - op: add
        path: /metadata/annotations/desk.ai~1public-access-mode
        value: "$PUBLIC_ACCESS_MODE"
YAML

  if [[ "$PUBLIC_ACCESS_MODE" == "ip-allowlist" ]]; then
    cat >> "$TMP_DIR/kustomization.yaml" <<YAML
      - op: add
        path: /metadata/annotations/nginx.ingress.kubernetes.io~1whitelist-source-range
        value: "$PUBLIC_ALLOWED_CIDRS"
      - op: add
        path: /metadata/annotations/desk.ai~1allowed-cidrs
        value: "$PUBLIC_ALLOWED_CIDRS"
YAML
  fi

  if [[ -n "$PUBLIC_WAF_POLICY_ID" ]]; then
    cat >> "$TMP_DIR/kustomization.yaml" <<YAML
      - op: add
        path: /metadata/annotations/desk.ai~1waf-policy-id
        value: "$PUBLIC_WAF_POLICY_ID"
YAML
  fi

  if [[ -n "$PUBLIC_DDOS_PROTECTION" ]]; then
    cat >> "$TMP_DIR/kustomization.yaml" <<YAML
      - op: add
        path: /metadata/annotations/desk.ai~1ddos-protection
        value: "$PUBLIC_DDOS_PROTECTION"
YAML
  fi

  if [[ -n "$PUBLIC_IDENTITY_PROVIDER" ]]; then
    cat >> "$TMP_DIR/kustomization.yaml" <<YAML
      - op: add
        path: /metadata/annotations/desk.ai~1identity-provider
        value: "$PUBLIC_IDENTITY_PROVIDER"
YAML
  fi
fi

if [[ -n "$NETWORK_POLICY_PROVIDER" || "$NETWORK_POLICY_ENFORCEMENT_CONFIRMED" == "true" ]]; then
  for policy_name in backend-ingress ollama-ingress; do
    if [[ "$policy_name" == "ollama-ingress" && "$EXTERNAL_MODEL_OVERLAY" == "true" ]]; then
      continue
    fi
    append_patches_header
    cat >> "$TMP_DIR/kustomization.yaml" <<YAML
  - target:
      kind: NetworkPolicy
      name: $policy_name
      namespace: desk-ai
    patch: |-
      - op: add
        path: /metadata/annotations
        value:
          desk.ai/network-policy-provider: "$NETWORK_POLICY_PROVIDER"
          desk.ai/network-policy-enforcement: "$NETWORK_POLICY_ENFORCEMENT_CONFIRMED"
YAML
  done
fi

if [[ -n "$OUTPUT_FILE" ]]; then
  "$KUBECTL" kustomize --load-restrictor LoadRestrictionsNone "$TMP_DIR" > "$OUTPUT_FILE"
  echo "Rendered release manifests to $OUTPUT_FILE with image tag $RELEASE_TAG."
else
  "$KUBECTL" kustomize --load-restrictor LoadRestrictionsNone "$TMP_DIR"
fi
