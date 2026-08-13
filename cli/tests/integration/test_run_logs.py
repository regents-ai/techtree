"""Reading a worker's log. Spec PR8 §8.13, §8.17, §10.5.

A worker's log is untrusted output. It holds whatever the worker wrote and
whatever anything the worker called wrote, and it is displayed to a person or
returned to a program without either of them having asked for the file. Two
rules follow, and both are tested here against a real run's real log.

*It is bounded.* A tail has a default, a floor, and a ceiling, and a caller
that asks for something outside them is told so rather than quietly given
something else.

*It is scrubbed.* Anything that looks like a credential is redacted on the way
out, and the identifiers an operator actually needs — run identifiers, digests,
task hashes — survive.

The response never carries the log's path. Handing a host agent a filename is
handing it an invitation to read something that is not this run's log.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fixtures.runs.support import (
    prepare_only,
    run_cli,
    start_through_the_cli,
    wait_for_terminal,
)
from techtree.errors import EXIT_OK, EXIT_USAGE
from techtree.paths import TechtreePaths

pytestmark = pytest.mark.integration


type FinishedRun = tuple[Path, TechtreePaths, str]


@pytest.fixture(scope="module")
def finished(tmp_path_factory: pytest.TempPathFactory) -> FinishedRun:
    """Return a home holding one finished run with a real worker log."""
    home = tmp_path_factory.mktemp("techtree-home")
    paths, prepared = prepare_only(home)
    run_id = start_through_the_cli(home, prepared).data()["run_id"]
    wait_for_terminal(home, run_id)
    return home, paths, run_id


def _append(paths: TechtreePaths, run_id: str, text: str) -> None:
    """Add lines to the run's log the way the worker's own output arrives."""
    with (paths.run_dir(run_id) / "worker.log").open("a", encoding="utf-8") as handle:
        handle.write(text)


# ---------------------------------------------------------------------------
# What the worker recorded
# ---------------------------------------------------------------------------


def test_a_real_run_leaves_a_readable_log(
    finished: FinishedRun,
) -> None:
    home, _, run_id = finished

    logs = run_cli(home, "run", "logs", run_id)

    assert logs.exit_code == EXIT_OK
    lines = logs.data()["lines"]
    assert any(run_id in line for line in lines)
    assert any("fake executor" in line for line in lines)


def test_the_response_does_not_hand_over_a_path(
    finished: FinishedRun,
) -> None:
    """Spec §8.13: never return the raw log path."""
    home, paths, run_id = finished

    envelope = run_cli(home, "run", "logs", run_id).envelope()

    rendered = json.dumps(envelope)
    assert str(paths.run_dir(run_id)) not in rendered
    assert "worker.log" not in rendered


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------


def test_a_tail_returns_only_what_was_asked_for(
    finished: FinishedRun,
) -> None:
    home, paths, run_id = finished
    _append(paths, run_id, "".join(f"filler {number}\n" for number in range(50)))

    payload = run_cli(home, "run", "logs", run_id, "--tail", "5").data()

    assert payload["lines"] == [f"filler {number}" for number in range(45, 50)]
    assert payload["truncated"] is True


@pytest.mark.parametrize("tail", ["0", "5001"])
def test_a_tail_outside_its_bounds_is_refused(finished: FinishedRun, tail: str) -> None:
    home, _, run_id = finished

    refused = run_cli(home, "run", "logs", run_id, "--tail", tail)

    assert refused.exit_code == EXIT_USAGE
    assert refused.envelope()["error"]["details"]["maximum"] == 5000


def test_the_default_tail_is_two_hundred(
    finished: FinishedRun,
) -> None:
    home, paths, run_id = finished
    _append(paths, run_id, "".join(f"many {number}\n" for number in range(400)))

    payload = run_cli(home, "run", "logs", run_id).data()

    assert len(payload["lines"]) == 200
    assert payload["truncated"] is True


# ---------------------------------------------------------------------------
# Scrubbing
# ---------------------------------------------------------------------------


def test_a_bearer_token_never_reaches_the_reader(
    finished: FinishedRun,
) -> None:
    home, paths, run_id = finished
    _append(
        paths,
        run_id,
        "calling out\nAuthorization: Bearer sk-live-abcdefghijklmnopqrstuvwx\n",
    )

    lines = run_cli(home, "run", "logs", run_id, "--tail", "5").data()["lines"]

    joined = "\n".join(lines)
    assert "sk-live-abcdefghijklmnopqrstuvwx" not in joined
    assert "[redacted]" in joined


def test_a_quoted_json_key_never_reaches_the_reader(
    finished: FinishedRun,
) -> None:
    home, paths, run_id = finished
    _append(
        paths,
        run_id,
        '{"api_key": "sk-live-9876543210fedcba", "model_id": "development"}\n',
    )

    line = run_cli(home, "run", "logs", run_id, "--tail", "1").data()["lines"][0]

    assert "sk-live-9876543210fedcba" not in line
    assert "[redacted]" in line
    assert "development" in line


def test_the_identifiers_an_operator_needs_survive(
    finished: FinishedRun,
) -> None:
    home, paths, run_id = finished
    digest = f"sha256:{'d' * 64}"
    _append(paths, run_id, f"verified {run_id} against {digest}\n")

    line = run_cli(home, "run", "logs", run_id, "--tail", "1").data()["lines"][0]

    assert run_id in line
    assert digest in line


# ---------------------------------------------------------------------------
# Following
# ---------------------------------------------------------------------------


def test_following_is_refused_in_machine_mode(
    finished: FinishedRun,
) -> None:
    home, _, run_id = finished

    refused = run_cli(home, "run", "logs", run_id, "--follow")

    assert refused.exit_code == EXIT_USAGE
    assert refused.envelope()["error"]["code"] == "run_follow_not_supported_in_json"


def test_following_a_finished_run_returns_and_leaves_it_alone(
    finished: FinishedRun,
) -> None:
    """A follower of a run that has ended stops; it does not wait forever."""
    home, _, run_id = finished

    followed = run_cli(home, "run", "logs", run_id, "--follow", machine=False)

    assert followed.exit_code == EXIT_OK
    assert run_cli(home, "run", "status", run_id).data()["phase"] == "completed"


def test_a_log_that_does_not_exist_yet_says_so(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    paths, prepared = prepare_only(home)
    run_id = start_through_the_cli(home, prepared).data()["run_id"]
    wait_for_terminal(home, run_id)
    (paths.run_dir(run_id) / "worker.log").unlink()

    refused = run_cli(home, "run", "logs", run_id)

    assert refused.envelope()["error"]["code"] == "run_logs_unavailable"
    assert refused.envelope()["error"]["retryable"] is True
