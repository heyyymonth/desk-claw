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
  "$KUBECTL" -n "$NAMESPACE" get deployment/ollama >/dev/null
  "$KUBECTL" -n "$NAMESPACE" get service/ollama >/dev/null
  "$KUBECTL" -n "$NAMESPACE" get job/ollama-pull-gemma4 >/dev/null
  echo "In-cluster Ollama runtime resources are present."
fi
