#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S_DIR="$ROOT_DIR/infra/k8s"
RENDERED_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-rendered.yaml"
RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-release-rendered.yaml"
DNS_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-dns-release-rendered.yaml"
TLS_PRECREATED_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-precreated-tls-release-rendered.yaml"
RUNTIME_SECRET_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-runtime-secret-release-rendered.yaml"
PUBLIC_ACCESS_ALLOWLIST_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-public-access-allowlist-release-rendered.yaml"
PUBLIC_ACCESS_PROVIDER_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-public-access-provider-release-rendered.yaml"
NETWORK_POLICY_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-network-policy-release-rendered.yaml"
STORAGE_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-storage-release-rendered.yaml"
STORAGE_EXTERNAL_MODEL_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-storage-external-model-release-rendered.yaml"
PRIVATE_GHCR_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-private-ghcr-rendered.yaml"
PRIVATE_GHCR_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-private-ghcr-release-rendered.yaml"
GPU_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-ollama-gpu-rendered.yaml"
GPU_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-ollama-gpu-release-rendered.yaml"
EXTERNAL_MODEL_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-external-model-rendered.yaml"
EXTERNAL_MODEL_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-external-model-release-rendered.yaml"
PRIVATE_GHCR_GPU_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-private-ghcr-ollama-gpu-release-rendered.yaml"
PRIVATE_GHCR_EXTERNAL_MODEL_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-private-ghcr-external-model-release-rendered.yaml"
CERT_MANAGER_ISSUER_MANIFEST="${TMPDIR:-/tmp}/desk-ai-cert-manager-issuer-rendered.yaml"
EXTERNAL_SECRET_MANIFEST="${TMPDIR:-/tmp}/desk-ai-external-secret-rendered.yaml"
SNAPSHOT_MANIFEST="${TMPDIR:-/tmp}/desk-ai-volume-snapshot-rendered.yaml"
TLS_CHECK_OUTPUT="${TMPDIR:-/tmp}/desk-ai-public-tls-check.out"
RUNTIME_SECRET_CHECK_OUTPUT="${TMPDIR:-/tmp}/desk-ai-runtime-secret-check.out"
MODEL_RUNTIME_CHECK_OUTPUT="${TMPDIR:-/tmp}/desk-ai-model-runtime-check.out"
STORAGE_CHECK_OUTPUT="${TMPDIR:-/tmp}/desk-ai-storage-check.out"
PUBLIC_ACCESS_CHECK_OUTPUT="${TMPDIR:-/tmp}/desk-ai-public-access-check.out"
NETWORK_POLICY_CHECK_OUTPUT="${TMPDIR:-/tmp}/desk-ai-network-policy-check.out"
INVALID_PUBLIC_HOST_ERROR="${TMPDIR:-/tmp}/desk-ai-invalid-public-host.err"
INVALID_TLS_MODE_ERROR="${TMPDIR:-/tmp}/desk-ai-invalid-tls-mode.err"
INVALID_PUBLIC_ACCESS_MODE_ERROR="${TMPDIR:-/tmp}/desk-ai-invalid-public-access-mode.err"
MISSING_PUBLIC_ACCESS_CONTROL_ERROR="${TMPDIR:-/tmp}/desk-ai-missing-public-access-control.err"
MISSING_PUBLIC_ALLOWED_CIDRS_ERROR="${TMPDIR:-/tmp}/desk-ai-missing-public-allowed-cidrs.err"
MISSING_NETWORK_POLICY_PROVIDER_ERROR="${TMPDIR:-/tmp}/desk-ai-missing-network-policy-provider.err"
MISSING_NETWORK_POLICY_CONFIRMATION_ERROR="${TMPDIR:-/tmp}/desk-ai-missing-network-policy-confirmation.err"
MISSING_FRONTEND_INGRESS_SELECTOR_ERROR="${TMPDIR:-/tmp}/desk-ai-missing-frontend-ingress-selector.err"
INVALID_MODEL_ENDPOINT_ERROR="${TMPDIR:-/tmp}/desk-ai-invalid-model-endpoint.err"
INVALID_STORAGE_CLASS_ERROR="${TMPDIR:-/tmp}/desk-ai-invalid-storage-class.err"
INVALID_SNAPSHOT_CLASS_ERROR="${TMPDIR:-/tmp}/desk-ai-invalid-snapshot-class.err"
INVALID_ACME_EMAIL_ERROR="${TMPDIR:-/tmp}/desk-ai-invalid-acme-email.err"
INVALID_EXTERNAL_SECRET_ERROR="${TMPDIR:-/tmp}/desk-ai-invalid-external-secret.err"
INVALID_REQUIRE_RUNTIME_SECRET_ERROR="${TMPDIR:-/tmp}/desk-ai-invalid-require-runtime-secret.err"
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
  local model_mode="${2:-in-cluster}"

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

  grep -q "prometheus.io/path: /metrics" "$manifest" || {
    echo "Rendered manifests do not include backend Prometheus scrape metadata." >&2
    exit 1
  }

  grep -q "kubernetes.io/metadata.name: monitoring" "$manifest" || {
    echo "Rendered manifests do not allow the monitoring namespace to scrape backend metrics." >&2
    exit 1
  }

  if [[ "$model_mode" == "external" ]]; then
    if grep -q "name: ollama-ingress" "$manifest"; then
      echo "External model manifests should not include the in-cluster Ollama ingress policy." >&2
      exit 1
    fi
  else
    grep -q "name: ollama-ingress" "$manifest" || {
      echo "Rendered manifests do not include the Ollama ingress policy." >&2
      exit 1
    }
  fi
}

check_sqlite_replica_policy() {
  local manifest="$1"
  if ! command -v ruby >/dev/null 2>&1; then
    echo "Ruby is not installed; skipping SQLite replica policy validation." >&2
    return
  fi

  ruby -e '
    require "yaml"

    docs = YAML.load_stream(File.read(ARGV.fetch(0))).compact
    config = docs.find { |doc| doc["kind"] == "ConfigMap" && doc.dig("metadata", "name") == "desk-ai-config" }
    database_url = config&.dig("data", "DATABASE_URL").to_s
    backend = docs.find { |doc| doc["kind"] == "Deployment" && doc.dig("metadata", "name") == "backend" }
    replicas = backend&.dig("spec", "replicas")

    if database_url.start_with?("sqlite:") && replicas != 1
      warn "Backend replicas must stay at 1 while DATABASE_URL uses SQLite."
      exit 1
    end
  ' "$manifest"
}

check_private_ghcr_invariants() {
  local manifest="$1"

  grep -q "imagePullSecrets:" "$manifest" || {
    echo "Private GHCR manifests do not include imagePullSecrets." >&2
    exit 1
  }

  grep -q "name: ghcr-pull-secret" "$manifest" || {
    echo "Private GHCR manifests do not reference ghcr-pull-secret." >&2
    exit 1
  }
}

