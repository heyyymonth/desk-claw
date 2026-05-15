#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: smoke-deploy.sh <base-url>

Runs public deployment smoke checks through the same origin exposed by ingress:
  - frontend root responds and serves the Desk AI app shell
  - /api/health responds with status ok
  - /api/rules/default returns deterministic workflow rules
  - /api/calendar/mock returns deterministic workflow calendar context

Environment:
  SMOKE_TIMEOUT_SECONDS  Per-request timeout, default 20.
  SMOKE_RETRIES          Curl retry count, default 2.
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

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required." >&2
  exit 1
fi

if ! command -v ruby >/dev/null 2>&1; then
  echo "ruby is required for JSON response validation." >&2
  exit 1
fi

BASE_URL="${1%/}"
TIMEOUT="${SMOKE_TIMEOUT_SECONDS:-20}"
RETRIES="${SMOKE_RETRIES:-2}"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/desk-ai-smoke.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

if ! [[ "$BASE_URL" =~ ^https?:// ]]; then
  echo "Base URL must start with http:// or https://." >&2
  exit 1
fi

request() {
  local path="$1"
  local output="$2"
  curl \
    --fail \
    --show-error \
    --silent \
    --location \
    --retry "$RETRIES" \
    --retry-all-errors \
    --connect-timeout "$TIMEOUT" \
    --max-time "$TIMEOUT" \
    --output "$output" \
    "$BASE_URL$path"
}

validate_json() {
  local file="$1"
  local script="$2"
  ruby -rjson -e "$script" "$file"
}

echo "Running Desk AI deployment smoke checks against $BASE_URL"

ROOT_HTML="$TMP_DIR/root.html"
request "/" "$ROOT_HTML"
if ! grep -qi "<title>desk.ai</title>" "$ROOT_HTML" && ! grep -q 'id="root"' "$ROOT_HTML"; then
  echo "Frontend root did not look like the Desk AI app shell." >&2
  exit 1
fi
echo "ok frontend root"

HEALTH_JSON="$TMP_DIR/health.json"
request "/api/health" "$HEALTH_JSON"
validate_json "$HEALTH_JSON" '
  payload = JSON.parse(File.read(ARGV.fetch(0)))
  abort("health status was #{payload["status"].inspect}") unless payload["status"] == "ok"
  abort("health response missing model_warmup") unless payload.key?("model_warmup")
'
echo "ok api health"

RULES_JSON="$TMP_DIR/rules.json"
request "/api/rules/default" "$RULES_JSON"
validate_json "$RULES_JSON" '
  payload = JSON.parse(File.read(ARGV.fetch(0)))
  abort("rules response missing executive_name") unless payload["executive_name"].to_s.length.positive?
  hours = payload["working_hours"] || {}
  abort("rules response missing working hours") unless hours["start"].to_s.length.positive? && hours["end"].to_s.length.positive?
'
echo "ok default rules"

CALENDAR_JSON="$TMP_DIR/calendar.json"
request "/api/calendar/mock" "$CALENDAR_JSON"
validate_json "$CALENDAR_JSON" '
  payload = JSON.parse(File.read(ARGV.fetch(0)))
  abort("calendar response missing blocks array") unless payload["blocks"].is_a?(Array)
'
echo "ok mock calendar"

echo "Deployment smoke checks passed."
