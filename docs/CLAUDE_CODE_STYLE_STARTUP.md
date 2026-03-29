# Claude-Code-Style Startup (Wrapper, No Core Fork)

This guide shows how to run nanobot with a wrapper workflow inspired by Claude Code features, while keeping core nanobot broadly compatible.

## What this setup provides

- **Auto-mode guardrails**: strict project isolation via `tools.restrictToWorkspace=true` and Discord channel allow-listing.
- **Discord remote-control shape**: one gateway process per project/channel mapping.
- **Role hats**: `agents.defaults.role` with built-in presets:
  - `programmer`
  - `researcher`
  - `business_analyst`
  - `consultant`
- **Token optimization defaults**: wrapper can disable progress/tool-hint streaming metadata.
- **Plugin marketplace compatibility**: use built-in channel plugins (`nanobot plugins list`) and existing skill marketplace flow (`clawhub` skill).
- **Requirements + task intake files**: `REQUIREMENTS.md` and `TASKS.md` are synced into each workspace for you to edit; the agent will read them.

## Startup script

Use:

```bash
python scripts/startup_multi_project_discord.py \
  --discord-token "$DISCORD_BOT_TOKEN" \
  --allow-user "YOUR_DISCORD_USER_ID" \
  --project projA:/abs/path/to/project-a:123456789012345678 \
  --project projB:/abs/path/to/project-b:223456789012345678 \
  --heartbeat-interval 3600 \
  --role business_analyst
```

Each `--project` starts a dedicated gateway instance with:

- its own generated config under `~/.nanobot/instances/`
- workspace set to that project directory
- Discord restricted to exactly that channel (`allowChannelIds`)
- workspace-restricted tools enabled

### Dry run

```bash
python scripts/startup_multi_project_discord.py \
  --discord-token "$DISCORD_BOT_TOKEN" \
  --allow-user "YOUR_DISCORD_USER_ID" \
  --project projA:/abs/path/to/project-a:123456789012345678 \
  --heartbeat-interval 1800 \
  --dry-run
```

## Config fields used

```json
{
  "agents": {
    "defaults": {
      "model": "openrouter/your-model",
      "role": "programmer"
    }
  },
  "tools": {
    "restrictToWorkspace": true
  }
}
```

## Notes on “opus plan” and queued execution

- nanobot already has heartbeat-based periodic execution via `HEARTBEAT.md`.
- Keep tasks modular/granular in `TASKS.md` (and optionally mirror high-priority items into `HEARTBEAT.md` for timed execution).
- Capture upstream context in `REQUIREMENTS.md` — the agent reads this alongside role presets.
- The wrapper flag `--heartbeat-interval` sets the cadence (e.g., `3600` for hourly PM-led nudges).