check_model_hosting_invariants() {
  local manifest="$1"
  local model_mode="${2:-in-cluster}"

  if ! command -v ruby >/dev/null 2>&1; then
    echo "Ruby is not installed; skipping model hosting invariant validation." >&2
    return
  fi

  ruby -e '
    require "yaml"

    manifest = ARGV.fetch(0)
    mode = ARGV.fetch(1)
    docs = YAML.load_stream(File.read(manifest)).compact
    errors = []

    resource = lambda do |kind, name|
      docs.find { |doc| doc["kind"] == kind && doc.dig("metadata", "name") == name }
    end

    config = resource.call("ConfigMap", "desk-ai-config")
    model_url = config&.dig("data", "OLLAMA_BASE_URL").to_s
    ollama_deployment = resource.call("Deployment", "ollama")
    ollama_service = resource.call("Service", "ollama")
    ollama_pvc = resource.call("PersistentVolumeClaim", "ollama-data")
    ollama_job = resource.call("Job", "ollama-pull-gemma4")
    ollama_policy = resource.call("NetworkPolicy", "ollama-ingress")

    case mode
    when "external"
      present = [
        ["Deployment/ollama", ollama_deployment],
        ["Service/ollama", ollama_service],
        ["PersistentVolumeClaim/ollama-data", ollama_pvc],
        ["Job/ollama-pull-gemma4", ollama_job],
        ["NetworkPolicy/ollama-ingress", ollama_policy],
      ].select { |_name, value| value }.map(&:first)
      errors << "external model manifest still includes #{present.join(", ")}" unless present.empty?
      errors << "external model manifest still points at in-cluster Ollama" if model_url == "http://ollama:11434"
      errors << "external model endpoint must be http(s), got #{model_url.inspect}" unless model_url.match?(/\Ahttps?:\/\/\S+\z/)
    when "gpu"
      errors << "GPU model manifest is missing Deployment/ollama" unless ollama_deployment
      errors << "GPU model manifest is missing Service/ollama" unless ollama_service
      errors << "GPU model manifest is missing PersistentVolumeClaim/ollama-data" unless ollama_pvc
      errors << "GPU model manifest is missing Job/ollama-pull-gemma4" unless ollama_job
      errors << "GPU model manifest is missing NetworkPolicy/ollama-ingress" unless ollama_policy
      errors << "GPU model manifest should keep in-cluster Ollama URL, got #{model_url.inspect}" unless model_url == "http://ollama:11434"

      if ollama_deployment
        template = ollama_deployment.dig("spec", "template", "spec") || {}
        container = (template["containers"] || []).find { |entry| entry["name"] == "ollama" } || {}
        limits = container.dig("resources", "limits") || {}
        node_selector = template["nodeSelector"] || {}
        tolerations = template["tolerations"] || []

        errors << "GPU model manifest must request one NVIDIA GPU limit" unless limits["nvidia.com/gpu"].to_s == "1"
        errors << "GPU model manifest must pin Ollama to desk-ai/model-runtime=ollama-gpu nodes" unless node_selector["desk-ai/model-runtime"] == "ollama-gpu"
        has_toleration = tolerations.any? do |entry|
          entry["key"] == "desk-ai/model-runtime" &&
            entry["operator"] == "Equal" &&
            entry["value"] == "ollama-gpu" &&
            entry["effect"] == "NoSchedule"
        end
        errors << "GPU model manifest must tolerate the ollama-gpu taint" unless has_toleration
      end
    else
      errors << "model manifest is missing Deployment/ollama" unless ollama_deployment
      errors << "model manifest is missing Service/ollama" unless ollama_service
      errors << "model manifest is missing PersistentVolumeClaim/ollama-data" unless ollama_pvc
      errors << "model manifest is missing Job/ollama-pull-gemma4" unless ollama_job
      errors << "model manifest is missing NetworkPolicy/ollama-ingress" unless ollama_policy
      errors << "model manifest should keep in-cluster Ollama URL, got #{model_url.inspect}" unless model_url == "http://ollama:11434"
    end

    unless errors.empty?
      warn errors.join("\n")
      exit 1
    end
  ' "$manifest" "$model_mode"
}

check_storage_policy_invariants() {
  local manifest="$1"
  local model_mode="${2:-in-cluster}"
  local expected_backend_storage_class="${3:-}"
  local expected_ollama_storage_class="${4:-}"

  if ! command -v ruby >/dev/null 2>&1; then
    echo "Ruby is not installed; skipping storage policy invariant validation." >&2
    return
  fi

  ruby -e '
    require "yaml"

    manifest = ARGV.fetch(0)
    mode = ARGV.fetch(1)
    expected_backend_storage_class = ARGV.fetch(2)
    expected_ollama_storage_class = ARGV.fetch(3)
    docs = YAML.load_stream(File.read(manifest)).compact
    errors = []

    resource = lambda do |kind, name|
      docs.find { |doc| doc["kind"] == kind && doc.dig("metadata", "name") == name }
    end

    check_pvc = lambda do |name, role, backup_policy, recovery_priority, expected_storage_class|
      pvc = resource.call("PersistentVolumeClaim", name)
      unless pvc
        errors << "manifest is missing PersistentVolumeClaim/#{name}"
        next
      end

      annotations = pvc.dig("metadata", "annotations") || {}
      access_modes = pvc.dig("spec", "accessModes") || []
      storage = pvc.dig("spec", "resources", "requests", "storage").to_s
      storage_class = pvc.dig("spec", "storageClassName").to_s

      errors << "#{name} must use ReadWriteOnce" unless access_modes.include?("ReadWriteOnce")
      errors << "#{name} must request storage" if storage.empty?
      errors << "#{name} missing desk.ai/storage-role=#{role}" unless annotations["desk.ai/storage-role"] == role
      errors << "#{name} missing desk.ai/backup-policy=#{backup_policy}" unless annotations["desk.ai/backup-policy"] == backup_policy
      errors << "#{name} missing desk.ai/recovery-priority=#{recovery_priority}" unless annotations["desk.ai/recovery-priority"] == recovery_priority
      if !expected_storage_class.empty? && storage_class != expected_storage_class
        errors << "#{name} storageClassName is #{storage_class.inspect}, expected #{expected_storage_class.inspect}"
      end
    end

    check_pvc.call("backend-data", "sqlite-state", "sqlite-online-plus-csi-snapshot", "critical", expected_backend_storage_class)

    if mode == "external"
      errors << "external model manifest should not include PersistentVolumeClaim/ollama-data" if resource.call("PersistentVolumeClaim", "ollama-data")
    else
      check_pvc.call("ollama-data", "model-cache", "recreate-or-csi-snapshot", "rebuildable", expected_ollama_storage_class)
    end

    unless errors.empty?
      warn errors.join("\n")
      exit 1
    end
  ' "$manifest" "$model_mode" "$expected_backend_storage_class" "$expected_ollama_storage_class"
}

