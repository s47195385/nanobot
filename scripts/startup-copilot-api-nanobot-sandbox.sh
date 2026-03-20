#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script is macOS-only (requires sandbox-exec)."
  exit 1
fi

if ! command -v sandbox-exec >/dev/null 2>&1; then
  echo "sandbox-exec not found on this macOS installation."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_PATH="${NANOBOT_SANDBOX_PROFILE:-$SCRIPT_DIR/macos-strictly-locked.sb}"

NANOBOT_HOME="${NANOBOT_HOME:-$HOME/.nanobot}"
NANOBOT_WORKSPACE="${NANOBOT_WORKSPACE:-$NANOBOT_HOME/workspace}"

mkdir -p "$NANOBOT_HOME" "$NANOBOT_WORKSPACE"

echo "Running in macOS sandbox:"
echo "  profile: $PROFILE_PATH"
echo "  NANOBOT_HOME: $NANOBOT_HOME"
echo "  NANOBOT_WORKSPACE: $NANOBOT_WORKSPACE"

exec sandbox-exec \
  -f "$PROFILE_PATH" \
  -D NANOBOT_HOME="$NANOBOT_HOME" \
  -D NANOBOT_WORKSPACE="$NANOBOT_WORKSPACE" \
  "$SCRIPT_DIR/startup-copilot-api-nanobot.sh" "$@"
