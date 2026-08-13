"""``techtree release info|verify`` as a host agent sees them. Spec section 9.5.

Every test here runs a real ``uv run techtree`` subprocess with stdin closed,
against a Techtree home under ``tmp_path`` and an environment stripped of
``TECHTREE_*``. The contract being checked is about a process — its envelope,
its exit status, and the promise that it changes nothing — and none of that can
be observed honestly from inside the interpreter that would be answering.

The dry-run promise matters more for these two commands than for most. A host
agent runs ``release verify`` immediately after installing the CLI, before
anything has been set up and before the operator has agreed to anything, so a
command that created state, prompted, or reached out would be unusable exactly
where it is needed.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from techtree.errors import EXIT_OK, EXIT_VALIDATION, EXIT_VERIFICATION
from techtree.release.document import document_digest, packaged_release_core_bytes

#: Generous, but finite: anything past this is a command waiting for a human.
TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class Invocation:
    """What one real ``techtree`` process did."""

    exit_code: int
    stdout: str
    stderr: str

    def envelope(self) -> dict[str, Any]:
        """Parse the single JSON object on stdout, insisting there is one."""
        lines = self.stdout.splitlines()
        assert len(lines) == 1, f"expected one JSON object, got {self.stdout!r}"
        parsed = json.loads(lines[0])
        assert isinstance(parsed, dict)
        return parsed


@pytest.fixture(scope="module")
def repository_root() -> Path:
    """The project directory ``uv run`` is invoked from."""
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def techtree_home(tmp_path: Path) -> Path:
    """The isolated Techtree home every subprocess in one test shares."""
    return tmp_path / "techtree-home"


@pytest.fixture
def techtree(repository_root: Path, techtree_home: Path) -> Any:
    """Return a callable that runs the real CLI against an isolated home."""
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("TECHTREE_")
    }

    def run(*arguments: str) -> Invocation:
        completed = subprocess.run(
            ["uv", "run", "techtree", "--home", str(techtree_home), *arguments],
            cwd=repository_root,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
            stdin=subprocess.DEVNULL,
            env=environment,
        )
        return Invocation(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    return run


def checks(envelope: dict[str, Any]) -> dict[str, Any]:
    """Return the checks a verification envelope carries, keyed by identifier."""
    return {check["id"]: check for check in envelope["data"]["checks"]}


# ---------------------------------------------------------------------------
# release info
# ---------------------------------------------------------------------------


def test_release_info_reports_every_coordinate_the_spec_lists(techtree: Any) -> None:
    result = techtree("release", "info", "--json", "--no-color", "--no-input")
    assert result.exit_code == EXIT_OK

    data = result.envelope()["data"]
    assert set(data) >= {
        "cli_version",
        "cli_source_commit",
        "protocol_version",
        "release_core_digest",
        "engine_digest",
        "catalog_digest",
        "intro_climb_reference",
    }
    assert data["release_core_digest"] == document_digest(packaged_release_core_bytes())


def test_release_info_says_out_loud_that_this_release_is_a_placeholder(
    techtree: Any,
) -> None:
    envelope = techtree("release", "info", "--json").envelope()

    assert envelope["data"]["placeholder_release"] is True
    assert envelope["data"]["placeholder_fields"]
    assert [warning["code"] for warning in envelope["warnings"]] == [
        "release_placeholder"
    ]


def test_release_info_shows_the_installed_version_beside_the_named_one(
    techtree: Any,
) -> None:
    """While a release is a placeholder those two differ, and hiding that lies."""
    data = techtree("release", "info", "--json").envelope()["data"]

    assert data["cli_version"] == "0.0.0-placeholder"
    assert data["package_version"] != data["cli_version"]


# ---------------------------------------------------------------------------
# release verify
# ---------------------------------------------------------------------------


def test_release_verify_passes_on_this_build(techtree: Any) -> None:
    result = techtree("release", "verify", "--json", "--no-color", "--no-input")
    assert result.exit_code == EXIT_OK

    envelope = result.envelope()
    assert envelope["ok"] is True
    assert envelope["error"] is None
    assert envelope["data"]["verified"] is True
    assert envelope["messages"][0]["code"] == "release_verified"


def test_release_verify_accepts_the_published_digest(techtree: Any) -> None:
    digest = document_digest(packaged_release_core_bytes())
    result = techtree("release", "verify", "--expected", digest, "--json")

    assert result.exit_code == EXIT_OK
    assert checks(result.envelope())["release_core_digest"]["status"] == "passed"


def test_release_verify_refuses_the_wrong_digest(techtree: Any) -> None:
    result = techtree(
        "release", "verify", "--expected", "sha256:" + "0e" * 32, "--json"
    )
    assert result.exit_code == EXIT_VERIFICATION

    envelope = result.envelope()
    assert envelope["ok"] is False
    assert envelope["data"]["verified"] is False
    assert envelope["error"]["code"] == "release_not_verified"
    assert envelope["error"]["details"]["failed_checks"] == ["release_core_digest"]


def test_release_verify_reports_the_check_it_could_not_run(techtree: Any) -> None:
    envelope = techtree("release", "verify", "--json").envelope()
    assert checks(envelope)["release_core_digest"]["status"] == "skipped"


def test_a_malformed_expected_digest_is_a_typed_failure(techtree: Any) -> None:
    result = techtree("release", "verify", "--expected", "not-a-digest", "--json")

    assert result.exit_code == EXIT_VALIDATION
    assert result.envelope()["ok"] is False


# ---------------------------------------------------------------------------
# Both commands are dry runs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("subcommand", ["info", "verify"])
def test_a_release_command_writes_no_state(
    techtree: Any, techtree_home: Path, subcommand: str
) -> None:
    """Every command creates the home layout; only directories may appear."""
    assert techtree("release", subcommand, "--json").exit_code == EXIT_OK

    written = [path for path in techtree_home.rglob("*") if path.is_file()]
    assert written == []


@pytest.mark.parametrize("subcommand", ["info", "verify"])
def test_a_release_command_leaves_the_release_document_alone(
    techtree: Any, subcommand: str
) -> None:
    before = packaged_release_core_bytes()
    assert techtree("release", subcommand, "--json").exit_code == EXIT_OK
    assert packaged_release_core_bytes() == before


@pytest.mark.parametrize("subcommand", ["info", "verify"])
def test_a_release_command_never_waits_for_a_human(
    techtree: Any, subcommand: str
) -> None:
    """stdin is closed, so a prompt fails these tests by timing out."""
    result = techtree("release", subcommand, "--json")

    assert result.exit_code == EXIT_OK
    assert result.envelope()["ok"] is True


def test_the_release_group_is_discoverable(techtree: Any) -> None:
    result = techtree("release", "--help")

    assert result.exit_code == EXIT_OK
    assert "info" in result.stdout
    assert "verify" in result.stdout
