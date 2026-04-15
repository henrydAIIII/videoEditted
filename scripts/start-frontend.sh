#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Missing frontend dependencies: $FRONTEND_DIR/node_modules"
  echo "Run: cd \"$FRONTEND_DIR\" && npm install"
  exit 1
fi

cd "$FRONTEND_DIR"
exec npm run dev -- --host 0.0.0.0 --port 5173
