#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
PORT="${PORT:-3000}"
HOST="${HOST:-127.0.0.1}"
API_BASE_URL="${QC_API_BASE_URL:-http://127.0.0.1:8000}"

if [ ! -d "$FRONTEND_DIR" ]; then
  echo "frontend 目录不存在，请先完成前端初始化。" >&2
  exit 1
fi

cd "$FRONTEND_DIR"
export QC_API_BASE_URL="$API_BASE_URL"
exec npm run dev -- --hostname "$HOST" --port "$PORT"
