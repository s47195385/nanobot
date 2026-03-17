#!/usr/bin/env bash
# setup-ollama-gemini.sh
#
# Idempotent setup script for nanobot on macOS with:
#   - Ollama (local) for simple / triage tasks     → model: rnj-1
#   - Gemini API      for complex / planning tasks  → model: gemini/gemini-2.5-pro-preview-06-05
#   - Heartbeat every 20 minutes
#
# Safe to re-run: only fills in missing values, never overwrites existing ones.
#
# Usage:
#   bash scripts/setup-ollama-gemini.sh [--gemini-key <KEY>]
#   GEMINI_API_KEY=<KEY> bash scripts/setup-ollama-gemini.sh
#
# The Gemini API key is read from (in priority order):
#   1. --gemini-key CLI argument
#   2. GEMINI_API_KEY environment variable
#   3. Interactive prompt

set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RESET='\033[0m'

info()    { echo -e "${GREEN}[setup]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[warn]${RESET}  $*"; }
heading() { echo -e "\n${BOLD}$*${RESET}"; }

require_cmd() {
    if ! command -v "$1" &>/dev/null; then
        echo "ERROR: '$1' not found. $2" >&2
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

require_cmd python3  "Install Python 3.11+ first."
require_cmd jq       "Install jq with: brew install jq"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------

GEMINI_KEY="${GEMINI_API_KEY:-}"
OLLAMA_MODEL="rnj-1"
PLANNING_MODEL="gemini/gemini-2.5-pro-preview-06-05"
HEARTBEAT_INTERVAL=1200  # 20 minutes

while [[ $# -gt 0 ]]; do
    case "$1" in
        --gemini-key)
            GEMINI_KEY="$2"
            shift 2
            ;;
        --ollama-model)
            OLLAMA_MODEL="$2"
            shift 2
            ;;
        --planning-model)
            PLANNING_MODEL="$2"
            shift 2
            ;;
        --interval)
            HEARTBEAT_INTERVAL="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Prompt for Gemini API key if not provided
# ---------------------------------------------------------------------------

if [[ -z "$GEMINI_KEY" ]]; then
    heading "Gemini API Key"
    echo "Enter your Gemini API key (input is hidden):"
    read -rs GEMINI_KEY
    echo
fi

if [[ -z "$GEMINI_KEY" ]]; then
    echo "ERROR: Gemini API key is required." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Config file location
# ---------------------------------------------------------------------------

CONFIG_DIR="${HOME}/.nanobot"
CONFIG_FILE="${CONFIG_DIR}/config.json"

mkdir -p "${CONFIG_DIR}"

# ---------------------------------------------------------------------------
# Load or create config
# ---------------------------------------------------------------------------

heading "Loading config: ${CONFIG_FILE}"

if [[ -f "${CONFIG_FILE}" ]]; then
    info "Existing config found — merging (no values will be overwritten)."
    EXISTING=$(cat "${CONFIG_FILE}")
else
    info "No existing config — creating a fresh one."
    EXISTING='{}'
fi

# ---------------------------------------------------------------------------
# Merge helper: only set leaf values that are currently empty / absent
# ---------------------------------------------------------------------------

# We use Python for safe JSON merging so we don't depend on jq for deep paths.
UPDATED=$(python3 - <<'PYEOF'
import json, sys, os

config_file = os.path.expanduser("~/.nanobot/config.json")
gemini_key  = os.environ["_NB_GEMINI_KEY"]
ollama_model = os.environ["_NB_OLLAMA_MODEL"]
planning_model = os.environ["_NB_PLANNING_MODEL"]
interval    = int(os.environ["_NB_INTERVAL"])

try:
    with open(config_file) as f:
        cfg = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    cfg = {}

def _set_if_absent(d, *keys, value):
    """Walk keys into dict d, creating sub-dicts as needed.
    Sets the final key only when it is absent or empty-string."""
    cur = d
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    leaf = keys[-1]
    if not cur.get(leaf):
        cur[leaf] = value
        return True
    return False

changed = False
changed |= _set_if_absent(cfg, "providers", "gemini",  "apiKey",  value=gemini_key)
changed |= _set_if_absent(cfg, "providers", "ollama",  "apiBase", value="http://localhost:11434")
changed |= _set_if_absent(cfg, "gateway",   "heartbeat", "intervalS", value=interval)
changed |= _set_if_absent(cfg, "gateway",   "heartbeat", "triageModel",   value=f"ollama_chat/{ollama_model}")
changed |= _set_if_absent(cfg, "gateway",   "heartbeat", "planningModel", value=planning_model)
# Default agent model → planning model when absent
changed |= _set_if_absent(cfg, "agents", "defaults", "model", value=planning_model)

print(json.dumps(cfg, indent=2, ensure_ascii=False))
PYEOF
)

