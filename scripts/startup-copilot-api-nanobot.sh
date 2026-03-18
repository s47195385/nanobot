#!/usr/bin/env bash
set -euo pipefail

PORT="${COPILOT_API_PORT:-4141}"
COPILOT_API_DATA_HOME="${COPILOT_API_DATA_HOME:-$HOME/.nanobot/copilot-api-data}"
export XDG_DATA_HOME="$COPILOT_API_DATA_HOME"

if [[ $# -eq 0 ]]; then
  set -- gateway
fi

echo "Starting copilot-api on port $PORT (npx, no Docker)..."
npx copilot-api@latest start --port "$PORT" &
COPILOT_PID=$!

cleanup() {
  if kill -0 "$COPILOT_PID" 2>/dev/null; then
    kill "$COPILOT_PID"
    wait "$COPILOT_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Waiting for copilot-api to become ready..."
READY=0
for _ in $(seq 1 60); do
  if command -v curl >/dev/null 2>&1; then
    if curl -fsS "http://127.0.0.1:${PORT}/v1/models" >/dev/null 2>&1; then
      READY=1
      break
    fi
  else
    READY=1
    break
  fi
  sleep 1
done

if [[ "$READY" -ne 1 ]]; then
  echo "copilot-api did not become ready in time."
  exit 1
fi

echo "copilot-api is ready. Starting nanobot: $*"
nanobot "$@"
