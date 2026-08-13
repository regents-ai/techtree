"""One draft becomes one run. Spec PR8 §8.8, §8.17, §9.

A start can be retried by a person who did not see the first response, by a
host agent that timed out, or by a process that crashed halfway through its
own transaction. None of those may produce a second run: the confirmation is
one-time, the acceptance of the data policy is a deliberate act, and two runs
from one draft would mean two answers to a question that was asked once.

Every test here goes through real ``techtree`` processes, because the
duplicate-start problem is a problem *between* processes. The crash windows of
spec §9 are reproduced by stopping partway through the real transaction and
starting again.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from fixtures.runs.support import (
    prepare_only,
    run_cli,
    start_through_the_cli,
    wait_for_terminal,
)
from techtree.drafts.confirmation import ConfirmationService
from techtree.drafts.store import DraftStore
from techtree.errors import EXIT_OK
from techtree.fs import remove_tree
from techtree.ids import new_id
from techtree.paths import TechtreePaths
from techtree.skills.service import PreparedDraft

pytestmark = pytest.mark.integration


@pytest.fixture
def prepared(tmp_path: Path) -> tuple[Path, TechtreePaths, PreparedDraft]:
    """Return a home holding one prepared, unstarted draft."""
    home = tmp_path / "home"
    home.mkdir()
    paths, draft = prepare_only(home)
    return home, paths, draft


def _runs(paths: TechtreePaths) -> list[Path]:
    return sorted(path for path in paths.runs_dir.iterdir() if path.is_dir())


# ---------------------------------------------------------------------------
# Repeating a start
# ---------------------------------------------------------------------------


def test_starting_twice_returns_the_same_run(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    home, paths, draft = prepared

    first = start_through_the_cli(home, draft)
    second = start_through_the_cli(home, draft)

    assert first.exit_code == EXIT_OK
    assert second.exit_code == EXIT_OK
    assert second.data()["run_id"] == first.data()["run_id"]
    assert len(_runs(paths)) == 1
    wait_for_terminal(home, first.data()["run_id"])


def test_two_starts_at_once_still_produce_one_run(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    """The draft lock decides, and it decides once."""
    home, paths, draft = prepared

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: start_through_the_cli(home, draft), range(2)))

    succeeded = [result for result in results if result.exit_code == EXIT_OK]
    assert succeeded, [result.stdout + result.stderr for result in results]
    identifiers = {result.data()["run_id"] for result in succeeded}
    assert len(identifiers) == 1
    assert len(_runs(paths)) == 1
    wait_for_terminal(home, identifiers.pop())


def test_a_finished_run_is_returned_rather_than_restarted(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    home, paths, draft = prepared
    run_id = start_through_the_cli(home, draft).data()["run_id"]
    wait_for_terminal(home, run_id)
    report = run_cli(home, "run", "result", run_id).data()

    again = start_through_the_cli(home, draft)

    assert again.exit_code == EXIT_OK
    assert again.data()["run_id"] == run_id
    assert again.data()["phase"] == "completed"
    assert len(_runs(paths)) == 1
    assert run_cli(home, "run", "result", run_id).data() == report


# ---------------------------------------------------------------------------
# The crash windows of spec §9
# ---------------------------------------------------------------------------


def test_a_crash_before_the_claim_leaves_the_token_usable(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    """Spec §9.2: nothing changed, so the same token still starts the run."""
    home, paths, draft = prepared
    refused = run_cli(
        home,
        "climb",
        "start",
        draft.draft.id,
        "--confirmation-token",
        draft.confirmation_token,
        "--accept-data-policy",
        f"sha256:{'0' * 64}",
    )

    assert refused.exit_code != EXIT_OK
    assert refused.envelope()["error"]["code"] == "policy_acceptance_digest_mismatch"
    assert not paths.runs_dir.exists() or _runs(paths) == []

    started = start_through_the_cli(home, draft)
    assert started.exit_code == EXIT_OK
    wait_for_terminal(home, started.data()["run_id"])


def test_a_crash_after_the_claim_repairs_the_same_run(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    """Spec §9.3: start.json holds the canonical run identifier."""
    home, paths, draft = prepared
    claimed = DraftStore(paths, ConfirmationService()).claim_start(
        draft_id=draft.draft.id,
        token=draft.confirmation_token,
        run_id=new_id("run"),
    )
    assert _runs(paths) == [] if paths.runs_dir.exists() else True

    started = start_through_the_cli(home, draft)

    assert started.exit_code == EXIT_OK, started.stdout + started.stderr
    assert started.data()["run_id"] == claimed.run_id
    assert len(_runs(paths)) == 1
    assert wait_for_terminal(home, claimed.run_id)["phase"] == "completed"


def test_a_crash_after_the_run_was_created_finishes_the_start(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    """Spec §9.4: staging and launching are repaired, not repeated."""
    home, paths, draft = prepared
    run_id = start_through_the_cli(home, draft).data()["run_id"]
    wait_for_terminal(home, run_id)
    remove_tree(paths.run_dir(run_id) / "inputs")

    again = start_through_the_cli(home, draft)

    assert again.exit_code == EXIT_OK
    assert again.data()["run_id"] == run_id
    assert (paths.run_dir(run_id) / "inputs" / "draft.json").exists()
    assert len(_runs(paths)) == 1


# ---------------------------------------------------------------------------
# What a start refuses
# ---------------------------------------------------------------------------


def test_a_wrong_token_starts_nothing(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    home, paths, draft = prepared

    refused = run_cli(
        home,
        "climb",
        "start",
        draft.draft.id,
        "--confirmation-token",
        "not-the-token-that-was-issued",
        "--accept-data-policy",
        draft.draft.data_policy_digest,
    )

    assert refused.exit_code != EXIT_OK
    assert refused.envelope()["error"]["code"] == "confirmation_token_invalid"
    assert not paths.runs_dir.exists() or _runs(paths) == []


def test_a_machine_caller_must_name_the_policy_digest(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    """Spec §10.3: holding the token has never implied accepting the policy."""
    home, paths, draft = prepared

    refused = run_cli(
        home,
        "climb",
        "start",
        draft.draft.id,
        "--confirmation-token",
        draft.confirmation_token,
    )

    assert refused.exit_code != EXIT_OK
    error = refused.envelope()["error"]
    assert error["code"] == "policy_acceptance_required"
    assert error["details"]["data_policy_digest"] == draft.draft.data_policy_digest
    assert not paths.runs_dir.exists() or _runs(paths) == []


def test_a_person_accepts_by_answering_yes(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    home, _, draft = prepared

    started = run_cli(
        home,
        "climb",
        "start",
        draft.draft.id,
        "--confirmation-token",
        draft.confirmation_token,
        machine=False,
        stdin="y\n",
    )

    assert started.exit_code == EXIT_OK, started.stdout + started.stderr
    assert draft.draft.data_policy_digest in started.stdout
    assert "interactive cli" in started.stdout
    run_id = run_cli(
        home,
        "climb",
        "start",
        draft.draft.id,
        "--confirmation-token",
        draft.confirmation_token,
        "--accept-data-policy",
        draft.draft.data_policy_digest,
    ).data()["run_id"]
    assert wait_for_terminal(home, run_id)["phase"] == "completed"


def test_a_person_who_declines_starts_nothing(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    home, paths, draft = prepared

    refused = run_cli(
        home,
        "climb",
        "start",
        draft.draft.id,
        "--confirmation-token",
        draft.confirmation_token,
        machine=False,
        stdin="n\n",
    )

    assert refused.exit_code != EXIT_OK
    assert not paths.runs_dir.exists() or _runs(paths) == []
    assert DraftStore(paths, ConfirmationService()).start_record(draft.draft.id) is None
