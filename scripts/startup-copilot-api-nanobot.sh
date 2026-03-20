#!/usr/bin/env bash
set -euo pipefail

PORT="${COPILOT_API_PORT:-4141}"
STARTUP_TIMEOUT_SECONDS="${COPILOT_API_STARTUP_TIMEOUT:-60}"
HEALTH_PATH="${COPILOT_API_HEALTH_PATH:-/v1/models}"
COPILOT_API_DATA_HOME="${COPILOT_API_DATA_HOME:-$HOME/.nanobot/copilot-api-data}"
LOG_PATH="${COPILOT_API_LOG_PATH:-$COPILOT_API_DATA_HOME/copilot-api.log}"
export XDG_DATA_HOME="$COPILOT_API_DATA_HOME"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required for startup health checks. Please install curl."
  exit 1
fi

mkdir -p "$COPILOT_API_DATA_HOME"

if [[ $# -eq 0 ]]; then
  set -- gateway
fi

echo "Starting copilot-api on port $PORT (npx, no Docker)..."
npx copilot-api@latest start --port "$PORT" >>"$LOG_PATH" 2>&1 &
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
for _ in $(seq 1 "$STARTUP_TIMEOUT_SECONDS"); do
  if curl -fsS "http://127.0.0.1:${PORT}${HEALTH_PATH}" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

if [[ "$READY" -ne 1 ]]; then
  echo "copilot-api did not become ready in time. Check logs at: $LOG_PATH"
  exit 1
fi

echo "copilot-api is ready. Starting nanobot: $*"
nanobot "$@"
