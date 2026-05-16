#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: check-model-runtime.sh <public-base-url>

Validates the deployed backend model runtime through /api/health.

Environment:
  EXPECTED_MODEL=gemma4:latest
  MODEL_HOSTING_MODE=in-cluster|gpu|external
  NAMESPACE=desk-ai
  SKIP_CLUSTER_CHECK=false
  EXPECTED_GPU_NODE_SELECTOR=desk-ai/model-runtime=ollama-gpu
  GPU_TOLERATION_KEY=desk-ai/model-runtime
  GPU_TOLERATION_VALUE=ollama-gpu
  GPU_RESOURCE_NAME=nvidia.com/gpu
  GPU_RESOURCE_QUANTITY=1
  KUBECTL=kubectl
  CURL=curl
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

BASE_URL="${1%/}"
EXPECTED_MODEL="${EXPECTED_MODEL:-gemma4:latest}"
MODEL_HOSTING_MODE="${MODEL_HOSTING_MODE:-in-cluster}"
NAMESPACE="${NAMESPACE:-desk-ai}"
SKIP_CLUSTER_CHECK="${SKIP_CLUSTER_CHECK:-false}"
EXPECTED_GPU_NODE_SELECTOR="${EXPECTED_GPU_NODE_SELECTOR:-desk-ai/model-runtime=ollama-gpu}"
GPU_TOLERATION_KEY="${GPU_TOLERATION_KEY:-desk-ai/model-runtime}"
GPU_TOLERATION_VALUE="${GPU_TOLERATION_VALUE:-ollama-gpu}"
GPU_RESOURCE_NAME="${GPU_RESOURCE_NAME:-nvidia.com/gpu}"
GPU_RESOURCE_QUANTITY="${GPU_RESOURCE_QUANTITY:-1}"
KUBECTL="${KUBECTL:-kubectl}"
CURL="${CURL:-curl}"

if ! [[ "$BASE_URL" =~ ^https?://[^[:space:]]+$ ]]; then
  echo "public-base-url must be an http(s) URL without whitespace." >&2
  exit 1
fi

case "$MODEL_HOSTING_MODE" in
  in-cluster | gpu | external) ;;
  *)
    echo "MODEL_HOSTING_MODE must be one of: in-cluster, gpu, external." >&2
    exit 1
    ;;
esac

case "$SKIP_CLUSTER_CHECK" in
  true | false) ;;
  *)
    echo "SKIP_CLUSTER_CHECK must be true or false." >&2
    exit 1
    ;;
esac

if [[ "$MODEL_HOSTING_MODE" == "gpu" && "$EXPECTED_GPU_NODE_SELECTOR" != *=* ]]; then
  echo "EXPECTED_GPU_NODE_SELECTOR must use key=value format." >&2
  exit 1
fi

HEALTH_JSON="$("$CURL" -fsS "$BASE_URL/api/health")"

printf '%s' "$HEALTH_JSON" | EXPECTED_MODEL="$EXPECTED_MODEL" ruby -rjson -e '
  payload = JSON.parse(STDIN.read)
  expected_model = ENV.fetch("EXPECTED_MODEL")
  expected_adk_model = "ollama_chat/#{expected_model}"
  errors = []

  errors << "status is #{payload["status"].inspect}, expected \"ok\"" unless payload["status"] == "ok"
  errors << "ollama is #{payload["ollama"].inspect}, expected \"configured\"" unless payload["ollama"] == "configured"
  errors << "ollama_model is #{payload["ollama_model"].inspect}, expected #{expected_model.inspect}" unless payload["ollama_model"] == expected_model

  adk_model = payload["adk_model"] || payload["model"]
  errors << "ADK model is #{adk_model.inspect}, expected #{expected_adk_model.inspect}" unless adk_model == expected_adk_model

  warmup = payload["model_warmup"] || {}
  errors << "model_warmup.status is #{warmup["status"].inspect}, expected \"ready\"" unless warmup["status"] == "ready"

  unless errors.empty?
    warn "Model runtime check failed:"
    errors.each { |error| warn "- #{error}" }
    exit 1
  end

  puts "Model runtime health passed."
  puts "ADK model: #{adk_model}"
  puts "Ollama model: #{payload["ollama_model"]}"
  puts "Warmup status: #{warmup["status"]}"
  puts "Warmup elapsed seconds: #{warmup["elapsed_seconds"] || "unknown"}"
  puts "Ollama total seconds: #{warmup["ollama_total_seconds"] || "unknown"}"
  puts "Ollama load seconds: #{warmup["ollama_load_seconds"] || "unknown"}"
'

if [[ "$SKIP_CLUSTER_CHECK" == "true" ]]; then
  echo "Skipped Kubernetes model runtime checks."
  exit 0
