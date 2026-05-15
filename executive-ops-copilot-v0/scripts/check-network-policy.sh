#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: check-network-policy.sh [namespace]

Validates the deployed Desk AI NetworkPolicy shape and checks for CNI enforcement evidence.

Environment:
  KUBECTL=kubectl
  REQUIRE_CNI_EVIDENCE=true|false
  NETWORK_POLICY_PROVIDER=auto|calico|cilium|antrea|provider-managed|<name>
  NETWORK_POLICY_ENFORCEMENT_CONFIRMED=true|false
  REQUIRE_FRONTEND_INGRESS_POLICY=true|false
  INGRESS_CONTROLLER_NAMESPACE=<namespace>
  INGRESS_CONTROLLER_POD_SELECTOR=<key=value,key=value>
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

NAMESPACE="${1:-desk-ai}"
KUBECTL="${KUBECTL:-kubectl}"
REQUIRE_CNI_EVIDENCE="${REQUIRE_CNI_EVIDENCE:-true}"
NETWORK_POLICY_PROVIDER="${NETWORK_POLICY_PROVIDER:-auto}"
NETWORK_POLICY_ENFORCEMENT_CONFIRMED="${NETWORK_POLICY_ENFORCEMENT_CONFIRMED:-false}"
REQUIRE_FRONTEND_INGRESS_POLICY="${REQUIRE_FRONTEND_INGRESS_POLICY:-false}"
INGRESS_CONTROLLER_NAMESPACE="${INGRESS_CONTROLLER_NAMESPACE:-}"
INGRESS_CONTROLLER_POD_SELECTOR="${INGRESS_CONTROLLER_POD_SELECTOR:-}"

case "$REQUIRE_CNI_EVIDENCE" in
  true | false) ;;
  *)
    echo "REQUIRE_CNI_EVIDENCE must be true or false." >&2
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

case "$REQUIRE_FRONTEND_INGRESS_POLICY" in
  true | false) ;;
  *)
    echo "REQUIRE_FRONTEND_INGRESS_POLICY must be true or false." >&2
    exit 1
    ;;
esac

if ! [[ "$NAMESPACE" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]]; then
  echo "namespace must be a valid Kubernetes DNS label." >&2
  exit 1
fi

validate_selector() {
  local selector="$1"
  ruby -e '
    selector = ARGV.fetch(0)
    entries = selector.split(",").map(&:strip)
    if entries.empty? || entries.any?(&:empty?)
      warn "selector must be a comma-separated list of key=value labels."
      exit 1
    end

    entries.each do |entry|
      key, value = entry.split("=", 2)
      if key.to_s.empty? || value.to_s.empty?
        warn "selector entry #{entry.inspect} must use key=value."
        exit 1
      end
      unless key.match?(/\A[A-Za-z0-9_.\/-]+\z/) && value.match?(/\A[A-Za-z0-9_.-]+\z/)
        warn "selector entry #{entry.inspect} contains unsupported label characters."
        exit 1
      end
    end
  ' "$selector"
}

policy_json() {
  local name="$1"
  "$KUBECTL" -n "$NAMESPACE" get networkpolicy "$name" -o json
}

check_policy() {
  local name="$1"
  local selected_app="$2"
  local port="$3"
  shift 3
  local expected_sources=("$@")

  policy_json "$name" | ruby -rjson -e '
    policy = JSON.parse(STDIN.read)
    selected_app = ARGV.fetch(0)
    port = Integer(ARGV.fetch(1))
    expected_sources = ARGV.drop(2)
    errors = []

    errors << "#{policy.dig("metadata", "name")} selects app=#{policy.dig("spec", "podSelector", "matchLabels", "app").inspect}, expected #{selected_app.inspect}" unless policy.dig("spec", "podSelector", "matchLabels", "app") == selected_app

    ingress = policy.dig("spec", "ingress") || []
    ports = ingress.flat_map { |rule| rule["ports"] || [] }
    errors << "#{policy.dig("metadata", "name")} does not allow TCP #{port}" unless ports.any? { |entry| entry["protocol"].to_s.upcase == "TCP" && entry["port"].to_i == port }

    from = ingress.flat_map { |rule| rule["from"] || [] }
    expected_sources.each do |source|
      kind, selector = source.split(":", 2)
      labels = selector.split(",").to_h { |pair| pair.split("=", 2) }
      matches = from.any? do |entry|
        case kind
        when "pod"
          actual = entry.dig("podSelector", "matchLabels") || {}
          labels.all? { |key, value| actual[key] == value }
        when "namespace"
          actual = entry.dig("namespaceSelector", "matchLabels") || {}
          labels.all? { |key, value| actual[key] == value }
        else
          false
        end
      end
      errors << "#{policy.dig("metadata", "name")} is missing #{source} as an allowed source" unless matches
    end

    unless errors.empty?
      warn errors.join("\n")
      exit 1
    end
  ' "$selected_app" "$port" "${expected_sources[@]}"
}

