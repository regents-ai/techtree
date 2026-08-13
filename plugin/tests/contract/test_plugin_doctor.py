"""The plugin doctor. Specification sections 7.4, 7.15, 9.18.

Two things are checked here: that this build passes its own doctor, and that
the doctor tells the truth about a host with and without the Techtree CLI —
a missing CLI is a warning with a repair, never a broken plugin.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from techtree_hermes.constants import MANIFEST_FILENAME, RELEASE_CORE_FILENAME
from techtree_hermes.doctor import (
    DoctorReport,
    format_report,
    main,
    read_manifest,
    run_plugin_doctor,
)


def _no_executables(name: str) -> str | None:
    return None


def _all_executables(name: str) -> str | None:
    return f"/usr/local/bin/{name}"


def _check(report: DoctorReport, check_id: str) -> Any:
    return next(check for check in report.checks if check.id == check_id)


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """A copy of this plugin that a test may damage."""
    from techtree_hermes.constants import PLUGIN_ROOT

    destination = tmp_path / "plugin"
    shutil.copytree(
        PLUGIN_ROOT,
        destination,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", ".mypy_cache"),
    )
    return destination


# A sound build ----------------------------------------------------------------


def test_this_build_passes_its_own_doctor() -> None:
    report = run_plugin_doctor()

    assert report.ok, format_report(report)
    for check_id in (
        "plugin_manifest",
        "tool_schemas",
        "release_core",
        "runtime_imports",
        "tool_handlers",
        "hook_callbacks",
    ):
        assert _check(report, check_id).status != "fail"


def test_the_runtime_imports_only_the_standard_library() -> None:
    """No third-party dependency, and no Techtree Python import."""
    check = _check(run_plugin_doctor(), "runtime_imports")

    assert check.status == "pass"
    assert check.blocking is True


def test_the_report_is_json_ready() -> None:
    report = run_plugin_doctor(path_lookup=_all_executables)

    document = json.loads(json.dumps(report.to_dict()))

    assert document["ok"] is True
    assert document["plugin_id"] == "techtree"
    assert {check["id"] for check in document["checks"]} >= {"techtree_cli", "uv"}


# With and without an installed CLI ---------------------------------------------


def test_a_host_without_the_cli_is_warned_not_failed() -> None:
    report = run_plugin_doctor(path_lookup=_no_executables)

    cli = _check(report, "techtree_cli")
    assert report.ok
    assert cli.status == "warn"
    assert cli.blocking is False
    assert "techtree_bootstrap_check" in cli.repair


def test_a_host_without_uv_is_told_how_to_get_it() -> None:
    report = run_plugin_doctor(path_lookup=_no_executables)

    uv = _check(report, "uv")
    assert uv.status == "warn"
    assert "Install uv" in uv.repair


def test_a_host_with_the_cli_reports_where_it_is() -> None:
    report = run_plugin_doctor(path_lookup=_all_executables)

    cli = _check(report, "techtree_cli")
    assert cli.status == "pass"
    assert cli.detail.endswith("/usr/local/bin/techtree")
    assert cli.repair is None


def test_only_the_executable_checks_change_with_the_host() -> None:
    """Plugin soundness does not depend on what is installed."""
    without = {
        check.id: check.status
        for check in run_plugin_doctor(path_lookup=_no_executables).checks
    }
    with_cli = {
        check.id: check.status
        for check in run_plugin_doctor(path_lookup=_all_executables).checks
    }

    differing = {
        check_id for check_id, status in without.items() if with_cli[check_id] != status
    }
    assert differing == {"techtree_cli", "uv"}


# A damaged build ---------------------------------------------------------------


def test_a_broken_release_file_blocks(checkout: Path) -> None:
    (checkout / RELEASE_CORE_FILENAME).write_text("{}", encoding="utf-8")

    report = run_plugin_doctor(checkout, path_lookup=_all_executables)

    assert not report.ok
    assert _check(report, "release_core").status == "fail"


def test_a_manifest_that_declares_a_different_tool_set_blocks(checkout: Path) -> None:
    manifest = checkout / MANIFEST_FILENAME
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "  - techtree_run_cancel\n", "  - techtree_run_delete\n"
        ),
        encoding="utf-8",
    )

    report = run_plugin_doctor(checkout, path_lookup=_all_executables)

    assert not report.ok
    schemas = _check(report, "tool_schemas")
    assert schemas.status == "fail"
    assert "techtree_run_delete" in schemas.detail


def test_a_manifest_that_asks_for_credentials_is_rejected(checkout: Path) -> None:
    """`requires_env` is not part of this plugin's grammar at all."""
    manifest = checkout / MANIFEST_FILENAME
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + "requires_env:\n  - OPENAI_API_KEY\n",
        encoding="utf-8",
    )

    report = run_plugin_doctor(checkout, path_lookup=_all_executables)

    assert not report.ok
    assert "requires_env" in _check(report, "plugin_manifest").detail


