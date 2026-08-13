"""Installation only ever happens because a person said yes.

Specification sections 7.6 and 7.15 (bootstrap rows), amended by decision
0007 R10: a release that has not chosen its coordinates yet is refused by the
public flow, and the developer override is not something a model can ask for.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from support import FakeCli, envelope, install_fake_cli, print_envelope
from techtree_hermes.approvals import InstallPlanStore
from techtree_hermes.bootstrap import (
    DEVELOPER_OVERRIDE_VARIABLE,
    TERMINAL_TOOL,
    UV_DOCUMENTATION_URL,
    bootstrap_check,
    create_install_plan,
    display_command,
    install_cli_with_approval,
    manual_install_response,
    release_install_refusal,
    uv_prerequisite,
)
from techtree_hermes.bridge import CliBridge
from techtree_hermes.errors import BootstrapPlanError
from techtree_hermes.models import parse_bootstrap_install_plan
from techtree_hermes.release import load_embedded_release_core, release_core_digest
from techtree_hermes.services.assets import ReleaseSkillProvider
from techtree_hermes.services.container import PluginServices
from techtree_hermes.state import SessionStore

CORE = load_embedded_release_core()
DIGEST = release_core_digest(CORE)

#: The embedded release is a development placeholder, so most of these tests
#: describe a published one.
PUBLISHED = dataclasses.replace(
    CORE,
    placeholder_release=False,
    placeholder_fields=(),
    release_id="0.1.0",
    cli_version="0.1.0",
    cli_source_commit="a" * 40,
)


class RecordingHost:
    """A host whose terminal tool records what it was asked to run."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.dispatched: list[tuple[str, dict[str, Any]]] = []
        self._raises = raises

    def dispatch_tool(self, tool_name: str, args: dict[str, Any]) -> str:
        self.dispatched.append((tool_name, args))
        if self._raises is not None:
            raise self._raises
        return '{"exit_code": 0}'


class HostWithoutTerminal:
    """A host that exposes no tool dispatch at all."""


def _services(
    *, release: Any = PUBLISHED, ctx: Any = None, root: Path | None = None
) -> PluginServices:
    return PluginServices(
        ctx=ctx,
        root=root or Path("."),
        release_core=release,
        release_core_digest=DIGEST,
        bridge=CliBridge(),
        plans=InstallPlanStore(),
        sessions=SessionStore(),
        assets=ReleaseSkillProvider(),
    )


def _no_environment(name: str) -> str | None:
    return None


def _override_environment(name: str) -> str | None:
    return "1" if name == DEVELOPER_OVERRIDE_VARIABLE else None


def _only_uv(name: str) -> str | None:
    return "/usr/local/bin/uv" if name == "uv" else None


def _nothing_installed(name: str) -> str | None:
    return None


# uv ------------------------------------------------------------------------------


def test_missing_uv_returns_instructions_not_an_installer() -> None:
    prerequisite = uv_prerequisite()

    assert prerequisite["code"] == "uv_not_found"
    assert prerequisite["documentation_url"] == UV_DOCUMENTATION_URL
    assert prerequisite["options"]
    for option in prerequisite["options"]:
        assert "curl" not in option
        assert "|" not in option
        assert "sh " not in option


def test_a_host_without_uv_is_told_what_to_do_and_offered_no_plan() -> None:
    result = bootstrap_check(
        _services(),
        include_doctor=False,
        path_lookup=_nothing_installed,
        environment=_no_environment,
    )

    assert result["uv"]["installed"] is False
    assert result["uv"]["prerequisite"]["code"] == "uv_not_found"
    assert result["install_plan"] is None
    assert result["next_action"]["id"] == "install_uv"


# The plan --------------------------------------------------------------------------


def test_a_missing_cli_produces_one_exact_plan() -> None:
    services = _services()

    result = bootstrap_check(
        services,
        include_doctor=False,
        path_lookup=_only_uv,
        environment=_no_environment,
    )

    plan = result["install_plan"]
    assert plan["argv"] == ["uv", "tool", "install", "techtree==0.1.0"]
    assert plan["command"] == "uv tool install techtree==0.1.0"
    assert plan["requires_confirmation"] is True
    assert result["next_action"]["tool"] == "techtree_bootstrap_install"
    assert result["next_action"]["requires_user_confirmation"] is True
    assert services.plans.get(plan["plan_id"]) is not None


