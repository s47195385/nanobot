from pathlib import Path

from nanobot.agent.context import ContextBuilder


def test_apply_role_preset_prepends_role_agents_file() -> None:
    builder = ContextBuilder(Path("/tmp/workspace"))

    builder.apply_role_preset("programmer")

    assert builder.BOOTSTRAP_FILES[0] == "AGENTS.programmer.md"
    assert "AGENTS.md" in builder.BOOTSTRAP_FILES


def test_apply_role_preset_ignores_unknown_role() -> None:
    builder = ContextBuilder(Path("/tmp/workspace"))
    original = list(builder.BOOTSTRAP_FILES)

    builder.apply_role_preset("unknown-role")

    assert builder.BOOTSTRAP_FILES == original