check_public_access_invariants() {
  local manifest="$1"
  local expected_mode="$2"
  local expected_cidrs="${3:-}"
  local expected_waf="${4:-}"
  local expected_ddos="${5:-}"
  local expected_identity="${6:-}"

  if ! command -v ruby >/dev/null 2>&1; then
    echo "Ruby is not installed; skipping public access invariant validation." >&2
    return
  fi

  ruby -e '
    require "yaml"

    manifest = ARGV.fetch(0)
    expected_mode = ARGV.fetch(1)
    expected_cidrs = ARGV.fetch(2)
    expected_waf = ARGV.fetch(3)
    expected_ddos = ARGV.fetch(4)
    expected_identity = ARGV.fetch(5)
    docs = YAML.load_stream(File.read(manifest)).compact
    ingress = docs.find { |doc| doc["kind"] == "Ingress" && doc.dig("metadata", "name") == "frontend" }
    errors = []

    if ingress.nil?
      errors << "manifest is missing Ingress/frontend"
    else
      annotations = ingress.dig("metadata", "annotations") || {}
      errors << "desk.ai/public-access-mode is #{annotations["desk.ai/public-access-mode"].inspect}, expected #{expected_mode.inspect}" unless annotations["desk.ai/public-access-mode"] == expected_mode

      if expected_mode == "ip-allowlist"
        errors << "nginx whitelist-source-range is #{annotations["nginx.ingress.kubernetes.io/whitelist-source-range"].inspect}, expected #{expected_cidrs.inspect}" unless annotations["nginx.ingress.kubernetes.io/whitelist-source-range"] == expected_cidrs
        errors << "desk.ai/allowed-cidrs is #{annotations["desk.ai/allowed-cidrs"].inspect}, expected #{expected_cidrs.inspect}" unless annotations["desk.ai/allowed-cidrs"] == expected_cidrs
      end

      if expected_mode == "provider-gated"
        errors << "desk.ai/waf-policy-id is #{annotations["desk.ai/waf-policy-id"].inspect}, expected #{expected_waf.inspect}" unless annotations["desk.ai/waf-policy-id"] == expected_waf
        errors << "desk.ai/ddos-protection is #{annotations["desk.ai/ddos-protection"].inspect}, expected #{expected_ddos.inspect}" unless annotations["desk.ai/ddos-protection"] == expected_ddos
        errors << "desk.ai/identity-provider is #{annotations["desk.ai/identity-provider"].inspect}, expected #{expected_identity.inspect}" unless annotations["desk.ai/identity-provider"] == expected_identity
      end
    end

    unless errors.empty?
      warn errors.join("\n")
      exit 1
    end
  ' "$manifest" "$expected_mode" "$expected_cidrs" "$expected_waf" "$expected_ddos" "$expected_identity"
}

check_network_policy_release_invariants() {
  local manifest="$1"
  local expected_provider="$2"
  local expected_ingress_namespace="$3"
  local expected_ingress_selector="$4"

  if ! command -v ruby >/dev/null 2>&1; then
    echo "Ruby is not installed; skipping network policy release invariant validation." >&2
    return
  fi

  ruby -e '
    require "yaml"

    manifest = ARGV.fetch(0)
    expected_provider = ARGV.fetch(1)
    expected_ingress_namespace = ARGV.fetch(2)
    expected_ingress_selector = ARGV.fetch(3).split(",").to_h { |pair| pair.split("=", 2) }
    docs = YAML.load_stream(File.read(manifest)).compact
    errors = []

    resource = lambda do |kind, name|
      docs.find { |doc| doc["kind"] == kind && doc.dig("metadata", "name") == name }
    end

    ["backend-ingress", "ollama-ingress"].each do |name|
      policy = resource.call("NetworkPolicy", name)
      if policy.nil?
        errors << "manifest is missing NetworkPolicy/#{name}"
        next
      end
      annotations = policy.dig("metadata", "annotations") || {}
      errors << "#{name} network-policy provider is #{annotations["desk.ai/network-policy-provider"].inspect}, expected #{expected_provider.inspect}" unless annotations["desk.ai/network-policy-provider"] == expected_provider
      errors << "#{name} enforcement annotation is #{annotations["desk.ai/network-policy-enforcement"].inspect}, expected \"true\"" unless annotations["desk.ai/network-policy-enforcement"] == "true"
    end

    frontend = resource.call("NetworkPolicy", "frontend-ingress")
    if frontend.nil?
      errors << "manifest is missing NetworkPolicy/frontend-ingress"
    else
      errors << "frontend-ingress must select app=frontend" unless frontend.dig("spec", "podSelector", "matchLabels", "app") == "frontend"
      ingress = frontend.dig("spec", "ingress") || []
      from = ingress.flat_map { |rule| rule["from"] || [] }
      ports = ingress.flat_map { |rule| rule["ports"] || [] }

      errors << "frontend-ingress must allow TCP 80" unless ports.any? { |entry| entry["protocol"].to_s.upcase == "TCP" && entry["port"].to_i == 80 }

      matches = from.any? do |entry|
        ns_labels = entry.dig("namespaceSelector", "matchLabels") || {}
        pod_labels = entry.dig("podSelector", "matchLabels") || {}
        ns_labels["kubernetes.io/metadata.name"] == expected_ingress_namespace &&
          expected_ingress_selector.all? { |key, value| pod_labels[key] == value }
      end
      errors << "frontend-ingress does not allow the expected ingress controller selector" unless matches
    end

    unless errors.empty?
      warn errors.join("\n")
      exit 1
    end
  ' "$manifest" "$expected_provider" "$expected_ingress_namespace" "$expected_ingress_selector"
}

validate_manifest() {
  local manifest="$1"
  local model_mode="${2:-in-cluster}"
  local expected_backend_storage_class="${3:-}"
  local expected_ollama_storage_class="${4:-}"
  parse_yaml "$manifest"
  validate_schema "$manifest"
  check_common_invariants "$manifest" "$model_mode"
  check_sqlite_replica_policy "$manifest"
  check_model_hosting_invariants "$manifest" "$model_mode"
  check_storage_policy_invariants "$manifest" "$model_mode" "$expected_backend_storage_class" "$expected_ollama_storage_class"
}

for script in \
  "$ROOT_DIR/scripts/check-model-runtime.sh" \
  "$ROOT_DIR/scripts/check-network-policy.sh" \
  "$ROOT_DIR/scripts/check-public-access.sh" \
  "$ROOT_DIR/scripts/check-public-dns.sh" \
  "$ROOT_DIR/scripts/check-public-tls.sh" \
  "$ROOT_DIR/scripts/check-runtime-secret.sh" \
  "$ROOT_DIR/scripts/check-storage-policy.sh" \
  "$ROOT_DIR/scripts/render-cert-manager-issuer.sh" \
  "$ROOT_DIR/scripts/render-external-secret.sh" \
  "$ROOT_DIR/scripts/render-release-k8s.sh" \
  "$ROOT_DIR/scripts/render-volume-snapshot.sh"; do
  bash -n "$script"
done

"$KUBECTL" kustomize "$K8S_DIR" > "$RENDERED_MANIFEST"
validate_manifest "$RENDERED_MANIFEST"

"$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$RELEASE_MANIFEST"
validate_manifest "$RELEASE_MANIFEST"

PUBLIC_HOST=desk-ai.example.test TLS_SECRET_NAME=desk-ai-example-tls "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$DNS_RELEASE_MANIFEST"
validate_manifest "$DNS_RELEASE_MANIFEST"

TLS_MODE=precreated-secret PUBLIC_HOST=desk-ai.example.test TLS_SECRET_NAME=desk-ai-manual-tls "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$TLS_PRECREATED_RELEASE_MANIFEST"
validate_manifest "$TLS_PRECREATED_RELEASE_MANIFEST"

REQUIRE_RUNTIME_SECRET=true "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$RUNTIME_SECRET_RELEASE_MANIFEST"
validate_manifest "$RUNTIME_SECRET_RELEASE_MANIFEST"