def test_the_plan_names_only_the_release_version() -> None:
    """Nothing about the command is negotiable, including by this plugin."""
    plan = create_install_plan(
        PUBLISHED, uv_path="/usr/local/bin/uv", release_core_digest=DIGEST
    )

    assert plan.package == "techtree"
    assert plan.version == PUBLISHED.cli_version
    assert plan.argv[0] == "uv"
    assert f"techtree=={PUBLISHED.cli_version}" in plan.argv
    assert (
        parse_bootstrap_install_plan(
            {
                "plan_id": plan.plan_id,
                "package": plan.package,
                "version": plan.version,
                "argv": list(plan.argv),
                "release_core_digest": plan.release_core_digest,
                "requires_confirmation": plan.requires_confirmation,
                "created_at": plan.created_at,
                "expires_at": plan.expires_at,
            }
        )
        == plan
    )


def test_a_plan_expires() -> None:
    services = _services()
    issued = datetime.now(UTC) - timedelta(hours=2)
    plan = create_install_plan(
        PUBLISHED,
        uv_path="/usr/local/bin/uv",
        release_core_digest=DIGEST,
        now=issued,
    )
    services.plans.save(plan)

    with pytest.raises(BootstrapPlanError, match="expired"):
        install_cli_with_approval(
            RecordingHost(),
            services,
            plan_id=plan.plan_id,
            environment=_no_environment,
        )


def test_a_plan_identifier_that_was_never_offered_is_refused() -> None:
    services = _services()

    with pytest.raises(BootstrapPlanError, match="not offered"):
        install_cli_with_approval(
            RecordingHost(),
            services,
            plan_id="install_" + "0" * 32,
            environment=_no_environment,
        )


def test_a_plan_from_another_release_is_refused() -> None:
    services = _services()
    plan = create_install_plan(
        PUBLISHED,
        uv_path="/usr/local/bin/uv",
        release_core_digest="sha256:" + "9" * 64,
    )
    services.plans.save(plan)

    with pytest.raises(BootstrapPlanError, match="different release"):
        install_cli_with_approval(
            RecordingHost(),
            services,
            plan_id=plan.plan_id,
            environment=_no_environment,
        )


def test_expired_plans_are_pruned() -> None:
    store = InstallPlanStore()
    old = create_install_plan(
        PUBLISHED,
        uv_path="/usr/local/bin/uv",
        release_core_digest=DIGEST,
        now=datetime.now(UTC) - timedelta(hours=2),
    )
    fresh = create_install_plan(
        PUBLISHED, uv_path="/usr/local/bin/uv", release_core_digest=DIGEST
    )
    store.save(old)
    store.save(fresh)

    assert store.prune_expired() == 1
    assert store.count() == 1


# Approval ----------------------------------------------------------------------------


def test_installation_goes_through_the_hosts_own_terminal_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _installed_cli(tmp_path, monkeypatch)
    services = _services()
    plan = create_install_plan(
        PUBLISHED, uv_path="/usr/local/bin/uv", release_core_digest=DIGEST
    )
    services.plans.save(plan)
    host = RecordingHost()

    result = install_cli_with_approval(
        host, services, plan_id=plan.plan_id, environment=_no_environment
    )

    assert host.dispatched == [
        (TERMINAL_TOOL, {"command": "uv tool install techtree==0.1.0"})
    ]
    assert result["approval"] == "host_terminal"


