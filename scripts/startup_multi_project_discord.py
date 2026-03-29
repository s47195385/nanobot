#!/usr/bin/env python3
"""Launch isolated nanobot gateways per Discord channel/project mapping."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _parse_project(value: str) -> tuple[str, Path, str]:
    parts = value.split(":", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            "Project must be NAME:/abs/project/path:DISCORD_CHANNEL_ID"
        )
    name, raw_dir, channel_id = parts
    project_dir = Path(raw_dir).expanduser().resolve()
    if not project_dir.is_absolute():
        raise argparse.ArgumentTypeError("Project directory must be absolute")
    return name.strip(), project_dir, channel_id.strip()


def _write_instance_config(
    *,
    base: dict,
    name: str,
    project_dir: Path,
    channel_id: str,
    args: argparse.Namespace,
    out_dir: Path,
) -> Path:
    cfg = json.loads(json.dumps(base))
    cfg.setdefault("agents", {}).setdefault("defaults", {})
    cfg.setdefault("tools", {})
    cfg.setdefault("channels", {}).setdefault("discord", {})
    cfg.setdefault("gateway", {}).setdefault("heartbeat", {})

    defaults = cfg["agents"]["defaults"]
    defaults["workspace"] = str(project_dir)
    defaults["model"] = args.model
    defaults["provider"] = args.provider
    defaults["role"] = args.role
    if args.planner_model:
        defaults["plannerModel"] = args.planner_model
    if args.max_tokens:
        defaults["maxTokens"] = int(args.max_tokens)
    if args.context_window_tokens:
        defaults["contextWindowTokens"] = int(args.context_window_tokens)

    cfg["tools"]["restrictToWorkspace"] = True

    discord = cfg["channels"]["discord"]
    discord["enabled"] = True
    discord["token"] = args.discord_token
    # Parser enforces: when allow_all_users is False, at least one allow_user is provided.
    discord["allowFrom"] = ["*"] if args.allow_all_users else [u.strip() for u in args.allow_user]
    discord["allowChannelIds"] = [channel_id]

    if args.token_optimized:
        cfg["channels"]["sendProgress"] = False
        cfg["channels"]["sendToolHints"] = False

    cfg["gateway"]["heartbeat"]["enabled"] = not args.disable_heartbeat
    if args.heartbeat_interval:
        cfg["gateway"]["heartbeat"]["intervalS"] = int(args.heartbeat_interval)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.config.json"
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run one nanobot gateway per Discord channel/project (isolated workspaces)."
    )
    p.add_argument(
        "--project",
        action="append",
        type=_parse_project,
        required=True,
        help="NAME:/abs/project/path:DISCORD_CHANNEL_ID (repeat for multiple projects)",
    )
    p.add_argument("--discord-token", required=True, help="Discord bot token")
    p.add_argument("--allow-user", action="append", default=[], help="Discord user id allowed to interact")
    p.add_argument("--allow-all-users", action="store_true", help="Allow all Discord users (not recommended)")
    p.add_argument("--provider", default="openrouter")
    p.add_argument("--model", default="anthropic/claude-opus-4-5")
    p.add_argument("--planner-model", default="anthropic/claude-opus-4-5")
    p.add_argument(
        "--role",
        default="programmer",
        choices=["programmer", "researcher", "business_analyst", "consultant"],
    )
    p.add_argument("--max-tokens", type=int, default=4096)
    p.add_argument("--context-window-tokens", type=int, default=32768)
    p.add_argument(
        "--heartbeat-interval",
        type=int,
        default=3600,
        help="Heartbeat interval seconds (queue cadence). Default: 3600 (1h).",
    )
    p.add_argument(
        "--token-optimized",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reduce chat streaming metadata to save tokens (default: enabled)",
    )
    p.add_argument("--disable-heartbeat", action="store_true")
    p.add_argument("--base-config", default=str(Path.home() / ".nanobot" / "config.json"))
    p.add_argument("--instance-dir", default=str(Path.home() / ".nanobot" / "instances"))
    p.add_argument("--start-port", type=int, default=18790)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not args.allow_all_users and not args.allow_user:
        p.error("Set --allow-user at least once, or use --allow-all-users")

    base_cfg_path = Path(args.base_config).expanduser()
    if base_cfg_path.exists():
        base = json.loads(base_cfg_path.read_text(encoding="utf-8"))
    else:
        base = {}

    instance_dir = Path(args.instance_dir).expanduser().resolve()
    procs: list[subprocess.Popen] = []
    for idx, (name, project_dir, channel_id) in enumerate(args.project):
        cfg_path = _write_instance_config(
            base=base,
            name=name,
            project_dir=project_dir,
            channel_id=channel_id,
            args=args,
            out_dir=instance_dir,
        )
        port = args.start_port + idx
        cmd = [
            sys.executable,
            "-m",
            "nanobot",
            "gateway",
            "--config",
            str(cfg_path),
            "--port",
            str(port),
        ]
        print(f"[{name}] workspace={project_dir} channel={channel_id} port={port}")
        print(" ", " ".join(cmd))
        if not args.dry_run:
            procs.append(subprocess.Popen(cmd, env=os.environ.copy()))

    if args.dry_run or not procs:
        return 0

    print(f"Started {len(procs)} gateway process(es). Press Ctrl+C to stop.")
    try:
        for proc in procs:
            proc.wait()
    except KeyboardInterrupt:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
