from pathlib import Path

from nanobot.agent.context import ContextBuilder


def test_apply_role_preset_prepends_role_agents_file() -> None:
    builder = ContextBuilder(Path("/tmp/workspace"))

    builder.apply_role_preset("programmer")

    assert builder.bootstrap_files[0] == "AGENTS.programmer.md"
    assert "AGENTS.md" in builder.bootstrap_files
    # Extra workflow templates for role should be inserted after the role preset.
    assert builder.bootstrap_files[1] == "PROGRAMMER.WORKFLOWS.md"
    assert "PROGRAMMER.BYPRODUCTS.md" in builder.bootstrap_files


def test_apply_role_preset_ignores_unknown_role() -> None:
    builder = ContextBuilder(Path("/tmp/workspace"))
    original = list(builder.bootstrap_files)

    builder.apply_role_preset("unknown-role")

    assert builder.bootstrap_files == original
