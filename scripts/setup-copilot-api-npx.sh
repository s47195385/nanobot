#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH="${1:-$HOME/.nanobot/config.json}"
MODEL="${NANOBOT_COPILOT_MODEL:-gpt-4.1}"
PORT="${COPILOT_API_PORT:-4141}"
COPILOT_API_DATA_HOME="${COPILOT_API_DATA_HOME:-$HOME/.nanobot/copilot-api-data}"

export XDG_DATA_HOME="$COPILOT_API_DATA_HOME"

echo "Using config: $CONFIG_PATH"
echo "Using copilot-api data dir: $XDG_DATA_HOME"

mkdir -p "$(dirname "$CONFIG_PATH")"
mkdir -p "$XDG_DATA_HOME"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Config not found. Running nanobot onboard..."
  nanobot onboard --config "$CONFIG_PATH"
fi

COPILOT_STATE_DIR="$XDG_DATA_HOME/copilot-api"
AUTH_MARKER="$COPILOT_STATE_DIR/.nanobot-auth-ok"
mkdir -p "$COPILOT_STATE_DIR"

if [[ ! -f "$AUTH_MARKER" ]]; then
  echo "No copilot-api auth state found. Starting one-time login..."
  npx copilot-api@latest auth
  touch "$AUTH_MARKER"
else
  echo "Existing copilot-api auth marker found. Skipping login."
fi

python - "$CONFIG_PATH" "$MODEL" "$PORT" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1]).expanduser()
model = sys.argv[2]
port = sys.argv[3]

try:
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        data = {}
except json.JSONDecodeError as exc:
    raise SystemExit(f"Invalid JSON in {config_path}: {exc}") from exc

providers = data.setdefault("providers", {})
providers.setdefault("copilotApi", {})
providers["copilotApi"]["apiBase"] = f"http://127.0.0.1:{port}/v1"
providers["copilotApi"]["apiKey"] = providers["copilotApi"].get("apiKey") or "no-key"

agents = data.setdefault("agents", {})
defaults = agents.setdefault("defaults", {})
defaults["provider"] = "copilot_api"
defaults["model"] = model

try:
    config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
except OSError as exc:
    raise SystemExit(f"Failed to write config {config_path}: {exc}") from exc
PY

echo "Done."
echo "Config now targets copilot-api (npx) with model '$MODEL'."
echo "Start everything with: scripts/startup-copilot-api-nanobot.sh gateway --config \"$CONFIG_PATH\""