PUBLIC_HOST=desk-ai.example.test REQUIRE_PUBLIC_ACCESS_CONTROL=true PUBLIC_ACCESS_MODE=ip-allowlist PUBLIC_ALLOWED_CIDRS=203.0.113.10/32,198.51.100.0/24 "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$PUBLIC_ACCESS_ALLOWLIST_RELEASE_MANIFEST"
validate_manifest "$PUBLIC_ACCESS_ALLOWLIST_RELEASE_MANIFEST"
check_public_access_invariants "$PUBLIC_ACCESS_ALLOWLIST_RELEASE_MANIFEST" ip-allowlist "203.0.113.10/32,198.51.100.0/24"

PUBLIC_HOST=desk-ai.example.test REQUIRE_PUBLIC_ACCESS_CONTROL=true PUBLIC_ACCESS_MODE=provider-gated PUBLIC_WAF_POLICY_ID=aws-wafv2-desk-ai-prod PUBLIC_DDOS_PROTECTION=true PUBLIC_IDENTITY_PROVIDER=okta-workforce "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$PUBLIC_ACCESS_PROVIDER_RELEASE_MANIFEST"
validate_manifest "$PUBLIC_ACCESS_PROVIDER_RELEASE_MANIFEST"
check_public_access_invariants "$PUBLIC_ACCESS_PROVIDER_RELEASE_MANIFEST" provider-gated "" aws-wafv2-desk-ai-prod true okta-workforce

REQUIRE_NETWORK_POLICY_ENFORCEMENT=true NETWORK_POLICY_PROVIDER=cilium NETWORK_POLICY_ENFORCEMENT_CONFIRMED=true FRONTEND_INGRESS_POLICY=enabled INGRESS_CONTROLLER_NAMESPACE=ingress-nginx INGRESS_CONTROLLER_POD_SELECTOR=app.kubernetes.io/name=ingress-nginx,app.kubernetes.io/component=controller "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$NETWORK_POLICY_RELEASE_MANIFEST"
validate_manifest "$NETWORK_POLICY_RELEASE_MANIFEST"
check_network_policy_release_invariants "$NETWORK_POLICY_RELEASE_MANIFEST" cilium ingress-nginx app.kubernetes.io/name=ingress-nginx,app.kubernetes.io/component=controller

STORAGE_CLASS_NAME=desk-ai-retain "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$STORAGE_RELEASE_MANIFEST"
validate_manifest "$STORAGE_RELEASE_MANIFEST" in-cluster desk-ai-retain desk-ai-retain

MODEL_ENDPOINT_URL=https://ollama.internal.example.test STORAGE_CLASS_NAME=desk-ai-retain K8S_BASE_DIR="infra/k8s-overlays/external-model" "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$STORAGE_EXTERNAL_MODEL_RELEASE_MANIFEST"
validate_manifest "$STORAGE_EXTERNAL_MODEL_RELEASE_MANIFEST" external desk-ai-retain ""

"$KUBECTL" kustomize "$ROOT_DIR/infra/k8s-overlays/private-ghcr" > "$PRIVATE_GHCR_MANIFEST"
validate_manifest "$PRIVATE_GHCR_MANIFEST"
check_private_ghcr_invariants "$PRIVATE_GHCR_MANIFEST"

K8S_BASE_DIR="infra/k8s-overlays/private-ghcr" "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$PRIVATE_GHCR_RELEASE_MANIFEST"
validate_manifest "$PRIVATE_GHCR_RELEASE_MANIFEST"
check_private_ghcr_invariants "$PRIVATE_GHCR_RELEASE_MANIFEST"

"$KUBECTL" kustomize "$ROOT_DIR/infra/k8s-overlays/ollama-gpu-nvidia" > "$GPU_MANIFEST"
validate_manifest "$GPU_MANIFEST" gpu

K8S_BASE_DIR="infra/k8s-overlays/ollama-gpu-nvidia" "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$GPU_RELEASE_MANIFEST"
validate_manifest "$GPU_RELEASE_MANIFEST" gpu

"$KUBECTL" kustomize "$ROOT_DIR/infra/k8s-overlays/external-model" > "$EXTERNAL_MODEL_MANIFEST"
validate_manifest "$EXTERNAL_MODEL_MANIFEST" external

MODEL_ENDPOINT_URL=https://ollama.internal.example.test K8S_BASE_DIR="infra/k8s-overlays/external-model" "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$EXTERNAL_MODEL_RELEASE_MANIFEST"
validate_manifest "$EXTERNAL_MODEL_RELEASE_MANIFEST" external

if K8S_BASE_DIR="infra/k8s-overlays/external-model" "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee >/dev/null 2>"$INVALID_MODEL_ENDPOINT_ERROR"; then
  echo "Release renderer accepted an external model overlay without MODEL_ENDPOINT_URL." >&2
  exit 1
fi

grep -q "MODEL_ENDPOINT_URL must be set" "$INVALID_MODEL_ENDPOINT_ERROR" || {
  echo "Release renderer did not explain missing MODEL_ENDPOINT_URL input." >&2
  exit 1
}

if STORAGE_CLASS_NAME=Invalid_Class "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee >/dev/null 2>"$INVALID_STORAGE_CLASS_ERROR"; then
  echo "Release renderer accepted an invalid STORAGE_CLASS_NAME." >&2
  exit 1
fi

grep -q "STORAGE_CLASS_NAME must be a valid Kubernetes DNS subdomain name\\|BACKEND_STORAGE_CLASS_NAME must be a valid Kubernetes DNS subdomain name" "$INVALID_STORAGE_CLASS_ERROR" || {
  echo "Release renderer did not explain invalid STORAGE_CLASS_NAME input." >&2
  exit 1
}

if PUBLIC_HOST=desk-ai.example.test REQUIRE_PUBLIC_ACCESS_CONTROL=true "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee >/dev/null 2>"$MISSING_PUBLIC_ACCESS_CONTROL_ERROR"; then
  echo "Release renderer accepted missing PUBLIC_ACCESS_MODE while public access control is required." >&2
  exit 1
fi

grep -q "PUBLIC_ACCESS_MODE must be set when REQUIRE_PUBLIC_ACCESS_CONTROL=true" "$MISSING_PUBLIC_ACCESS_CONTROL_ERROR" || {
  echo "Release renderer did not explain missing PUBLIC_ACCESS_MODE input." >&2
  exit 1
}

if PUBLIC_ACCESS_MODE=invalid "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee >/dev/null 2>"$INVALID_PUBLIC_ACCESS_MODE_ERROR"; then
  echo "Release renderer accepted an invalid PUBLIC_ACCESS_MODE." >&2
  exit 1
fi

grep -q "PUBLIC_ACCESS_MODE must be one of" "$INVALID_PUBLIC_ACCESS_MODE_ERROR" || {
  echo "Release renderer did not explain invalid PUBLIC_ACCESS_MODE input." >&2
  exit 1
}

if PUBLIC_ACCESS_MODE=ip-allowlist "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee >/dev/null 2>"$MISSING_PUBLIC_ALLOWED_CIDRS_ERROR"; then
  echo "Release renderer accepted ip-allowlist mode without PUBLIC_ALLOWED_CIDRS." >&2
  exit 1
fi

grep -q "PUBLIC_ALLOWED_CIDRS must be set" "$MISSING_PUBLIC_ALLOWED_CIDRS_ERROR" || {
  echo "Release renderer did not explain missing PUBLIC_ALLOWED_CIDRS input." >&2
  exit 1
}

