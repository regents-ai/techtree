"""The machine boundary, exercised the way a host agent uses it. Spec 6.1, 12.

Every test here runs a real ``uv run techtree`` subprocess. That is the point:
the contract is about a process — its stdout, its stderr, its exit status, and
the fact that it never waits for a human — and none of those can be observed
honestly from inside the interpreter that would be answering the questions.

stdin is closed for every invocation and every invocation has a timeout, so a
command that decided to prompt fails these tests by hanging into a timeout
rather than by quietly passing.

Every subprocess gets its own ``--home`` under ``tmp_path`` and an environment
stripped of ``TECHTREE_*``. Nothing here reads or writes the real user home.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from techtree.errors import EXIT_ERROR, EXIT_OK, EXIT_PREREQUISITE, EXIT_USAGE
from techtree.version import package_version

#: A generous ceiling. Doctor probes Docker, which can be slow; anything past
#: this is a command that is waiting for something it will never get.
TIMEOUT_SECONDS = 120

#: Any escape sequence at all. Machine output has none, and human output has
#: none when stdout is a pipe.
ANSI = re.compile(r"\x1b\[")


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

    def run(*arguments: str, home_option: bool = True) -> Invocation:
        argv = ["uv", "run", "techtree"]
        if home_option:
            argv += ["--home", str(techtree_home)]
        completed = subprocess.run(
            [*argv, *arguments],
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


# ---------------------------------------------------------------------------
# One object on stdout, logs on stderr
# ---------------------------------------------------------------------------


def test_doctor_emits_exactly_one_json_envelope(techtree: Any) -> None:
    result = techtree("doctor", "--json")

    envelope = result.envelope()
    assert envelope["schema_version"] == "techtree.cli.v1"
    assert envelope["command"] == "doctor"
    assert envelope["ok"] is (envelope["error"] is None)
    assert result.exit_code in (EXIT_OK, EXIT_PREREQUISITE)


def test_the_doctor_envelope_reports_the_normalized_host_platform(
    techtree: Any,
) -> None:
    envelope = techtree("doctor", "--json").envelope()

    report = envelope["data"]
    assert re.fullmatch(r"(darwin|linux)/(arm64|amd64)", report["host_platform"])

    by_id = {check["id"]: check for check in report["checks"]}
    assert by_id["host_platform"]["detail"] == report["host_platform"]
    if report["docker_platform"] is not None:
        assert (
            by_id["docker_daemon"]["metadata"]["docker_platform"]
            == (report["docker_platform"])
        )


def test_the_doctor_envelope_runs_every_documented_check(techtree: Any) -> None:
    envelope = techtree("doctor", "--json").envelope()

    assert [check["id"] for check in envelope["data"]["checks"]] == [
        "python_version",
        "host_platform",
        "techtree_home",
        "uv",
        "docker_cli",
        "docker_daemon",
        "hermes",
        "active_engine",
    ]


def test_machine_output_carries_no_escape_sequences(techtree: Any) -> None:
    result = techtree("doctor", "--json")

    assert not ANSI.search(result.stdout)
    assert not ANSI.search(result.stderr)


def test_a_quiet_machine_run_says_nothing_on_stderr(techtree: Any) -> None:
    result = techtree("doctor", "--json")

    assert result.stderr == ""


def test_debug_logging_goes_to_stderr_and_leaves_stdout_alone(techtree: Any) -> None:
    result = techtree("doctor", "--json", "--debug")

    result.envelope()
    assert "techtree: running doctor" in result.stderr
    assert "techtree: doctor exited with code" in result.stderr
    assert "techtree: running doctor" not in result.stdout


def test_human_output_is_plain_text_when_stdout_is_a_pipe(techtree: Any) -> None:
    result = techtree("doctor")

    assert not ANSI.search(result.stdout)
    assert "Host platform:" in result.stdout
    assert "Python version" in result.stdout


# ---------------------------------------------------------------------------
# Global options anywhere, and never a prompt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "arguments",
    [
        ("--json", "doctor"),
        ("doctor", "--json"),
        ("--json", "--no-input", "doctor"),
        ("doctor", "--json", "--no-color", "--no-input"),
    ],
)
def test_the_json_flag_is_understood_wherever_it_appears(
    techtree: Any, arguments: tuple[str, ...]
) -> None:
    result = techtree(*arguments)

    assert result.envelope()["command"] == "doctor"


def test_no_input_never_prompts_and_never_waits(techtree: Any) -> None:
    # stdin is already closed for every invocation, so a command that asked a
    # question would either fail loudly or hang into the timeout.
    result = techtree("--no-input", "doctor", "--json")

    assert result.exit_code in (EXIT_OK, EXIT_PREREQUISITE)
    assert result.envelope()["command"] == "doctor"


def test_version_prints_the_package_version_and_nothing_else(techtree: Any) -> None:
    result = techtree("--version", home_option=False)

    assert result.exit_code == EXIT_OK
    assert result.stdout.strip() == package_version()
    assert result.stderr == ""


# ---------------------------------------------------------------------------
# Stable command and error identifiers
# ---------------------------------------------------------------------------


# Only the commands this build has not implemented yet. `climb list` and
# `climb show` are implemented and are exercised in
# ``tests/contract/test_catalog_object_graph.py``; the `engine` commands are
# implemented and are exercised in
# ``tests/integration/test_engine_install.py``.
@pytest.mark.parametrize(
    ("arguments", "command"),
    [
        (("climb", "prepare"), "climb prepare"),
        (("climb", "start"), "climb start"),
        (("run", "status"), "run status"),
        (("run", "logs"), "run logs"),
        (("run", "cancel"), "run cancel"),
        (("run", "result"), "run result"),
    ],
)
def test_a_registered_command_names_itself_and_reports_not_implemented(
    techtree: Any, arguments: tuple[str, ...], command: str
) -> None:
    result = techtree(*arguments, "--json")

    envelope = result.envelope()
    assert envelope["command"] == command
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "not_implemented"
    assert envelope["error"]["details"]["command"] == command
    assert result.exit_code == EXIT_ERROR


@pytest.mark.parametrize(
    "namespace",
    ["program", "blueprint", "forge", "verify", "uplift", "trace", "lab"],
)
def test_a_reserved_namespace_is_not_registered(techtree: Any, namespace: str) -> None:
    result = techtree(namespace, "--json")

    assert result.exit_code == EXIT_USAGE
    assert result.stdout == ""


def test_an_unknown_command_is_a_usage_error_with_nothing_on_stdout(
    techtree: Any,
) -> None:
    result = techtree("definitely-not-a-command", "--json")

    assert result.exit_code == EXIT_USAGE
    assert result.stdout == ""
    assert result.stderr != ""


def test_no_command_at_all_is_a_machine_readable_usage_error(techtree: Any) -> None:
    result = techtree("--json")

    envelope = result.envelope()
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "no_command"
    assert result.exit_code == EXIT_USAGE


# ---------------------------------------------------------------------------
# Failures before a command can start
# ---------------------------------------------------------------------------


def test_unreadable_settings_still_produce_one_envelope(
    techtree: Any, techtree_home: Path
) -> None:
    techtree_home.mkdir()
    (techtree_home / "config.toml").write_text(
        "this is = = not toml\n", encoding="utf-8"
    )

    result = techtree("doctor", "--json")

    envelope = result.envelope()
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "validation_error"
    assert envelope["command"] == "doctor"
    assert result.exit_code == 3


def test_a_next_action_is_always_an_argument_vector(techtree: Any) -> None:
    envelope = techtree("doctor", "--json").envelope()

    for step in envelope["next_actions"]:
        assert step["cli"] is None or isinstance(step["cli"], list)
        assert step["cli"] or step["hermes_tool"]
        if step["cli"]:
            assert all(isinstance(word, str) for word in step["cli"])
    assert len(envelope["next_actions"]) <= 3


def test_no_envelope_field_looks_like_a_credential(techtree: Any) -> None:
    rendered = techtree("doctor", "--json").stdout.lower()

    for forbidden in ("api_key", "secret", "password", "bearer "):
        assert forbidden not in rendered


def test_the_bare_command_shows_help_rather_than_an_envelope(techtree: Any) -> None:
    result = techtree(home_option=False)

    assert result.exit_code == EXIT_USAGE
    assert "Usage: techtree" in result.stdout
    assert not ANSI.search(result.stdout)
