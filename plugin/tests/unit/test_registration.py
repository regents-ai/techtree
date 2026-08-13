"""Registration registers what it declares, and nothing more.

Specification section 7.15, registration tests.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

import pytest
import techtree_hermes
from support import RecordingContext
from techtree_hermes.constants import TOOLSET_NAME
from techtree_hermes.errors import PluginError
from techtree_hermes.schemas import all_tool_schemas
from techtree_hermes.tools import TOOL_HANDLERS


def test_registration_succeeds_without_the_techtree_cli(
    ctx: RecordingContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A host that has never installed Techtree still loads the plugin."""
    monkeypatch.setenv("PATH", "")

    techtree_hermes.register(ctx)


def test_registration_registers_every_implemented_tool(ctx: RecordingContext) -> None:
    techtree_hermes.register(ctx)

    assert set(ctx.tools) == set(TOOL_HANDLERS)
    schemas = all_tool_schemas()
    for name, registered in ctx.tools.items():
        assert registered.toolset == TOOLSET_NAME
        assert registered.schema == schemas[name]
        assert registered.description == schemas[name]["description"]
        # The host calls handler(args, **kwargs); the services it works
        # through were supplied at registration, not by the caller.
        assert registered.handler.__wrapped__ is TOOL_HANDLERS[name]


def test_registration_registers_implemented_commands_and_hooks(
    ctx: RecordingContext,
) -> None:
    from techtree_hermes.commands import CLI_COMMAND_NAMES, SLASH_COMMANDS
    from techtree_hermes.hooks import SESSION_HOOKS

    techtree_hermes.register(ctx)

    assert set(ctx.commands) == set(SLASH_COMMANDS)
    assert set(ctx.cli_commands) == set(CLI_COMMAND_NAMES)
    assert set(ctx.hooks) == set(SESSION_HOOKS)


def test_registration_refuses_a_tool_the_manifest_never_declared(
    ctx: RecordingContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A handler without a declared schema is a build defect, not a surprise."""

    def handler(args: dict[str, object], **kwargs: object) -> str:
        return "{}"

    monkeypatch.setattr(
        techtree_hermes, "TOOL_HANDLERS", MappingProxyType({"techtree_secret": handler})
    )

    with pytest.raises(PluginError, match="no declared schema"):
        techtree_hermes.register(ctx)

    assert ctx.tools == {}


def test_registration_namespaces_bundled_skills(
    ctx: RecordingContext, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Bundled Skills register by directory name, under the plugin namespace."""
    operator = tmp_path / "skills" / "operator"
    operator.mkdir(parents=True)
    (operator / "SKILL.md").write_text("# Operator\n", encoding="utf-8")
    (tmp_path / "skills" / "not-a-skill").mkdir()
    monkeypatch.setattr(techtree_hermes, "PLUGIN_ROOT", tmp_path)

    techtree_hermes.register(ctx)

    assert set(ctx.skills) == {"operator"}
    assert ctx.skills["operator"].path == operator


def test_registration_exposes_the_verified_release_digest(
    ctx: RecordingContext,
) -> None:
    """The container registration builds carries the release it verified."""
    from techtree_hermes.services.container import build_services

    services = build_services(ctx)

    assert services.release_core_digest.startswith("sha256:")
    assert services.release_core.schema_version == "techtree.release-core.v1"