# Export vars used by the Python snippet
export _NB_GEMINI_KEY="$GEMINI_KEY"
export _NB_OLLAMA_MODEL="$OLLAMA_MODEL"
export _NB_PLANNING_MODEL="$PLANNING_MODEL"
export _NB_INTERVAL="$HEARTBEAT_INTERVAL"

UPDATED=$(python3 - <<'PYEOF'
import json, sys, os

config_file = os.path.expanduser("~/.nanobot/config.json")
gemini_key  = os.environ["_NB_GEMINI_KEY"]
ollama_model = os.environ["_NB_OLLAMA_MODEL"]
planning_model = os.environ["_NB_PLANNING_MODEL"]
interval    = int(os.environ["_NB_INTERVAL"])

try:
    with open(config_file) as f:
        cfg = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    cfg = {}

def _set_if_absent(d, *keys, value):
    cur = d
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    leaf = keys[-1]
    if not cur.get(leaf):
        cur[leaf] = value
        return True
    return False

_set_if_absent(cfg, "providers", "gemini",    "apiKey",        value=gemini_key)
_set_if_absent(cfg, "providers", "ollama",    "apiBase",       value="http://localhost:11434")
_set_if_absent(cfg, "gateway",   "heartbeat", "intervalS",     value=interval)
_set_if_absent(cfg, "gateway",   "heartbeat", "triageModel",   value=f"ollama_chat/{ollama_model}")
_set_if_absent(cfg, "gateway",   "heartbeat", "planningModel", value=planning_model)
_set_if_absent(cfg, "agents",    "defaults",  "model",         value=planning_model)

print(json.dumps(cfg, indent=2, ensure_ascii=False))
PYEOF
)

# ---------------------------------------------------------------------------
# Write updated config
# ---------------------------------------------------------------------------

echo "$UPDATED" > "${CONFIG_FILE}"
info "Config written to ${CONFIG_FILE}"

# ---------------------------------------------------------------------------
# Verify Ollama is reachable (non-fatal)
# ---------------------------------------------------------------------------

heading "Checking Ollama"
if curl -sf "http://localhost:11434/api/tags" > /dev/null 2>&1; then
    info "Ollama is running at http://localhost:11434"
    if curl -sf "http://localhost:11434/api/tags" | python3 -c "
import json, sys
tags = json.load(sys.stdin)
models = [m['name'] for m in tags.get('models', [])]
print('  Available models:', ', '.join(models) if models else '(none)')
" 2>/dev/null; then
        :
    fi
else
    warn "Ollama not reachable at http://localhost:11434"
    warn "Start it with: ollama serve"
    warn "Then pull the model: ollama pull ${OLLAMA_MODEL}"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

heading "Setup complete"
cat <<MSG
  Gemini provider  : configured (key stored in ${CONFIG_FILE})
  Ollama provider  : http://localhost:11434
  Heartbeat model  : ${PLANNING_MODEL}  (planning / complex tasks)
  Triage model     : ollama_chat/${OLLAMA_MODEL}  (simple tasks)
  Heartbeat every  : $((HEARTBEAT_INTERVAL / 60)) minutes

Next steps:
  1. Make sure Ollama is running: ollama serve
  2. Pull the local model:        ollama pull ${OLLAMA_MODEL}
  3. Start nanobot gateway:       nanobot gateway
     Or headless:                 bash scripts/heartbeat-only.sh

MSG