if REQUIRE_NETWORK_POLICY_ENFORCEMENT=true "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee >/dev/null 2>"$MISSING_NETWORK_POLICY_PROVIDER_ERROR"; then
  echo "Release renderer accepted required network policy enforcement without NETWORK_POLICY_PROVIDER." >&2
  exit 1
fi

grep -q "NETWORK_POLICY_PROVIDER must be set" "$MISSING_NETWORK_POLICY_PROVIDER_ERROR" || {
  echo "Release renderer did not explain missing NETWORK_POLICY_PROVIDER input." >&2
  exit 1
}

if REQUIRE_NETWORK_POLICY_ENFORCEMENT=true NETWORK_POLICY_PROVIDER=cilium "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee >/dev/null 2>"$MISSING_NETWORK_POLICY_CONFIRMATION_ERROR"; then
  echo "Release renderer accepted required network policy enforcement without confirmation." >&2
  exit 1
fi

grep -q "NETWORK_POLICY_ENFORCEMENT_CONFIRMED=true must be set" "$MISSING_NETWORK_POLICY_CONFIRMATION_ERROR" || {
  echo "Release renderer did not explain missing NETWORK_POLICY_ENFORCEMENT_CONFIRMED input." >&2
  exit 1
}

if FRONTEND_INGRESS_POLICY=enabled INGRESS_CONTROLLER_NAMESPACE=ingress-nginx "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee >/dev/null 2>"$MISSING_FRONTEND_INGRESS_SELECTOR_ERROR"; then
  echo "Release renderer accepted frontend ingress isolation without INGRESS_CONTROLLER_POD_SELECTOR." >&2
  exit 1
fi

grep -q "INGRESS_CONTROLLER_POD_SELECTOR must be set" "$MISSING_FRONTEND_INGRESS_SELECTOR_ERROR" || {
  echo "Release renderer did not explain missing INGRESS_CONTROLLER_POD_SELECTOR input." >&2
  exit 1
}

K8S_BASE_DIR="infra/k8s-overlays/private-ghcr-ollama-gpu-nvidia" "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$PRIVATE_GHCR_GPU_RELEASE_MANIFEST"
validate_manifest "$PRIVATE_GHCR_GPU_RELEASE_MANIFEST" gpu
check_private_ghcr_invariants "$PRIVATE_GHCR_GPU_RELEASE_MANIFEST"

MODEL_ENDPOINT_URL=https://ollama.internal.example.test K8S_BASE_DIR="infra/k8s-overlays/private-ghcr-external-model" "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$PRIVATE_GHCR_EXTERNAL_MODEL_RELEASE_MANIFEST"
validate_manifest "$PRIVATE_GHCR_EXTERNAL_MODEL_RELEASE_MANIFEST" external
check_private_ghcr_invariants "$PRIVATE_GHCR_EXTERNAL_MODEL_RELEASE_MANIFEST"

if PUBLIC_HOST=https://desk-ai.example.test "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee >/dev/null 2>"$INVALID_PUBLIC_HOST_ERROR"; then
  echo "Release renderer accepted an invalid PUBLIC_HOST with scheme." >&2
  exit 1
fi

grep -q "PUBLIC_HOST must be a DNS hostname only" "$INVALID_PUBLIC_HOST_ERROR" || {
  echo "Release renderer did not explain invalid PUBLIC_HOST input." >&2
  exit 1
}

if TLS_MODE=invalid PUBLIC_HOST=desk-ai.example.test "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee >/dev/null 2>"$INVALID_TLS_MODE_ERROR"; then
  echo "Release renderer accepted an invalid TLS_MODE." >&2
  exit 1
fi

grep -q "TLS_MODE must be one of" "$INVALID_TLS_MODE_ERROR" || {
  echo "Release renderer did not explain invalid TLS_MODE input." >&2
  exit 1
}

if REQUIRE_RUNTIME_SECRET=maybe "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee >/dev/null 2>"$INVALID_REQUIRE_RUNTIME_SECRET_ERROR"; then
  echo "Release renderer accepted an invalid REQUIRE_RUNTIME_SECRET value." >&2
  exit 1
fi

grep -q "REQUIRE_RUNTIME_SECRET must be true or false" "$INVALID_REQUIRE_RUNTIME_SECRET_ERROR" || {
  echo "Release renderer did not explain invalid REQUIRE_RUNTIME_SECRET input." >&2
  exit 1
}

if ACME_ENV=staging "$ROOT_DIR/scripts/render-cert-manager-issuer.sh" letsencrypt-staging >/dev/null 2>"$INVALID_ACME_EMAIL_ERROR"; then
  echo "ClusterIssuer renderer accepted missing ACME_EMAIL." >&2
  exit 1
fi

grep -q "ACME_EMAIL must be set" "$INVALID_ACME_EMAIL_ERROR" || {
  echo "ClusterIssuer renderer did not explain missing ACME_EMAIL input." >&2
  exit 1
}

ACME_EMAIL=ops@example.com ACME_ENV=staging "$ROOT_DIR/scripts/render-cert-manager-issuer.sh" letsencrypt-staging > "$CERT_MANAGER_ISSUER_MANIFEST"
parse_yaml "$CERT_MANAGER_ISSUER_MANIFEST"
validate_schema "$CERT_MANAGER_ISSUER_MANIFEST"

grep -q "kind: ClusterIssuer" "$CERT_MANAGER_ISSUER_MANIFEST" || {
  echo "ClusterIssuer renderer did not render a ClusterIssuer." >&2
  exit 1
}

grep -q "server: https://acme-staging-v02.api.letsencrypt.org/directory" "$CERT_MANAGER_ISSUER_MANIFEST" || {
  echo "ClusterIssuer renderer did not use the Let's Encrypt staging server." >&2
  exit 1
}

grep -q "ingressClassName: nginx" "$CERT_MANAGER_ISSUER_MANIFEST" || {
  echo "ClusterIssuer renderer did not configure the nginx HTTP-01 ingress solver." >&2
  exit 1
}

if "$ROOT_DIR/scripts/render-external-secret.sh" >/dev/null 2>"$INVALID_EXTERNAL_SECRET_ERROR"; then
  echo "ExternalSecret renderer accepted a missing SECRET_STORE_NAME." >&2
  exit 1
fi

grep -q "SECRET_STORE_NAME must be set" "$INVALID_EXTERNAL_SECRET_ERROR" || {
  echo "ExternalSecret renderer did not explain missing SECRET_STORE_NAME input." >&2
  exit 1
}

SECRET_STORE_NAME=desk-ai-runtime-secrets REMOTE_SECRET_KEY=desk-ai/production/runtime "$ROOT_DIR/scripts/render-external-secret.sh" > "$EXTERNAL_SECRET_MANIFEST"
parse_yaml "$EXTERNAL_SECRET_MANIFEST"
validate_schema "$EXTERNAL_SECRET_MANIFEST"

grep -q "kind: ExternalSecret" "$EXTERNAL_SECRET_MANIFEST" || {
  echo "ExternalSecret renderer did not render an ExternalSecret." >&2
  exit 1
}

grep -q "name: desk-ai-runtime-secrets" "$EXTERNAL_SECRET_MANIFEST" || {
  echo "ExternalSecret renderer did not use the requested SecretStore name." >&2
  exit 1
}