def test_the_runtime_cannot_open_a_connection(checkout: Path) -> None:
    """No handler can upload a result, because none of them can reach a socket."""
    check = _check(
        run_plugin_doctor(checkout, path_lookup=_all_executables), "no_network"
    )

    assert check.status == "pass"
    assert check.blocking is True


def test_a_networking_import_blocks(checkout: Path) -> None:
    (checkout / "uploader.py").write_text("import urllib.request\n", encoding="utf-8")

    report = run_plugin_doctor(checkout, path_lookup=_all_executables)

    assert not report.ok
    assert "urllib" in _check(report, "no_network").detail


def test_no_relay_dependency_exists(checkout: Path) -> None:
    """Relay is deferred, and nothing here quietly reaches for it."""
    from techtree_hermes.doctor import iter_runtime_modules

    for path in iter_runtime_modules(checkout):
        text = path.read_text(encoding="utf-8").lower()
        assert "nemo" not in text
        assert "import relay" not in text


def test_a_runtime_third_party_import_blocks(checkout: Path) -> None:
    (checkout / "bridge.py").write_text("import requests\n", encoding="utf-8")

    report = run_plugin_doctor(checkout, path_lookup=_all_executables)

    imports = _check(report, "runtime_imports")
    assert not report.ok
    assert "requests" in imports.detail


def test_a_runtime_techtree_import_blocks(checkout: Path) -> None:
    """The CLI JSON envelope is the only boundary."""
    (checkout / "bridge.py").write_text("import techtree\n", encoding="utf-8")

    report = run_plugin_doctor(checkout, path_lookup=_all_executables)

    imports = _check(report, "runtime_imports")
    assert not report.ok
    assert "Techtree Python" in imports.detail


def test_bundled_skills_are_reported_when_present(checkout: Path) -> None:
    """This build bundles the operator Skill, namespaced to the plugin."""
    assert (checkout / "skills" / "operator" / "SKILL.md").is_file()

    report = run_plugin_doctor(checkout, path_lookup=_all_executables)

    check = _check(report, "bundled_skills")
    assert check.status == "pass"
    assert check.detail.endswith("techtree:operator")


def test_a_build_without_bundled_skills_is_only_warned(checkout: Path) -> None:
    shutil.rmtree(checkout / "skills")

    report = run_plugin_doctor(checkout, path_lookup=_all_executables)

    check = _check(report, "bundled_skills")
    assert report.ok
    assert check.status == "warn"
    assert check.blocking is False


# Manifest grammar ---------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "name techtree\n",
        "name: techtree\nname: techtree\n",
        "  - orphan\n",
        "unexpected: value\n",
    ],
)
def test_the_manifest_grammar_is_strict(tmp_path: Path, text: str) -> None:
    manifest = tmp_path / MANIFEST_FILENAME
    manifest.write_text(text, encoding="utf-8")

    with pytest.raises(Exception, match="not usable"):
        read_manifest(manifest)


# Command line -------------------------------------------------------------------


def test_the_command_line_reports_success(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([])

    assert code == 0
    assert "Plugin doctor passed." in capsys.readouterr().out


def test_the_command_line_fails_on_a_damaged_build(
    checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (checkout / RELEASE_CORE_FILENAME).unlink()

    code = main(["--json", "--root", str(checkout)])

    assert code == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