fi

if [[ "$MODEL_HOSTING_MODE" == "external" ]]; then
  for resource in "deployment/ollama" "service/ollama" "job/ollama-pull-gemma4"; do
    if "$KUBECTL" -n "$NAMESPACE" get "$resource" >/dev/null 2>&1; then
      echo "External model mode should not deploy $resource in namespace $NAMESPACE." >&2
      exit 1
    fi
  done
  echo "External model mode has no in-cluster Ollama runtime resources."
else
  OLLAMA_DEPLOYMENT_JSON="$("$KUBECTL" -n "$NAMESPACE" get deployment/ollama -o json)"
  "$KUBECTL" -n "$NAMESPACE" get service/ollama >/dev/null
  MODEL_PULL_JOB_JSON="$("$KUBECTL" -n "$NAMESPACE" get job/ollama-pull-gemma4 -o json)"

  printf '%s' "$OLLAMA_DEPLOYMENT_JSON" | MODEL_HOSTING_MODE="$MODEL_HOSTING_MODE" EXPECTED_GPU_NODE_SELECTOR="$EXPECTED_GPU_NODE_SELECTOR" GPU_TOLERATION_KEY="$GPU_TOLERATION_KEY" GPU_TOLERATION_VALUE="$GPU_TOLERATION_VALUE" GPU_RESOURCE_NAME="$GPU_RESOURCE_NAME" GPU_RESOURCE_QUANTITY="$GPU_RESOURCE_QUANTITY" ruby -rjson -e '
    deployment = JSON.parse(STDIN.read)
    mode = ENV.fetch("MODEL_HOSTING_MODE")
    errors = []

    available = deployment.dig("status", "conditions").to_a.find { |condition| condition["type"] == "Available" }
    unless available && available["status"] == "True"
      reason = available&.dig("reason")
      message = available&.dig("message")
      detail = [reason, message].compact.reject(&:empty?).join(": ")
      errors << "Deployment/ollama is not Available#{detail.empty? ? "" : " (#{detail})"}."
    end

    spec = deployment.dig("spec", "template", "spec") || {}
    containers = spec["containers"].to_a
    ollama_container = containers.find { |container| container["name"] == "ollama" }
    errors << "Deployment/ollama is missing container named ollama." unless ollama_container

    if mode == "gpu"
      selector_key, selector_value = ENV.fetch("EXPECTED_GPU_NODE_SELECTOR").split("=", 2)
      node_selector = spec["nodeSelector"] || {}
      unless node_selector[selector_key] == selector_value
        errors << "Deployment/ollama nodeSelector #{selector_key.inspect} is #{node_selector[selector_key].inspect}, expected #{selector_value.inspect}."
      end

      toleration_key = ENV.fetch("GPU_TOLERATION_KEY")
      toleration_value = ENV.fetch("GPU_TOLERATION_VALUE")
      toleration = spec["tolerations"].to_a.find do |entry|
        entry["key"] == toleration_key && entry["value"] == toleration_value && entry["effect"] == "NoSchedule"
      end
      errors << "Deployment/ollama is missing NoSchedule toleration #{toleration_key}=#{toleration_value}." unless toleration

      if ollama_container
        resource_name = ENV.fetch("GPU_RESOURCE_NAME")
        expected_quantity = ENV.fetch("GPU_RESOURCE_QUANTITY")
        limits = ollama_container.dig("resources", "limits") || {}
        unless limits[resource_name].to_s == expected_quantity
          errors << "Deployment/ollama GPU limit #{resource_name.inspect} is #{limits[resource_name].inspect}, expected #{expected_quantity.inspect}."
        end
      end
    end

    unless errors.empty?
      warn "Model runtime cluster check failed:"
      errors.each { |error| warn "- #{error}" }
      exit 1
    end

    puts "In-cluster Ollama deployment is Available."
    puts "GPU Ollama scheduling constraints are present." if mode == "gpu"
  '

  printf '%s' "$MODEL_PULL_JOB_JSON" | ruby -rjson -e '
    job = JSON.parse(STDIN.read)
    complete = job.dig("status", "conditions").to_a.find { |condition| condition["type"] == "Complete" }
    succeeded = job.dig("status", "succeeded").to_i
    unless (complete && complete["status"] == "True") || succeeded.positive?
      reason = complete&.dig("reason")
      message = complete&.dig("message")
      detail = [reason, message].compact.reject(&:empty?).join(": ")
      warn "Job/ollama-pull-gemma4 is not complete#{detail.empty? ? "" : " (#{detail})"}."
      exit 1
    end

    puts "Ollama model-pull job completed."
  '

  echo "In-cluster Ollama runtime resources are present."
fi