grep -q "key: desk-ai/production/runtime" "$EXTERNAL_SECRET_MANIFEST" || {
  echo "ExternalSecret renderer did not use the requested remote secret key." >&2
  exit 1
}

if "$ROOT_DIR/scripts/render-volume-snapshot.sh" backend-data backend-data-20260515 >/dev/null 2>"$INVALID_SNAPSHOT_CLASS_ERROR"; then
  echo "VolumeSnapshot renderer accepted a missing VOLUME_SNAPSHOT_CLASS_NAME." >&2
  exit 1
fi

grep -q "VOLUME_SNAPSHOT_CLASS_NAME must be set" "$INVALID_SNAPSHOT_CLASS_ERROR" || {
  echo "VolumeSnapshot renderer did not explain missing VOLUME_SNAPSHOT_CLASS_NAME input." >&2
  exit 1
}

VOLUME_SNAPSHOT_CLASS_NAME=desk-ai-snapshots "$ROOT_DIR/scripts/render-volume-snapshot.sh" backend-data backend-data-20260515 > "$SNAPSHOT_MANIFEST"
parse_yaml "$SNAPSHOT_MANIFEST"
validate_schema "$SNAPSHOT_MANIFEST"

grep -q "kind: VolumeSnapshot" "$SNAPSHOT_MANIFEST" || {
  echo "VolumeSnapshot renderer did not render a VolumeSnapshot." >&2
  exit 1
}

grep -q "volumeSnapshotClassName: desk-ai-snapshots" "$SNAPSHOT_MANIFEST" || {
  echo "VolumeSnapshot renderer did not use the requested VolumeSnapshotClass." >&2
  exit 1
}

grep -q "persistentVolumeClaimName: backend-data" "$SNAPSHOT_MANIFEST" || {
  echo "VolumeSnapshot renderer did not use the requested source PVC." >&2
  exit 1
}

TLS_CHECK_FAKE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/desk-ai-tls-check.XXXXXX")"
trap 'rm -rf "$TLS_CHECK_FAKE_DIR"' EXIT

cat > "$TLS_CHECK_FAKE_DIR/kubectl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

case "$*" in
  *"get ingress frontend -o json"*)
    cat <<'JSON'
{"spec":{"tls":[{"hosts":["desk-ai.example.test"],"secretName":"desk-ai-example-tls"}]}}
JSON
    ;;
  *"get secret desk-ai-example-tls -o json"*)
    cat <<'JSON'
{"type":"kubernetes.io/tls","data":{"tls.crt":"Y2VydA==","tls.key":"a2V5"}}
JSON
    ;;
  *)
    echo "unexpected kubectl args: $*" >&2
    exit 1
    ;;
esac
SH

cat > "$TLS_CHECK_FAKE_DIR/openssl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
echo "Verify return code: 0 (ok)"
SH

chmod +x "$TLS_CHECK_FAKE_DIR/kubectl" "$TLS_CHECK_FAKE_DIR/openssl"

KUBECTL="$TLS_CHECK_FAKE_DIR/kubectl" OPENSSL="$TLS_CHECK_FAKE_DIR/openssl" TLS_SECRET_NAME=desk-ai-example-tls "$ROOT_DIR/scripts/check-public-tls.sh" desk-ai.example.test > "$TLS_CHECK_OUTPUT"

grep -q "Public HTTPS certificate validates for desk-ai.example.test" "$TLS_CHECK_OUTPUT" || {
  echo "Public TLS check did not validate the fake HTTPS certificate." >&2
  exit 1
}

RUNTIME_SECRET_FAKE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/desk-ai-runtime-secret-check.XXXXXX")"
trap 'rm -rf "$TLS_CHECK_FAKE_DIR" "$RUNTIME_SECRET_FAKE_DIR"' EXIT

cat > "$RUNTIME_SECRET_FAKE_DIR/kubectl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

case "$*" in
  *"get secret desk-ai-secrets -o json"*)
    cat <<'JSON'
{"type":"Opaque","data":{"ADMIN_API_KEY":"cmVhbC1hZG1pbi10b2tlbg==","ACTOR_AUTH_TOKEN":"cmVhbC1hY3Rvci10b2tlbg=="}}
JSON
    ;;
  *"get deployment backend -o json"*)
    cat <<'JSON'
{"spec":{"template":{"spec":{"containers":[{"name":"backend","envFrom":[{"configMapRef":{"name":"desk-ai-config"}},{"secretRef":{"name":"desk-ai-secrets","optional":false}}]}]}}}}
JSON
    ;;
  *)
    echo "unexpected kubectl args: $*" >&2
    exit 1
    ;;
esac
SH

chmod +x "$RUNTIME_SECRET_FAKE_DIR/kubectl"

KUBECTL="$RUNTIME_SECRET_FAKE_DIR/kubectl" "$ROOT_DIR/scripts/check-runtime-secret.sh" desk-ai-secrets > "$RUNTIME_SECRET_CHECK_OUTPUT"

grep -q "Secret desk-ai-secrets contains required key" "$RUNTIME_SECRET_CHECK_OUTPUT" || {
  echo "Runtime Secret check did not validate required Secret keys." >&2
  exit 1
}

grep -q "Deployment backend references Secret desk-ai-secrets" "$RUNTIME_SECRET_CHECK_OUTPUT" || {
  echo "Runtime Secret check did not validate backend deployment wiring." >&2
  exit 1
}

MODEL_RUNTIME_FAKE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/desk-ai-model-runtime-check.XXXXXX")"
trap 'rm -rf "$TLS_CHECK_FAKE_DIR" "$RUNTIME_SECRET_FAKE_DIR" "$MODEL_RUNTIME_FAKE_DIR"' EXIT

cat > "$MODEL_RUNTIME_FAKE_DIR/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

case "$*" in
  *"/api/health"*)
    cat <<'JSON'
{"status":"ok","ollama":"configured","model":"ollama_chat/gemma4:latest","adk_model":"ollama_chat/gemma4:latest","ollama_model":"gemma4:latest","model_warmup":{"status":"ready","elapsed_seconds":41.2,"ollama_total_seconds":39.8,"ollama_load_seconds":32.1}}
JSON
    ;;
  *)
    echo "unexpected curl args: $*" >&2
    exit 1
    ;;
esac
SH

chmod +x "$MODEL_RUNTIME_FAKE_DIR/curl"

CURL="$MODEL_RUNTIME_FAKE_DIR/curl" SKIP_CLUSTER_CHECK=true "$ROOT_DIR/scripts/check-model-runtime.sh" https://desk-ai.example.test > "$MODEL_RUNTIME_CHECK_OUTPUT"

grep -q "Model runtime health passed" "$MODEL_RUNTIME_CHECK_OUTPUT" || {
  echo "Model runtime check did not validate the fake backend health payload." >&2
  exit 1
}

STORAGE_CHECK_FAKE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/desk-ai-storage-check.XXXXXX")"
trap 'rm -rf "$TLS_CHECK_FAKE_DIR" "$RUNTIME_SECRET_FAKE_DIR" "$MODEL_RUNTIME_FAKE_DIR" "$STORAGE_CHECK_FAKE_DIR"' EXIT

cat > "$STORAGE_CHECK_FAKE_DIR/kubectl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

