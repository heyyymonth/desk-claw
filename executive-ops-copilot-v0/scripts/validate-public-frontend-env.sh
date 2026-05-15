#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
CI_FILE="$REPO_ROOT/.github/workflows/ci.yml"
FRONTEND_DOCKERFILE="$ROOT_DIR/frontend/Dockerfile"
FORBIDDEN_VITE_VARS=("VITE_ADMIN_API_KEY" "VITE_ACTOR_AUTH_TOKEN")

for var_name in "${FORBIDDEN_VITE_VARS[@]}"; do
  if [[ -n "${!var_name:-}" ]]; then
    echo "$var_name must not be set for public frontend builds." >&2
    exit 1
  fi
done

if ! command -v ruby >/dev/null 2>&1; then
  echo "Ruby is required for CI workflow validation." >&2
  exit 1
fi

ruby -e '
  require "yaml"

  ci_file = ARGV.fetch(0)
  forbidden = ARGV.fetch(1).split(",")
  workflow = YAML.load_file(ci_file)
  job = workflow.fetch("jobs").fetch("frontend-container-image")
  build_step = job.fetch("steps").find { |step| step["name"] == "Build frontend image" }
  abort("Could not find frontend container image build step.") unless build_step

  build_args = build_step.fetch("with", {}).fetch("build-args", "").to_s
  forbidden.each do |name|
    if build_args.include?(name)
      abort("Public frontend image build must not pass #{name}.")
    end
  end
' "$CI_FILE" "$(IFS=,; echo "${FORBIDDEN_VITE_VARS[*]}")"

for var_name in "${FORBIDDEN_VITE_VARS[@]}"; do
  if grep -Eq "^(ARG|ENV)[[:space:]]+$var_name([[:space:]=]|$)" "$FRONTEND_DOCKERFILE"; then
    echo "Frontend Dockerfile must not declare $var_name." >&2
    exit 1
  fi
done

echo "Public frontend build environment is free of browser-bundled admin or actor secrets."

