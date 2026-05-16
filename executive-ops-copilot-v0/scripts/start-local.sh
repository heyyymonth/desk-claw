#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.local/logs"
PID_DIR="$ROOT_DIR/.local/pids"
AI_BACKEND_URL="${AI_BACKEND_URL:-http://127.0.0.1:9000}"
WEB_BACKEND_URL="${WEB_BACKEND_URL:-http://127.0.0.1:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:5173}"
KEEP_SERVICES_ATTACHED="${KEEP_SERVICES_ATTACHED:-true}"
STARTED_PIDS=()

mkdir -p "$LOG_DIR" "$PID_DIR"

wait_for_http() {
  local url="$1"
  local label="$2"
  local timeout_seconds="${3:-180}"
  local log_file="${4:-}"
  local started
  started="$(date +%s)"

  until curl -fsS "$url" >/dev/null 2>&1; do
    if (( "$(date +%s)" - started >= timeout_seconds )); then
      echo "Timed out waiting for $label at $url" >&2
      if [ -n "$log_file" ] && [ -f "$log_file" ]; then
        echo "Last logs for $label:" >&2
        tail -n 80 "$log_file" >&2
      fi
      return 1
    fi
    sleep 1
  done
}

start_ai_backend() {
  if curl -fsS "$AI_BACKEND_URL/health" >/dev/null 2>&1; then
    echo "AI Backend is already reachable at $AI_BACKEND_URL"
    return
  fi

  echo "Starting AI Backend..."
  bash -c "cd '$ROOT_DIR/ai_backend' && python3 -m uvicorn main:app --host 127.0.0.1 --port 9000" >"$LOG_DIR/ai-backend.log" 2>&1 &
  echo "$!" >"$PID_DIR/ai-backend.pid"
  STARTED_PIDS+=("$!")

  wait_for_http "$AI_BACKEND_URL/health" "AI Backend health" 120 "$LOG_DIR/ai-backend.log"
  echo "AI Backend ready: $AI_BACKEND_URL"
}

start_web_backend() {
  if curl -fsS "$WEB_BACKEND_URL/health" >/dev/null 2>&1; then
    echo "Web Backend is already reachable at $WEB_BACKEND_URL"
    curl -fsS "$WEB_BACKEND_URL/health"
    echo
    return
  fi

  echo "Starting Web Backend..."
  bash -c "cd '$ROOT_DIR/web_backend' && AI_BACKEND_URL='$AI_BACKEND_URL' python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000" >"$LOG_DIR/web-backend.log" 2>&1 &
  echo "$!" >"$PID_DIR/web-backend.pid"
  STARTED_PIDS+=("$!")

  wait_for_http "$WEB_BACKEND_URL/health" "Web Backend health" 240 "$LOG_DIR/web-backend.log"

  local warmup_status
  warmup_status="$(curl -fsS "$WEB_BACKEND_URL/health")"
  echo "Web Backend ready: $warmup_status"
}

start_frontend() {
  if curl -fsS "$FRONTEND_URL" >/dev/null 2>&1; then
    echo "Frontend is already reachable at $FRONTEND_URL"
    return
  fi

  echo "Starting frontend..."
  bash -c "cd '$ROOT_DIR/frontend' && VITE_API_BASE_URL='$WEB_BACKEND_URL' npm run dev" >"$LOG_DIR/frontend.log" 2>&1 &
  echo "$!" >"$PID_DIR/frontend.pid"
  STARTED_PIDS+=("$!")

  wait_for_http "$FRONTEND_URL" "frontend" 60 "$LOG_DIR/frontend.log"
  echo "Frontend ready: $FRONTEND_URL"
}

start_ai_backend
start_web_backend
start_frontend

echo "All services are ready."
echo "Logs: $LOG_DIR"
echo "PIDs: $PID_DIR"

if [ "$KEEP_SERVICES_ATTACHED" = "true" ] && [ "${#STARTED_PIDS[@]}" -gt 0 ]; then
  echo "Services are attached to this script. Press Ctrl-C to stop them."
  trap 'kill "${STARTED_PIDS[@]}" >/dev/null 2>&1 || true' INT TERM EXIT
  wait "${STARTED_PIDS[@]}"
fi