case "$*" in
  "get storageclass desk-ai-retain -o json")
    cat <<'JSON'
{"metadata":{"name":"desk-ai-retain"},"provisioner":"csi.example.com","reclaimPolicy":"Retain","allowVolumeExpansion":true}
JSON
    ;;
  "get volumesnapshotclass desk-ai-snapshots")
    exit 0
    ;;
  "-n desk-ai get pvc backend-data -o json")
    cat <<'JSON'
{"metadata":{"name":"backend-data","annotations":{"desk.ai/storage-role":"sqlite-state","desk.ai/backup-policy":"sqlite-online-plus-csi-snapshot","desk.ai/recovery-priority":"critical"}},"spec":{"storageClassName":"desk-ai-retain"},"status":{"phase":"Bound"}}
JSON
    ;;
  "-n desk-ai get pvc ollama-data -o json")
    cat <<'JSON'
{"metadata":{"name":"ollama-data","annotations":{"desk.ai/storage-role":"model-cache","desk.ai/backup-policy":"recreate-or-csi-snapshot","desk.ai/recovery-priority":"rebuildable"}},"spec":{"storageClassName":"desk-ai-retain"},"status":{"phase":"Bound"}}
JSON
    ;;
  *)
    echo "unexpected kubectl args: $*" >&2
    exit 1
    ;;
esac
SH

chmod +x "$STORAGE_CHECK_FAKE_DIR/kubectl"

KUBECTL="$STORAGE_CHECK_FAKE_DIR/kubectl" VOLUME_SNAPSHOT_CLASS_NAME=desk-ai-snapshots REQUIRE_VOLUME_SNAPSHOT_CLASS=true "$ROOT_DIR/scripts/check-storage-policy.sh" desk-ai-retain > "$STORAGE_CHECK_OUTPUT"

grep -q "Storage policy check passed" "$STORAGE_CHECK_OUTPUT" || {
  echo "Storage policy check did not validate the fake StorageClass and PVCs." >&2
  exit 1
}

PUBLIC_ACCESS_CHECK_FAKE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/desk-ai-public-access-check.XXXXXX")"
trap 'rm -rf "$TLS_CHECK_FAKE_DIR" "$RUNTIME_SECRET_FAKE_DIR" "$MODEL_RUNTIME_FAKE_DIR" "$STORAGE_CHECK_FAKE_DIR" "$PUBLIC_ACCESS_CHECK_FAKE_DIR"' EXIT

cat > "$PUBLIC_ACCESS_CHECK_FAKE_DIR/kubectl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

case "$*" in
  *"get ingress frontend -o json"*)
    cat <<'JSON'
{"metadata":{"annotations":{"desk.ai/public-access-mode":"ip-allowlist","desk.ai/allowed-cidrs":"203.0.113.10/32,198.51.100.0/24","nginx.ingress.kubernetes.io/whitelist-source-range":"203.0.113.10/32,198.51.100.0/24"}},"spec":{"tls":[{"hosts":["desk-ai.example.test"],"secretName":"desk-ai-example-tls"}],"rules":[{"host":"desk-ai.example.test"}]}}
JSON
    ;;
  *)
    echo "unexpected kubectl args: $*" >&2
    exit 1
    ;;
esac
SH

chmod +x "$PUBLIC_ACCESS_CHECK_FAKE_DIR/kubectl"

KUBECTL="$PUBLIC_ACCESS_CHECK_FAKE_DIR/kubectl" PUBLIC_ACCESS_MODE=ip-allowlist PUBLIC_ALLOWED_CIDRS=203.0.113.10/32,198.51.100.0/24 "$ROOT_DIR/scripts/check-public-access.sh" desk-ai.example.test > "$PUBLIC_ACCESS_CHECK_OUTPUT"

grep -q "Public access check passed" "$PUBLIC_ACCESS_CHECK_OUTPUT" || {
  echo "Public access check did not validate the fake Ingress access controls." >&2
  exit 1
}

NETWORK_POLICY_CHECK_FAKE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/desk-ai-network-policy-check.XXXXXX")"
trap 'rm -rf "$TLS_CHECK_FAKE_DIR" "$RUNTIME_SECRET_FAKE_DIR" "$MODEL_RUNTIME_FAKE_DIR" "$STORAGE_CHECK_FAKE_DIR" "$PUBLIC_ACCESS_CHECK_FAKE_DIR" "$NETWORK_POLICY_CHECK_FAKE_DIR"' EXIT

cat > "$NETWORK_POLICY_CHECK_FAKE_DIR/kubectl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

case "$*" in
  "-n desk-ai get networkpolicy backend-ingress -o json")
    cat <<'JSON'
{"metadata":{"name":"backend-ingress"},"spec":{"podSelector":{"matchLabels":{"app":"backend"}},"policyTypes":["Ingress"],"ingress":[{"from":[{"podSelector":{"matchLabels":{"app":"frontend"}}},{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"monitoring"}},"podSelector":{"matchLabels":{"app.kubernetes.io/name":"prometheus"}}}],"ports":[{"protocol":"TCP","port":8000}]}]}}
JSON
    ;;
  "-n desk-ai get deployment ollama")
    exit 0
    ;;
  "-n desk-ai get networkpolicy ollama-ingress -o json")
    cat <<'JSON'
{"metadata":{"name":"ollama-ingress"},"spec":{"podSelector":{"matchLabels":{"app":"ollama"}},"policyTypes":["Ingress"],"ingress":[{"from":[{"podSelector":{"matchLabels":{"app":"backend"}}},{"podSelector":{"matchLabels":{"app":"ollama-model-pull"}}}],"ports":[{"protocol":"TCP","port":11434}]}]}}
JSON
    ;;
  "-n desk-ai get networkpolicy frontend-ingress -o json")
    cat <<'JSON'
{"metadata":{"name":"frontend-ingress"},"spec":{"podSelector":{"matchLabels":{"app":"frontend"}},"policyTypes":["Ingress"],"ingress":[{"from":[{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"ingress-nginx"}},"podSelector":{"matchLabels":{"app.kubernetes.io/name":"ingress-nginx","app.kubernetes.io/component":"controller"}}}],"ports":[{"protocol":"TCP","port":80}]}]}}
JSON
    ;;
  "get pods -A -o json")
    cat <<'JSON'
{"items":[{"metadata":{"namespace":"kube-system","name":"cilium-agent-abc","labels":{"app.kubernetes.io/name":"cilium"}}}]}
JSON
    ;;
  *)
    echo "unexpected kubectl args: $*" >&2
    exit 1
    ;;
esac
SH

chmod +x "$NETWORK_POLICY_CHECK_FAKE_DIR/kubectl"

KUBECTL="$NETWORK_POLICY_CHECK_FAKE_DIR/kubectl" REQUIRE_FRONTEND_INGRESS_POLICY=true INGRESS_CONTROLLER_NAMESPACE=ingress-nginx INGRESS_CONTROLLER_POD_SELECTOR=app.kubernetes.io/name=ingress-nginx,app.kubernetes.io/component=controller "$ROOT_DIR/scripts/check-network-policy.sh" desk-ai > "$NETWORK_POLICY_CHECK_OUTPUT"

grep -q "NetworkPolicy check passed" "$NETWORK_POLICY_CHECK_OUTPUT" || {
  echo "NetworkPolicy check did not validate the fake CNI and policy state." >&2
  exit 1
}

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

