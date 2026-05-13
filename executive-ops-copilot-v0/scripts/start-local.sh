#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.local/logs"
PID_DIR="$ROOT_DIR/.local/pids"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4:latest}"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:5173}"
KEEP_SERVICES_ATTACHED="${KEEP_SERVICES_ATTACHED:-true}"
STARTED_PIDS=()

mkdir -p "$LOG_DIR" "$PID_DIR"

wait_for_http() {
  local url="$1"
  local label="$2"
  local timeout_seconds="${3:-180}"
  local started
  started="$(date +%s)"

  until curl -fsS "$url" >/dev/null 2>&1; do
    if (( "$(date +%s)" - started >= timeout_seconds )); then
      echo "Timed out waiting for $label at $url" >&2
      return 1
    fi
    sleep 1
  done
}

start_ollama() {
  if curl -fsS "$OLLAMA_BASE_URL/api/tags" >/dev/null 2>&1; then
    echo "Ollama is already reachable at $OLLAMA_BASE_URL"
    return
  fi

  echo "Starting Ollama..."
  ollama serve >"$LOG_DIR/ollama.log" 2>&1 &
  echo "$!" >"$PID_DIR/ollama.pid"
  STARTED_PIDS+=("$!")
  wait_for_http "$OLLAMA_BASE_URL/api/tags" "Ollama" 180
}

ensure_model_exists() {
  if curl -fsS "$OLLAMA_BASE_URL/api/tags" | grep -q "\"name\":\"$OLLAMA_MODEL\""; then
    echo "Ollama model is available: $OLLAMA_MODEL"
    return
  fi

  echo "Pulling Ollama model: $OLLAMA_MODEL"
  ollama pull "$OLLAMA_MODEL"
}

start_backend() {
  if curl -fsS "$BACKEND_URL/api/health" >/dev/null 2>&1; then
    echo "Backend is already reachable at $BACKEND_URL"
    curl -fsS "$BACKEND_URL/api/health"
    echo
    return
  fi

  echo "Starting backend and warming model before readiness..."
  bash -c "cd '$ROOT_DIR/backend' && LLM_MODE=ollama OLLAMA_BASE_URL='$OLLAMA_BASE_URL' OLLAMA_MODEL='$OLLAMA_MODEL' WARM_OLLAMA_ON_STARTUP=true python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000" >"$LOG_DIR/backend.log" 2>&1 &
  echo "$!" >"$PID_DIR/backend.pid"
  STARTED_PIDS+=("$!")

  wait_for_http "$BACKEND_URL/api/health" "backend health and model warmup" 240

  local warmup_status
  warmup_status="$(curl -fsS "$BACKEND_URL/api/health")"
  echo "Backend ready: $warmup_status"
}

start_frontend() {
  if curl -fsS "$FRONTEND_URL" >/dev/null 2>&1; then
    echo "Frontend is already reachable at $FRONTEND_URL"
    return
  fi

  echo "Starting frontend..."
  bash -c "cd '$ROOT_DIR/frontend' && VITE_API_BASE_URL='$BACKEND_URL' npm run dev" >"$LOG_DIR/frontend.log" 2>&1 &
  echo "$!" >"$PID_DIR/frontend.pid"
  STARTED_PIDS+=("$!")

  wait_for_http "$FRONTEND_URL" "frontend" 60
  echo "Frontend ready: $FRONTEND_URL"
}

start_ollama
ensure_model_exists
start_backend
start_frontend

echo "All services are ready."
echo "Logs: $LOG_DIR"
echo "PIDs: $PID_DIR"

if [ "$KEEP_SERVICES_ATTACHED" = "true" ] && [ "${#STARTED_PIDS[@]}" -gt 0 ]; then
  echo "Services are attached to this script. Press Ctrl-C to stop them."
  trap 'kill "${STARTED_PIDS[@]}" >/dev/null 2>&1 || true' INT TERM EXIT
  wait "${STARTED_PIDS[@]}"
fi
