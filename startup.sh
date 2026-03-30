#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH="${NANOBOT_CONFIG:-$HOME/.nanobot/config.json}"
WORKSPACE_PATH="${NANOBOT_WORKSPACE:-$HOME/.nanobot/workspace}"

printf "Using config: %s\n" "$CONFIG_PATH"
printf "Project workspace: %s\n" "$WORKSPACE_PATH"
printf "Starting nanobot gateway (verbose) ...\n"

# Ensure only one gateway instance is running.
pkill -f "python3 -m nanobot gateway" >/dev/null 2>&1 || true

exec python3 -m nanobot gateway -c "$CONFIG_PATH" -v