grep -q "host: desk-ai.example.test" "$DNS_RELEASE_MANIFEST" || {
  echo "DNS release manifests do not use the requested public host." >&2
  exit 1
}

grep -q "secretName: desk-ai-example-tls" "$DNS_RELEASE_MANIFEST" || {
  echo "DNS release manifests do not use the requested TLS Secret name." >&2
  exit 1
}

if grep -q "desk-ai.example.com" "$DNS_RELEASE_MANIFEST"; then
  echo "DNS release manifests still contain the placeholder ingress hostname." >&2
  exit 1
fi

grep -q "cert-manager.io/cluster-issuer: letsencrypt-prod" "$DNS_RELEASE_MANIFEST" || {
  echo "DNS release manifests do not keep the default cert-manager ClusterIssuer." >&2
  exit 1
}

grep -q "secretName: desk-ai-manual-tls" "$TLS_PRECREATED_RELEASE_MANIFEST" || {
  echo "Pre-created TLS release manifests do not use the requested TLS Secret name." >&2
  exit 1
}

if grep -q "cert-manager.io/cluster-issuer" "$TLS_PRECREATED_RELEASE_MANIFEST"; then
  echo "Pre-created TLS release manifests still include the cert-manager ClusterIssuer annotation." >&2
  exit 1
fi

grep -q "name: desk-ai-secrets" "$RUNTIME_SECRET_RELEASE_MANIFEST" || {
  echo "Runtime-secret release manifests do not reference the requested backend Secret name." >&2
  exit 1
}

grep -q "optional: false" "$RUNTIME_SECRET_RELEASE_MANIFEST" || {
  echo "Runtime-secret release manifests do not require the backend Secret." >&2
  exit 1
}

grep -q "ghcr.io/heyyymonth/desk-ai-backend:git-deadbee" "$PRIVATE_GHCR_RELEASE_MANIFEST" || {
  echo "Private GHCR release manifests do not use the requested immutable backend image tag." >&2
  exit 1
}

grep -q "ghcr.io/heyyymonth/desk-ai-frontend:git-deadbee" "$PRIVATE_GHCR_RELEASE_MANIFEST" || {
  echo "Private GHCR release manifests do not use the requested immutable frontend image tag." >&2
  exit 1
}

if grep -q "ghcr.io/heyyymonth/desk-ai-.*:latest" "$PRIVATE_GHCR_RELEASE_MANIFEST"; then
  echo "Private GHCR release manifests still contain mutable latest application image tags." >&2
  exit 1
fi

grep -q "nginx.ingress.kubernetes.io/whitelist-source-range: 203.0.113.10/32,198.51.100.0/24" "$PUBLIC_ACCESS_ALLOWLIST_RELEASE_MANIFEST" || {
  echo "Public access allowlist release does not include the requested nginx source allowlist." >&2
  exit 1
}

grep -q "desk.ai/public-access-mode: ip-allowlist" "$PUBLIC_ACCESS_ALLOWLIST_RELEASE_MANIFEST" || {
  echo "Public access allowlist release does not declare ip-allowlist mode." >&2
  exit 1
}

grep -q "desk.ai/public-access-mode: provider-gated" "$PUBLIC_ACCESS_PROVIDER_RELEASE_MANIFEST" || {
  echo "Public access provider-gated release does not declare provider-gated mode." >&2
  exit 1
}

grep -q "desk.ai/waf-policy-id: aws-wafv2-desk-ai-prod" "$PUBLIC_ACCESS_PROVIDER_RELEASE_MANIFEST" || {
  echo "Public access provider-gated release does not include the selected WAF policy id." >&2
  exit 1
}

grep -q "desk.ai/ddos-protection: \"true\"" "$PUBLIC_ACCESS_PROVIDER_RELEASE_MANIFEST" || {
  echo "Public access provider-gated release does not include DDoS protection acknowledgement." >&2
  exit 1
}

grep -q "desk.ai/identity-provider: okta-workforce" "$PUBLIC_ACCESS_PROVIDER_RELEASE_MANIFEST" || {
  echo "Public access provider-gated release does not include the selected identity provider." >&2
  exit 1
}

grep -q "name: frontend-ingress" "$NETWORK_POLICY_RELEASE_MANIFEST" || {
  echo "NetworkPolicy release does not render frontend ingress isolation." >&2
  exit 1
}

grep -q "kubernetes.io/metadata.name: ingress-nginx" "$NETWORK_POLICY_RELEASE_MANIFEST" || {
  echo "NetworkPolicy release does not include the selected ingress controller namespace." >&2
  exit 1
}

grep -q "app.kubernetes.io/name: ingress-nginx" "$NETWORK_POLICY_RELEASE_MANIFEST" || {
  echo "NetworkPolicy release does not include the selected ingress controller pod selector." >&2
  exit 1
}

grep -q "desk.ai/network-policy-provider: cilium" "$NETWORK_POLICY_RELEASE_MANIFEST" || {
  echo "NetworkPolicy release does not include the selected CNI provider metadata." >&2
  exit 1
}

grep -q "desk.ai/network-policy-enforcement: \"true\"" "$NETWORK_POLICY_RELEASE_MANIFEST" || {
  echo "NetworkPolicy release does not record enforcement confirmation." >&2
  exit 1
}

grep -q "nvidia.com/gpu: \"1\"" "$GPU_RELEASE_MANIFEST" || {
  echo "GPU release manifests do not request one NVIDIA GPU." >&2
  exit 1
}

grep -q "desk-ai/model-runtime: ollama-gpu" "$GPU_RELEASE_MANIFEST" || {
  echo "GPU release manifests do not pin Ollama to the GPU node pool." >&2
  exit 1
}

grep -q "OLLAMA_BASE_URL: https://ollama.internal.example.test" "$EXTERNAL_MODEL_RELEASE_MANIFEST" || {
  echo "External model release manifests do not use the requested model endpoint URL." >&2
  exit 1
}

if grep -q "name: ollama-ingress\\|name: ollama-pull-gemma4\\|name: ollama-data" "$EXTERNAL_MODEL_RELEASE_MANIFEST"; then
  echo "External model release manifests still include in-cluster Ollama resources." >&2
  exit 1
fi

grep -q "storageClassName: desk-ai-retain" "$STORAGE_RELEASE_MANIFEST" || {
  echo "Storage release manifests do not pin PVCs to the requested StorageClass." >&2
  exit 1
}

grep -q "desk.ai/backup-policy: sqlite-online-plus-csi-snapshot" "$STORAGE_RELEASE_MANIFEST" || {
  echo "Storage release manifests do not include the backend backup policy annotation." >&2
  exit 1
}

grep -q "desk.ai/backup-policy: recreate-or-csi-snapshot" "$STORAGE_RELEASE_MANIFEST" || {
  echo "Storage release manifests do not include the Ollama backup policy annotation." >&2
  exit 1
}

grep -q "storageClassName: desk-ai-retain" "$STORAGE_EXTERNAL_MODEL_RELEASE_MANIFEST" || {
  echo "External model storage release does not pin backend-data to the requested StorageClass." >&2
  exit 1
}

if grep -q "name: ollama-data" "$STORAGE_EXTERNAL_MODEL_RELEASE_MANIFEST"; then
  echo "External model storage release still includes the Ollama PVC." >&2
  exit 1
fi

echo "Kubernetes manifests rendered and validated successfully."
