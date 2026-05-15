#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: check-database-runtime.sh <public-base-url>

Validates that the deployed backend is wired for the selected database mode.

Environment:
  NAMESPACE=desk-ai
  CURL=curl
  KUBECTL=kubectl
  DATABASE_MODE=sqlite|postgres
  DATABASE_SECRET_NAME=desk-ai-secrets
  DATABASE_URL_SECRET_KEY=DATABASE_URL
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
NAMESPACE="${NAMESPACE:-desk-ai}"
CURL="${CURL:-curl}"
KUBECTL="${KUBECTL:-kubectl}"
DATABASE_MODE="${DATABASE_MODE:-sqlite}"
DATABASE_SECRET_NAME="${DATABASE_SECRET_NAME:-desk-ai-secrets}"
DATABASE_URL_SECRET_KEY="${DATABASE_URL_SECRET_KEY:-DATABASE_URL}"

case "$DATABASE_MODE" in
  sqlite | postgres) ;;
  *)
    echo "DATABASE_MODE must be sqlite or postgres." >&2
    exit 1
    ;;
esac

HEALTH_JSON="$("$CURL" --fail --silent --show-error "$BASE_URL/api/health")"

printf '%s' "$HEALTH_JSON" | ruby -rjson -e '
  health = JSON.parse(STDIN.read)
  expected = ARGV.fetch(0)
  actual = health.dig("database", "dialect")
  unless actual == expected
    warn "backend health reports database dialect #{actual.inspect}, expected #{expected.inspect}"
    exit 1
  end
' "$DATABASE_MODE"

echo "Backend health reports database dialect $DATABASE_MODE."

if [[ "$DATABASE_MODE" == "postgres" ]]; then
  "$KUBECTL" -n "$NAMESPACE" get secret "$DATABASE_SECRET_NAME" -o json | ruby -rjson -e '
    secret = JSON.parse(STDIN.read)
    key = ARGV.fetch(0)
    unless secret.dig("data", key).to_s.length.positive?
      warn "Secret #{secret.dig("metadata", "name")} does not contain required key #{key}."
      exit 1
    end
  ' "$DATABASE_URL_SECRET_KEY"

  "$KUBECTL" -n "$NAMESPACE" get deployment backend -o json | ruby -rjson -e '
    deployment = JSON.parse(STDIN.read)
    secret_name = ARGV.fetch(0)
    secret_key = ARGV.fetch(1)
    container = deployment.dig("spec", "template", "spec", "containers").find { |entry| entry["name"] == "backend" }
    env = container.fetch("env", [])
    database_url = env.find { |entry| entry["name"] == "DATABASE_URL" }
    volumes = deployment.dig("spec", "template", "spec", "volumes") || []
    volume_mounts = container["volumeMounts"] || []
    errors = []

    unless database_url&.dig("valueFrom", "secretKeyRef", "name") == secret_name &&
        database_url&.dig("valueFrom", "secretKeyRef", "key") == secret_key
      errors << "Deployment/backend does not read DATABASE_URL from Secret #{secret_name}/#{secret_key}."
    end
    errors << "Deployment/backend still mounts backend-data." if volume_mounts.any? { |entry| entry["name"] == "backend-data" }
    errors << "Deployment/backend still defines backend-data volume." if volumes.any? { |entry| entry["name"] == "backend-data" }

    unless errors.empty?
      warn errors.join("\n")
      exit 1
    end
  ' "$DATABASE_SECRET_NAME" "$DATABASE_URL_SECRET_KEY"

  echo "Postgres database Secret and backend deployment wiring are valid."
fi

echo "Database runtime check passed."
