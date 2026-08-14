"""One draft becomes one run. Spec PR8 §8.8, §8.17, §9.

A start can be retried by a person who did not see the first response, by a
host agent that timed out, or by a process that crashed halfway through its
own transaction. None of those may produce a second run: the draft is spent
once, the approval is a deliberate act, and two runs from one draft would mean
two answers to a question that was asked once.

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
from techtree.drafts.store import DraftStore
from techtree.errors import EXIT_OK
from techtree.fs import remove_tree
from techtree.ids import new_id
from techtree.paths import TechtreePaths
from techtree.runs.events import DETAIL_ACTOR, RUN_APPROVED, read_events
from techtree.runs.store import RunStore
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


def test_a_crash_before_the_claim_leaves_the_draft_startable(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    """Spec §9.2: nothing changed, so the same draft still starts the run."""
    home, paths, draft = prepared
    refused = run_cli(home, "climb", "start", draft.draft.id)

    assert refused.exit_code != EXIT_OK
    assert refused.envelope()["error"]["code"] == "policy_acceptance_required"
    assert not paths.runs_dir.exists() or _runs(paths) == []

    started = start_through_the_cli(home, draft)
    assert started.exit_code == EXIT_OK
    wait_for_terminal(home, started.data()["run_id"])


def test_a_crash_after_the_claim_repairs_the_same_run(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    """Spec §9.3: start.json holds the canonical run identifier."""
    home, paths, draft = prepared
    claimed = DraftStore(paths).claim_start(
        draft_id=draft.draft.id,
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


def test_a_machine_caller_must_name_the_policy_digest(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    """Decisions 0019 s2: nobody can be asked, so the flag has to say so."""
    home, paths, draft = prepared

    refused = run_cli(home, "climb", "start", draft.draft.id)

    assert refused.exit_code != EXIT_OK
    error = refused.envelope()["error"]
    assert error["code"] == "policy_acceptance_required"
    assert "--yes" in error["message"]
    assert error["details"]["data_policy_digest"] == draft.draft.data_policy_digest
    assert not paths.runs_dir.exists() or _runs(paths) == []


def test_a_person_approves_by_answering_yes(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    home, _, draft = prepared

    started = run_cli(
        home,
        "climb",
        "start",
        draft.draft.id,
        machine=False,
        stdin="y\n",
    )

    assert started.exit_code == EXIT_OK, started.stdout + started.stderr
    assert f"{draft.draft.estimated_episodes} episodes" in started.stdout
    assert "The Skill is the only scientific change." in started.stdout
    assert "human via cli" in started.stdout
    run_id = start_through_the_cli(home, draft).data()["run_id"]
    assert wait_for_terminal(home, run_id)["phase"] == "completed"


def test_the_surface_defaults_to_the_command_line_the_approval_was_given_on(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    """An operator at a terminal answered here, and the run says so."""
    home, paths, draft = prepared

    started = start_through_the_cli(home, draft)

    run_id = started.data()["run_id"]
    assert started.data()["policy_acknowledgement_method"] == "explicit_cli_review"
    assert started.data()["approved_by"] == "operator_via_flag"
    request = RunStore(paths).get_request(run_id)
    assert request.policy_acknowledgement.method == "explicit_cli_review"
    assert _approval_actor(paths, run_id) == "operator_via_flag"
    wait_for_terminal(home, run_id)


def test_a_declared_host_agent_review_is_what_the_run_records(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    """Decisions 0019 s2: the plugin's surface is where the person answered.

    Hermes shows the review and takes the confirmation through its own
    dispatch gate; this command only writes the record. A run that described
    that as a command-line acceptance would misdescribe who was asked and
    where.
    """
    home, paths, draft = prepared

    started = run_cli(
        home,
        "climb",
        "start",
        draft.draft.id,
        "--yes",
        "--reviewed-on",
        "host-agent",
    )

    assert started.exit_code == EXIT_OK, started.stdout + started.stderr
    run_id = started.data()["run_id"]
    assert started.data()["policy_acknowledgement_method"] == "host_agent_confirmation"
    assert started.data()["approved_by"] == "human_via_hermes"
    request = RunStore(paths).get_request(run_id)
    assert request.policy_acknowledgement.method == "host_agent_confirmation"
    assert request.policy_acknowledgement.data_policy_digest == (
        draft.draft.data_policy_digest
    )
    assert _approval_actor(paths, run_id) == "human_via_hermes"
    wait_for_terminal(home, run_id)


def test_declaring_a_surface_without_approving_starts_nothing(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    """The answer is about to be given here, so it was not given elsewhere."""
    home, paths, draft = prepared

    refused = run_cli(
        home, "climb", "start", draft.draft.id, "--reviewed-on", "host-agent"
    )

    assert refused.exit_code != EXIT_OK
    assert refused.envelope()["error"]["code"] == "review_surface_not_approved"
    assert not paths.runs_dir.exists() or _runs(paths) == []


def _approval_actor(paths: TechtreePaths, run_id: str) -> str:
    """Return the one actor this run's approval event names."""
    approvals = [
        event
        for event in read_events(paths.run_dir(run_id) / "events.jsonl")
        if event.kind == RUN_APPROVED
    ]
    assert len(approvals) == 1
    return str(approvals[0].details[DETAIL_ACTOR])


def test_a_person_who_declines_starts_nothing(
    prepared: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    home, paths, draft = prepared

    refused = run_cli(
        home,
        "climb",
        "start",
        draft.draft.id,
        machine=False,
        stdin="n\n",
    )

    assert refused.exit_code != EXIT_OK
    assert not paths.runs_dir.exists() or _runs(paths) == []
    assert DraftStore(paths).start_record(draft.draft.id) is None