check_frontend_policy() {
  if [[ -z "$INGRESS_CONTROLLER_NAMESPACE" ]]; then
    echo "INGRESS_CONTROLLER_NAMESPACE must be set when REQUIRE_FRONTEND_INGRESS_POLICY=true." >&2
    exit 1
  fi
  if [[ -z "$INGRESS_CONTROLLER_POD_SELECTOR" ]]; then
    echo "INGRESS_CONTROLLER_POD_SELECTOR must be set when REQUIRE_FRONTEND_INGRESS_POLICY=true." >&2
    exit 1
  fi
  validate_selector "$INGRESS_CONTROLLER_POD_SELECTOR"

  policy_json frontend-ingress | ruby -rjson -e '
    policy = JSON.parse(STDIN.read)
    namespace = ARGV.fetch(0)
    selector = ARGV.fetch(1).split(",").to_h { |pair| pair.split("=", 2) }
    errors = []

    errors << "frontend-ingress selects app=#{policy.dig("spec", "podSelector", "matchLabels", "app").inspect}, expected \"frontend\"" unless policy.dig("spec", "podSelector", "matchLabels", "app") == "frontend"

    ingress = policy.dig("spec", "ingress") || []
    from = ingress.flat_map { |rule| rule["from"] || [] }
    ports = ingress.flat_map { |rule| rule["ports"] || [] }

    errors << "frontend-ingress does not allow TCP 80" unless ports.any? { |entry| entry["protocol"].to_s.upcase == "TCP" && entry["port"].to_i == 80 }

    matches = from.any? do |entry|
      ns_labels = entry.dig("namespaceSelector", "matchLabels") || {}
      pod_labels = entry.dig("podSelector", "matchLabels") || {}
      ns_labels["kubernetes.io/metadata.name"] == namespace &&
        selector.all? { |key, value| pod_labels[key] == value }
    end

    errors << "frontend-ingress does not allow the configured ingress controller selector" unless matches

    unless errors.empty?
      warn errors.join("\n")
      exit 1
    end
  ' "$INGRESS_CONTROLLER_NAMESPACE" "$INGRESS_CONTROLLER_POD_SELECTOR"
}

detect_cni() {
  "$KUBECTL" get pods -A -o json | ruby -rjson -e '
    items = JSON.parse(STDIN.read).fetch("items", [])
    detected = []

    items.each do |pod|
      namespace = pod.dig("metadata", "namespace").to_s
      name = pod.dig("metadata", "name").to_s
      labels = pod.dig("metadata", "labels") || {}
      text = ([namespace, name] + labels.flat_map { |key, value| [key, value] }).join(" ").downcase

      detected << "cilium" if text.include?("cilium")
      detected << "calico" if text.include?("calico")
      detected << "antrea" if text.include?("antrea")
      detected << "amazon-vpc-cni" if text.include?("aws-node") || text.include?("amazon-vpc-cni")
      detected << "azure-npm" if text.include?("azure-npm") || text.include?("azure-network-policy")
    end

    puts detected.uniq.join(",")
  '
}

check_policy backend-ingress backend 8000 \
  pod:app=frontend \
  namespace:kubernetes.io/metadata.name=monitoring
echo "NetworkPolicy/backend-ingress matches Desk AI backend ingress expectations."

if "$KUBECTL" -n "$NAMESPACE" get deployment ollama >/dev/null 2>&1; then
  check_policy ollama-ingress ollama 11434 \
    pod:app=backend \
    pod:app=ollama-model-pull
  echo "NetworkPolicy/ollama-ingress matches in-cluster Ollama ingress expectations."
else
  echo "Skipping NetworkPolicy/ollama-ingress check because Deployment/ollama is not present."
fi

if [[ "$REQUIRE_FRONTEND_INGRESS_POLICY" == "true" ]]; then
  check_frontend_policy
  echo "NetworkPolicy/frontend-ingress matches the configured ingress controller selector."
fi

DETECTED_CNI="$(detect_cni || true)"
if [[ -n "$DETECTED_CNI" ]]; then
  echo "Detected NetworkPolicy-capable CNI evidence: $DETECTED_CNI."
fi

if [[ "$NETWORK_POLICY_PROVIDER" != "auto" && "$NETWORK_POLICY_PROVIDER" != "provider-managed" ]]; then
  if [[ ",$DETECTED_CNI," != *",$NETWORK_POLICY_PROVIDER,"* && "$NETWORK_POLICY_ENFORCEMENT_CONFIRMED" != "true" ]]; then
    echo "NETWORK_POLICY_PROVIDER=$NETWORK_POLICY_PROVIDER was requested but not detected; set NETWORK_POLICY_ENFORCEMENT_CONFIRMED=true only after provider-side verification." >&2
    exit 1
  fi
fi

if [[ "$REQUIRE_CNI_EVIDENCE" == "true" && -z "$DETECTED_CNI" && "$NETWORK_POLICY_ENFORCEMENT_CONFIRMED" != "true" ]]; then
  echo "No NetworkPolicy-capable CNI evidence detected. Confirm the cluster CNI enforces NetworkPolicy before relying on these policies." >&2
  exit 1
fi

if [[ "$NETWORK_POLICY_ENFORCEMENT_CONFIRMED" == "true" ]]; then
  echo "Operator confirmation recorded: NetworkPolicy enforcement is enabled for this cluster."
fi

echo "NetworkPolicy check passed for namespace $NAMESPACE."
