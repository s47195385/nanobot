import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "startup_multi_project_discord.py"


def test_startup_wrapper_requires_allow_list_unless_explicit_allow_all(tmp_path: Path) -> None:
    script = str(SCRIPT_PATH)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    argv = [
        script,
        "--discord-token",
        "token",
        "--project",
        f"proj:{project_dir}:123",
        "--dry-run",
    ]

    with patch.object(sys, "argv", argv):
        try:
            runpy.run_path(script, run_name="__main__")
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError("Expected parser error when no --allow-user is provided")


def test_startup_wrapper_writes_isolated_config(tmp_path: Path) -> None:
    script = str(SCRIPT_PATH)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    base_cfg = tmp_path / "base.json"
    base_cfg.write_text("{}", encoding="utf-8")
    instance_dir = tmp_path / "instances"

    argv = [
        script,
        "--discord-token",
        "token",
        "--allow-user",
        "u1",
        "--project",
        f"proj:{project_dir}:123",
        "--base-config",
        str(base_cfg),
        "--instance-dir",
        str(instance_dir),
        "--dry-run",
    ]

    with patch.object(sys, "argv", argv):
        try:
            runpy.run_path(script, run_name="__main__")
        except SystemExit as exc:
            assert exc.code == 0

    generated = instance_dir / "proj.config.json"
    assert generated.exists()

    data = json.loads(generated.read_text(encoding="utf-8"))
    assert data["tools"]["restrictToWorkspace"] is True
    assert data["channels"]["discord"]["allowChannelIds"] == ["123"]
    assert data["agents"]["defaults"]["workspace"] == str(project_dir.resolve())
