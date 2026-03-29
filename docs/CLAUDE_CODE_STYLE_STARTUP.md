# Claude-Code-Style Startup (Wrapper, No Core Fork)

This guide shows how to run nanobot with a wrapper workflow inspired by Claude Code features, while keeping core nanobot broadly compatible.

## What this setup provides

- **Auto-mode guardrails**: strict project isolation via `tools.restrictToWorkspace=true` and Discord channel allow-listing.
- **Discord remote-control shape**: one gateway process per project/channel mapping.
- **Planner/worker split**: heartbeat planning can use `agents.defaults.plannerModel` while normal execution uses `agents.defaults.model`.
- **Role hats**: `agents.defaults.role` with built-in presets:
  - `programmer`
  - `researcher`
  - `business_analyst`
  - `consultant`
- **Token optimization defaults**: wrapper can disable progress/tool-hint streaming metadata.
- **Plugin marketplace compatibility**: use built-in channel plugins (`nanobot plugins list`) and existing skill marketplace flow (`clawhub` skill).

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
      "model": "anthropic/claude-opus-4-5",
      "plannerModel": "anthropic/claude-opus-4-5",
      "role": "programmer"
    }
  },
  "tools": {
    "restrictToWorkspace": true
  },
  "channels": {
    "discord": {
      "allowChannelIds": ["123456789012345678"]
    }
  },
  "tools": {
    "mcpServers": {
      "geminiCli": {
        "type": "stdio",
        "command": "gemini",             // gemini CLI MCP server
        "args": ["mcp", "serve"],
        "toolTimeout": 60
      }
    }
  }
}
```

## Notes on “opus plan” and queued execution

- nanobot already has heartbeat-based periodic execution via `HEARTBEAT.md`.
- With `plannerModel`, you can choose a stronger planning model for heartbeat decision/planning while keeping a different worker model for normal agent execution.
- For granular queued work, keep tasks in `HEARTBEAT.md` and let the planner/worker flow process them over heartbeat intervals.
- The wrapper flag `--heartbeat-interval` sets the cadence (e.g., `3600` for hourly PM-led nudges).

## Suggested multi-model flow (Gemini CLI MCP + Claude/GitHub Copilot)

1) **Elicit requirements with Gemini CLI (MCP)**  
   - Configure the MCP server above. Use the `business_analyst` role to run structured discovery question sets (see `BA.WORKFLOWS.md`).
2) **Plan with a stronger planner model**  
   - Set `plannerModel` to `anthropic/claude-opus-4-5` (or GitHub Copilot endpoint). Output: modular work plan + backlog + acceptance tests.
3) **Execute with Gemini CLI**  
   - Keep `agents.defaults.model` pointing to a Gemini-compatible endpoint for the worker loop to implement tasks.
4) **Heartbeat queue**  
   - Maintain tasks in `HEARTBEAT.md`; set `--heartbeat-interval 3600` for hourly check-ins. The PM can edit the file to reprioritize between beats.
5) **Standup/status**  
   - Use the role byproducts templates (e.g., `PROGRAMMER.BYPRODUCTS.md`, `BA.BYPRODUCTS.md`) to summarize progress, blockers, and next steps.
