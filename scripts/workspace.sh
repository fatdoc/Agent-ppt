#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_PID_FILE="$ROOT_DIR/backend/server.pid"
FRONTEND_PID_FILE="$ROOT_DIR/frontend.pid"
BACKEND_LOG="$ROOT_DIR/backend/server_running.log"
FRONTEND_LOG="$ROOT_DIR/frontend_running.log"

ACTION="${1:-start}"

log() {
  printf '[workspace] %s\n' "$*"
}

fail() {
  printf '[workspace] ERROR: %s\n' "$*" >&2
  exit 1
}

compute_port() {
  local base_port="$1"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$ROOT_DIR" "$base_port" <<'PY'
import hashlib
import os
import sys

root = sys.argv[1]
base = int(sys.argv[2])
name = os.path.basename(os.path.abspath(root))
offset = int(hashlib.md5(name.encode()).hexdigest()[:8], 16) % 500
print(base + offset)
PY
  elif command -v uv >/dev/null 2>&1; then
    uv run python - "$ROOT_DIR" "$base_port" <<'PY'
import hashlib
import os
import sys

root = sys.argv[1]
base = int(sys.argv[2])
name = os.path.basename(os.path.abspath(root))
offset = int(hashlib.md5(name.encode()).hexdigest()[:8], 16) % 500
print(base + offset)
PY
  else
    printf '%s\n' "$base_port"
  fi
}

BACKEND_PORT="${BACKEND_PORT:-$(compute_port 5000)}"
FRONTEND_PORT="${FRONTEND_PORT:-$(compute_port 3000)}"

is_running() {
  local pid_file="$1"
  if [ ! -f "$pid_file" ]; then
    return 1
  fi

  local pid
  pid="$(tr -d '[:space:]' < "$pid_file")"
  if [ -z "$pid" ]; then
    return 1
  fi

  kill -0 "$pid" >/dev/null 2>&1
}

pid_value() {
  local pid_file="$1"
  if [ -f "$pid_file" ]; then
    tr -d '[:space:]' < "$pid_file"
  fi
}

ensure_env() {
  if [ ! -f "$ROOT_DIR/.env" ] && [ -f "$ROOT_DIR/.env.example" ]; then
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    log "created .env from .env.example; update API keys before using AI features"
  fi
}

ensure_backend_deps() {
  command -v uv >/dev/null 2>&1 || fail "uv is required. Install it first: https://docs.astral.sh/uv/"
  if [ ! -d "$ROOT_DIR/.venv" ]; then
    log "installing backend dependencies with uv sync"
    (cd "$ROOT_DIR" && uv sync)
  fi
}

ensure_frontend_deps() {
  command -v npm >/dev/null 2>&1 || fail "npm is required. Install Node.js >= 18 first."
  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    log "installing frontend dependencies with npm install"
    (cd "$FRONTEND_DIR" && npm install)
  fi
}

start_backend() {
  if is_running "$BACKEND_PID_FILE"; then
    log "backend already running: pid $(pid_value "$BACKEND_PID_FILE"), http://localhost:$BACKEND_PORT"
    return
  fi

  ensure_env
  ensure_backend_deps
  : > "$BACKEND_LOG"

  log "running backend migrations"
  (cd "$BACKEND_DIR" && BACKEND_PORT="$BACKEND_PORT" uv run alembic upgrade head) >> "$BACKEND_LOG" 2>&1

  log "starting backend on http://localhost:$BACKEND_PORT"
  (cd "$BACKEND_DIR" && BACKEND_PORT="$BACKEND_PORT" uv run python app.py) >> "$BACKEND_LOG" 2>&1 &
  printf '%s\n' "$!" > "$BACKEND_PID_FILE"
}

start_frontend() {
  if is_running "$FRONTEND_PID_FILE"; then
    log "frontend already running: pid $(pid_value "$FRONTEND_PID_FILE"), http://localhost:$FRONTEND_PORT"
    return
  fi

  ensure_frontend_deps
  : > "$FRONTEND_LOG"

  log "starting frontend on http://localhost:$FRONTEND_PORT"
  (cd "$FRONTEND_DIR" && BACKEND_PORT="$BACKEND_PORT" FRONTEND_PORT="$FRONTEND_PORT" npm run dev) >> "$FRONTEND_LOG" 2>&1 &
  printf '%s\n' "$!" > "$FRONTEND_PID_FILE"
}

stop_process() {
  local name="$1"
  local pid_file="$2"

  if ! is_running "$pid_file"; then
    rm -f "$pid_file"
    log "$name is not running"
    return
  fi

  local pid
  pid="$(pid_value "$pid_file")"
  log "stopping $name: pid $pid"
  kill "$pid" >/dev/null 2>&1 || true

  local i
  for i in 1 2 3 4 5; do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  if kill -0 "$pid" >/dev/null 2>&1; then
    log "$name did not stop gracefully; sending SIGKILL"
    kill -9 "$pid" >/dev/null 2>&1 || true
  fi

  rm -f "$pid_file"
}

start_all() {
  start_backend
  start_frontend
  log "workspace started"
  log "backend:  http://localhost:$BACKEND_PORT"
  log "frontend: http://localhost:$FRONTEND_PORT"
  log "logs: npm run workspace:logs"
}

stop_all() {
  stop_process "frontend" "$FRONTEND_PID_FILE"
  stop_process "backend" "$BACKEND_PID_FILE"
}

status_one() {
  local name="$1"
  local pid_file="$2"
  local url="$3"

  if is_running "$pid_file"; then
    log "$name running: pid $(pid_value "$pid_file"), $url"
  else
    log "$name stopped"
  fi
}

status_all() {
  status_one "backend" "$BACKEND_PID_FILE" "http://localhost:$BACKEND_PORT"
  status_one "frontend" "$FRONTEND_PID_FILE" "http://localhost:$FRONTEND_PORT"
}

show_logs() {
  log "backend log:  $BACKEND_LOG"
  log "frontend log: $FRONTEND_LOG"
  tail -f "$BACKEND_LOG" "$FRONTEND_LOG"
}

case "$ACTION" in
  start)
    start_all
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    start_all
    ;;
  status)
    status_all
    ;;
  logs)
    show_logs
    ;;
  *)
    cat <<EOF
Usage: bash scripts/workspace.sh <command>

Commands:
  start     Start backend and frontend
  stop      Stop backend and frontend
  restart   Restart backend and frontend
  status    Show process status
  logs      Follow backend and frontend logs

Environment overrides:
  BACKEND_PORT=5000 FRONTEND_PORT=3000 bash scripts/workspace.sh start
EOF
    exit 2
    ;;
esac
