"""The terminal subcommands, against a real process. Sections 7.12, 7.15.

`hermes techtree …` exists so Techtree's own human output reaches the terminal
a person is looking at. These tests run a real executable named ``techtree``
and check that the plugin invoked it in human mode — no machine flags, output
inherited — and returned its exit code.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest
from support import install_fake_cli
from techtree_hermes.approvals import InstallPlanStore, ReviewStore
from techtree_hermes.bridge import CliBridge
from techtree_hermes.commands import build_cli_commands
from techtree_hermes.release import load_embedded_release_core, release_core_digest
from techtree_hermes.services.assets import ReleaseSkillProvider
from techtree_hermes.services.container import PluginServices
from techtree_hermes.state import SessionStore

CORE = load_embedded_release_core()
RUN_ID = "run_" + "0" * 32


def _namespace(**values: Any) -> Any:
    return dataclasses.make_dataclass("Namespace", values)(**values)


@pytest.fixture
def services(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PluginServices:
    """A container wired to a fake Techtree that echoes how it was called."""
    body = (
        "print('techtree human output for: ' + ' '.join(argv))\n"
        "sys.exit(0 if 'fail' not in argv else 3)\n"
    )
    install_fake_cli(tmp_path / "bin", body=body, monkeypatch=monkeypatch)
    return PluginServices(
        ctx=None,
        root=tmp_path,
        release_core=CORE,
        release_core_digest=release_core_digest(CORE),
        bridge=CliBridge(),
        plans=InstallPlanStore(),
        reviews=ReviewStore(),
        sessions=SessionStore(),
        assets=ReleaseSkillProvider(),
    )


def test_doctor_runs_techtrees_own_output(
    services: PluginServices, capfd: pytest.CaptureFixture[str]
) -> None:
    code = build_cli_commands(services)["doctor"].handler(_namespace())

    assert code == 0
    assert "techtree human output for: doctor" in capfd.readouterr().out


def test_human_mode_never_adds_the_machine_flags(
    services: PluginServices, capfd: pytest.CaptureFixture[str]
) -> None:
    """Rich output is the point here; --json would defeat it."""
    build_cli_commands(services)["result"].handler(_namespace(run_id=RUN_ID))

    printed = capfd.readouterr().out
    assert f"run result {RUN_ID}" in printed
    assert "--json" not in printed
    assert "--no-color" not in printed


def test_watch_follows_the_run_in_the_terminal(
    services: PluginServices, capfd: pytest.CaptureFixture[str]
) -> None:
    build_cli_commands(services)["watch"].handler(_namespace(run_id=RUN_ID))

    assert f"run status {RUN_ID} --watch" in capfd.readouterr().out


def test_verify_passes_the_path_through(
    services: PluginServices, capfd: pytest.CaptureFixture[str]
) -> None:
    build_cli_commands(services)["verify"].handler(_namespace(target="/tmp/proof"))

    assert "proof verify /tmp/proof" in capfd.readouterr().out


def test_the_exit_code_is_the_cli_s_own(
    services: PluginServices, capfd: pytest.CaptureFixture[str]
) -> None:
    code = build_cli_commands(services)["status"].handler(_namespace(run_id="fail"))

    assert code == 3


def test_the_demo_command_prints_plain_text(
    services: PluginServices, capfd: pytest.CaptureFixture[str]
) -> None:
    """This build refuses the guided introduction, and says why in the terminal."""
    code = build_cli_commands(services)["demo"].handler(_namespace())

    printed = capfd.readouterr().out
    assert code == 0
    assert "cannot start yet" in printed
    assert "\x1b" not in printed
