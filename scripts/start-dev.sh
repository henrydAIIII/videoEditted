#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_SCRIPT="$ROOT_DIR/scripts/start-backend.sh"
FRONTEND_SCRIPT="$ROOT_DIR/scripts/start-frontend.sh"
LOG_DIR="$ROOT_DIR/.logs"
BACKEND_LOG="$LOG_DIR/backend.log"

mkdir -p "$LOG_DIR"

if [[ ! -x "$BACKEND_SCRIPT" || ! -x "$FRONTEND_SCRIPT" ]]; then
  echo "Start scripts are missing or not executable."
  exit 1
fi

"$BACKEND_SCRIPT" >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

cleanup() {
  if kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

echo "Backend started: http://127.0.0.1:8000"
echo "Backend log: $BACKEND_LOG"
echo "Frontend starting: http://127.0.0.1:5173"

"$FRONTEND_SCRIPT"
