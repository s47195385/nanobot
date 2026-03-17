#!/usr/bin/env bash
# heartbeat-only.sh
#
# Start nanobot in headless / daemon mode — heartbeat ticks without any
# interactive channel or live user prompting.
#
# The gateway still runs so the agent can process HEARTBEAT.md tasks on the
# configured interval and (optionally) deliver results to a configured channel.
#
# Usage:
#   bash scripts/heartbeat-only.sh [nanobot gateway options]
#   bash scripts/heartbeat-only.sh --config ~/.nanobot/config.json
#
# Run as a background daemon (logs to ~/.nanobot/heartbeat.log):
#   nohup bash scripts/heartbeat-only.sh > ~/.nanobot/heartbeat.log 2>&1 &

set -euo pipefail

CONFIG_DIR="${HOME}/.nanobot"
CONFIG_FILE="${CONFIG_DIR}/config.json"

# Ensure a config exists before starting.
if [[ ! -f "${CONFIG_FILE}" ]]; then
    echo "ERROR: No config found at ${CONFIG_FILE}." >&2
    echo "Run scripts/setup-ollama-gemini.sh first." >&2
    exit 1
fi

echo "[heartbeat-only] Starting nanobot gateway (headless)..."
echo "[heartbeat-only] Config : ${CONFIG_FILE}"
echo "[heartbeat-only] Press Ctrl+C to stop."
echo

exec nanobot gateway --config "${CONFIG_FILE}" "$@"