def test_the_dispatched_command_carries_nothing_but_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No force flag, no background, nothing that could skip the human."""
    _installed_cli(tmp_path, monkeypatch)
    services = _services()
    plan = create_install_plan(
        PUBLISHED, uv_path="/usr/local/bin/uv", release_core_digest=DIGEST
    )
    services.plans.save(plan)
    host = RecordingHost()

    install_cli_with_approval(
        host, services, plan_id=plan.plan_id, environment=_no_environment
    )

    _, args = host.dispatched[0]
    assert set(args) == {"command"}


def test_a_host_without_a_terminal_gets_manual_instructions() -> None:
    services = _services()
    plan = create_install_plan(
        PUBLISHED, uv_path="/usr/local/bin/uv", release_core_digest=DIGEST
    )
    services.plans.save(plan)

    result = install_cli_with_approval(
        HostWithoutTerminal(),
        services,
        plan_id=plan.plan_id,
        environment=_no_environment,
    )

    assert result["installed"] is False
    assert result["approval"] == "manual"
    assert result["plan"]["command"] == "uv tool install techtree==0.1.0"


def test_a_refused_dispatch_never_becomes_a_direct_install() -> None:
    """When approval is unavailable the plugin stops; it does not run it."""
    services = _services()
    plan = create_install_plan(
        PUBLISHED, uv_path="/usr/local/bin/uv", release_core_digest=DIGEST
    )
    services.plans.save(plan)
    host = RecordingHost(raises=PermissionError("the user declined"))

    result = install_cli_with_approval(
        host, services, plan_id=plan.plan_id, environment=_no_environment
    )

    assert result["installed"] is False
    assert result["approval"] == "manual"
    assert "declined" in result["message"]


def test_a_plan_is_single_use() -> None:
    services = _services()
    plan = create_install_plan(
        PUBLISHED, uv_path="/usr/local/bin/uv", release_core_digest=DIGEST
    )
    services.plans.save(plan)

    install_cli_with_approval(
        HostWithoutTerminal(),
        services,
        plan_id=plan.plan_id,
        environment=_no_environment,
    )

    assert services.plans.get(plan.plan_id) is None


def test_the_manual_response_shows_the_exact_command() -> None:
    plan = create_install_plan(
        PUBLISHED, uv_path="/usr/local/bin/uv", release_core_digest=DIGEST
    )

    response = manual_install_response(plan)

    assert response["plan"]["argv"] == list(plan.argv)
    assert response["plan"]["command"] == display_command(plan)


# A release nobody has finished --------------------------------------------------------


def test_a_placeholder_release_refuses_the_public_install_flow() -> None:
    """Decision 0007 R10."""
    refusal = release_install_refusal(CORE, environment=_no_environment)

    assert refusal is not None
    assert refusal["code"] == "bootstrap_release_placeholder"
    assert "development placeholder" in refusal["message"]
    assert refusal["placeholder_fields"] == list(CORE.placeholder_fields)


def test_a_placeholder_release_is_never_offered_a_plan() -> None:
    services = _services(release=CORE)

    result = bootstrap_check(
        services,
        include_doctor=False,
        path_lookup=_only_uv,
        environment=_no_environment,
    )

    assert result["install_plan"] is None
    assert result["refusal"]["code"] == "bootstrap_release_placeholder"
    assert result["next_action"]["id"] == "install_refused"
    assert services.plans.count() == 0


def test_a_placeholder_release_refuses_installation_even_with_a_plan() -> None:
    """The refusal is not only an absence of a plan; the install refuses too."""
    services = _services(release=CORE)
    plan = create_install_plan(
        CORE, uv_path="/usr/local/bin/uv", release_core_digest=DIGEST
    )
    services.plans.save(plan)
    host = RecordingHost()

    with pytest.raises(BootstrapPlanError, match="development placeholder"):
        install_cli_with_approval(
            host, services, plan_id=plan.plan_id, environment=_no_environment
        )

    assert host.dispatched == []


def test_a_developer_can_override_the_refusal_on_their_own_machine() -> None:
    assert release_install_refusal(CORE, environment=_override_environment) is None


def test_the_override_is_not_something_a_caller_can_pass() -> None:
    """It is an environment variable, so no tool argument can reach it."""
    from techtree_hermes.schemas import all_tool_schemas

    for name, schema in all_tool_schemas().items():
        for property_name in schema["properties"]:
            assert "override" not in property_name.lower(), name
            assert "placeholder" not in property_name.lower(), name
            assert "allow" not in property_name.lower(), name


# What landed --------------------------------------------------------------------------


def _installed_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, release: Any = PUBLISHED
) -> FakeCli:
    """Install a fake CLI that reports the given release and a clean Doctor."""
    info = {
        "release_id": release.release_id,
        "cli_version": release.cli_version,
        "package_version": release.cli_version,
        "cli_source_commit": release.cli_source_commit,
        "protocol_version": release.protocol_version,
        "release_core_digest": release_core_digest(release),
        "engine_digest": release.engine_digest,
        "catalog_digest": release.catalog_digest,
        "intro_climb_reference": release.intro_climb_reference,
        "placeholder_release": release.placeholder_release,
        "placeholder_fields": list(release.placeholder_fields),
    }
    doctor = {
        "checks": [
            {
                "id": "docker_daemon",
                "label": "Docker daemon",
                "status": "pass",
                "detail": "reachable",
                "blocking": False,
                "metadata": {},
            }
        ]
    }
    info_envelope = envelope(command="release info", data=info)
    doctor_envelope = envelope(command="doctor", data=doctor)
    body = (
        "if argv[:1] == ['--version']:\n"
        f"    print({release.cli_version!r})\n"
        "elif argv[:2] == ['release', 'info']:\n"
        f"    print(json.dumps({info_envelope!r}))\n"
        "else:\n"
        f"    print(json.dumps({doctor_envelope!r}))\n"
    )
    return install_fake_cli(tmp_path / "bin", body=body, monkeypatch=monkeypatch)


def test_an_installed_release_that_matches_verifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _installed_cli(tmp_path, monkeypatch)
    services = _services()
    plan = create_install_plan(
        PUBLISHED, uv_path="/usr/local/bin/uv", release_core_digest=DIGEST
    )
    services.plans.save(plan)

    result = install_cli_with_approval(
        RecordingHost(), services, plan_id=plan.plan_id, environment=_no_environment
    )

    assert result["installed"] is True
    assert result["verification"]["version"] == PUBLISHED.cli_version
    assert result["verification"]["release"]["compatible"] is True
    assert result["verification"]["doctor"]["can_prepare_demo"] is True


def test_an_installed_release_that_differs_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = dataclasses.replace(PUBLISHED, cli_version="9.9.9", release_id="9.9.9")
    _installed_cli(tmp_path, monkeypatch, release=other)
    services = _services()
    plan = create_install_plan(
        PUBLISHED, uv_path="/usr/local/bin/uv", release_core_digest=DIGEST
    )
    services.plans.save(plan)

    result = install_cli_with_approval(
        RecordingHost(), services, plan_id=plan.plan_id, environment=_no_environment
    )

    assert result["installed"] is False
    verification = result["verification"]
    assert verification["code"] == "bootstrap_post_install_verify_failed"
    assert "cli_version" in verification["release"]["mismatches"]


def test_a_blocking_doctor_failure_stops_demo_preparation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doctor = {
        "checks": [
            {
                "id": "docker_daemon",
                "label": "Docker daemon",
                "status": "fail",
                "detail": "Docker is not running",
                "blocking": True,
                "metadata": {},
            }
        ]
    }
    install_fake_cli(
        tmp_path / "bin",
        body=print_envelope(
            command="doctor",
            data=doctor,
            ok=False,
            error={
                "code": "docker_unavailable",
                "message": "Docker is not running",
                "retryable": True,
                "details": {},
            },
        ),
        monkeypatch=monkeypatch,
    )
    services = _services()

    from techtree_hermes.bootstrap import doctor_summary

    summary = doctor_summary(services)

    assert summary["ran"] is True
    assert summary["can_prepare_demo"] is False
    assert summary["blocking_failures"][0]["id"] == "docker_daemon"


def test_an_installed_host_is_checked_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = _installed_cli(tmp_path, monkeypatch)
    services = _services()

    result = bootstrap_check(services, environment=_no_environment)

    assert result["cli"]["installed"] is True
    assert result["cli"]["version"] == PUBLISHED.cli_version
    assert result["release_compatibility"]["compatible"] is True
    assert result["doctor"]["can_prepare_demo"] is True
    assert result["next_action"]["id"] == "inspect_climbs"
    assert ["--version"] in cli.recorded_argv()
