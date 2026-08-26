"""The whole development loop, in real processes. Spec PR8 §8.17, §13.

This file is the definition of done for PR6 through PR8, executed rather than
asserted: a real draft is prepared against the injected complete catalog, a
real ``techtree climb start`` subprocess starts it, a real detached worker runs
it, and separate ``run status`` and ``run result`` subprocesses read the answer
back. Nothing here shares memory with the thing it is testing.

Every claim in spec §13's checklist is one test below, including the ones that
are about what did *not* happen: no model was called, no Docker subject
started, no Verifiers evaluation ran, and the report cannot be published.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fixtures.runs.support import (
    prepare_only,
    run_cli,
    start_through_the_cli,
    wait_for_terminal,
)
from techtree.canonical import digest_object
from techtree.errors import EXIT_OK
from techtree.fs import remove_tree
from techtree.models.experiment import ExperimentVariant
from techtree.models.uplift_report import UpliftReport
from techtree.paths import TechtreePaths
from techtree.runs.artifacts import RunArtifactStore
from techtree.runs.events import (
    DETAIL_ACTOR,
    DETAIL_APPROVED_AT,
    DETAIL_DRAFT_DIGEST,
    RUN_APPROVED,
    read_events,
)
from techtree.runs.machine import reduce_events
from techtree.runs.store import RunStore

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def finished_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Run the whole loop once, and let every test read the same answer.

    One end-to-end pass costs several subprocesses. The properties below are
    all properties of the same finished run, so they are established once and
    inspected many times rather than re-run per assertion.
    """
    home = tmp_path_factory.mktemp("techtree-home")
    paths, prepared = prepare_only(home)

    started = start_through_the_cli(home, prepared)
    assert started.exit_code == EXIT_OK, started.stdout + started.stderr
    run_id = started.data()["run_id"]

    final = wait_for_terminal(home, run_id)
    result = run_cli(home, "run", "result", run_id)

    return {
        "home": home,
        "paths": paths,
        "draft": prepared.draft,
        "run_id": run_id,
        "started": started,
        "status": final,
        "result": result,
    }


def _report(finished_run: dict[str, Any]) -> UpliftReport:
    # Protocol documents are loaded from bytes, never from a decoded dict: it
    # is the JSON spelling the strict models accept, and it is what a real
    # reader of this envelope would have. ``run result`` returns the report
    # together with the neutral presentation payload every channel draws from
    # (spec section 7.21), so the report is one field of the response.
    return UpliftReport.model_validate_json(
        json.dumps(finished_run["result"].data()["report"])
    )


def _paths(finished_run: dict[str, Any]) -> TechtreePaths:
    paths: TechtreePaths = finished_run["paths"]
    return paths


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


def test_starting_returns_promptly_with_a_run_to_watch(
    finished_run: dict[str, Any],
) -> None:
    payload = finished_run["started"].data()

    assert payload["run_id"].startswith("run_")
    assert payload["phase"] == "created"
    assert payload["worker_pid"] is not None
    assert payload["policy_acknowledgement_method"] == "explicit_cli_review"
    assert payload["approved_by"] == "operator_via_flag"
    assert payload["campaign_spec_digest"] == finished_run["draft"].campaign_spec_digest
    assert payload["data_policy_digest"] == finished_run["draft"].data_policy_digest


def test_the_run_completes(finished_run: dict[str, Any]) -> None:
    assert finished_run["status"]["phase"] == "completed"
    assert finished_run["status"]["result_available"] is True
    assert finished_run["result"].exit_code == EXIT_OK


def test_watching_is_refused_in_machine_mode(finished_run: dict[str, Any]) -> None:
    """Spec §8.12: one envelope per invocation, so nothing may print twice."""
    refused = run_cli(
        finished_run["home"], "run", "status", finished_run["run_id"], "--watch"
    )

    assert refused.exit_code != EXIT_OK
    assert refused.envelope()["error"]["code"] == "run_watch_not_supported_in_json"


def test_the_journal_reconstructs_the_state(finished_run: dict[str, Any]) -> None:
    run_id = finished_run["run_id"]
    events = read_events(_paths(finished_run).run_dir(run_id) / "events.jsonl")

    rebuilt = reduce_events(events)

    assert [event.sequence for event in events] == list(range(len(events)))
    assert rebuilt.phase.value == "completed"
    assert rebuilt.result_digest == digest_object(_report(finished_run))


def test_one_receipt_per_campaign_task_and_variant(
    finished_run: dict[str, Any],
) -> None:
    paths = _paths(finished_run)
    run_id = finished_run["run_id"]
    artifacts = RunArtifactStore(paths)
    request = RunStore(paths).get_request(run_id)
    hashes = artifacts.load_inputs(run_id, request).ordered_task_hashes

    for variant in ExperimentVariant:
        receipts = artifacts.episode_receipts(run_id, variant)
        assert [receipt.task_hash for receipt in receipts] == hashes


def test_the_comparison_remains_controlled(finished_run: dict[str, Any]) -> None:
    report = _report(finished_run)

    assert report.manifest_comparison.controlled is True
    assert report.manifest_comparison.violations == []
    assert [
        difference.pointer for difference in report.manifest_comparison.differences
    ] == ["/agents/subject/harness/skills/0"]


def test_the_report_carries_the_whole_lineage(finished_run: dict[str, Any]) -> None:
    paths = _paths(finished_run)
    run_id = finished_run["run_id"]
    request = RunStore(paths).get_request(run_id)
    inputs = RunArtifactStore(paths).load_inputs(run_id, request)
    report = _report(finished_run)

    assert report.campaign_spec_digest == inputs.source.campaign_digest
    assert report.data_policy_digest == inputs.source.data_policy_digest
    assert report.public_context is not None
    assert report.public_context.climb_digest == inputs.source.climb_digest
    assert report.evaluation_backend == inputs.campaign.evaluation_backend
    assert report.taskset_validation_receipt_digest == (
        inputs.source.publisher_validation_digest
    )


# ---------------------------------------------------------------------------
# What a development-only report may not claim
# ---------------------------------------------------------------------------


def test_the_report_is_development_only_and_cannot_be_published(
    finished_run: dict[str, Any],
) -> None:
    report = _report(finished_run)

    assert report.proof_grade == "development_only"
    assert report.decision.value == "development_only"
    assert report.publication_eligible is False
    assert report.statuses.publication.value == "blocked"
    assert report.statuses.score.value == "development_only"
    assert report.statuses.evidence.value == "development_only"
    assert report.statuses.comparison.value == "development_only"


def test_starting_a_fake_run_says_no_model_is_called(
    finished_run: dict[str, Any],
) -> None:
    """The other side of ticket ce9: here the executor really is the fake one.

    The start surface reads the run's own executor, so the sentence about
    model calls follows the run rather than a literal, and this catalog is
    where it is true.
    """
    envelope = finished_run["started"].envelope()
    warnings = {warning["code"]: warning["text"] for warning in envelope["warnings"]}

    assert finished_run["started"].data()["fake_executor"] is True
    assert "development_only_run" in warnings
    assert "no model is called" in warnings["development_only_run"]
    assert "spends money" not in " ".join(warnings.values())


def test_the_machine_envelope_carries_the_caveat(
    finished_run: dict[str, Any],
) -> None:
    """A host agent reading JSON is the caller most likely to over-read this."""
    warnings = finished_run["result"].envelope()["warnings"]

    assert any(warning["code"] == "development_only_result" for warning in warnings)


def test_the_human_result_leads_with_the_banner(
    finished_run: dict[str, Any],
) -> None:
    result = run_cli(
        finished_run["home"],
        "run",
        "result",
        finished_run["run_id"],
        machine=False,
    )

    lines = result.stdout.splitlines()
    assert lines[0] == "DEVELOPMENT-ONLY FAKE RESULT"
    assert "No agent was evaluated." in lines
    assert "No model was called." in lines
    assert "This report is not publication eligible." in lines


def test_no_subject_ran_anywhere(finished_run: dict[str, Any]) -> None:
    """No model was called, no Docker subject started, no evaluation ran."""
    paths = _paths(finished_run)
    run_id = finished_run["run_id"]
    artifacts = RunArtifactStore(paths)
    request = RunStore(paths).get_request(run_id)

    for variant in ExperimentVariant:
        for receipt in artifacts.episode_receipts(run_id, variant):
            assert receipt.execution_backend == "fake"
            assert receipt.subject_runtime.kind == "not_executed"
            assert receipt.subject_runtime.resolved_image_digest is None
    assert request.executor_kind == "fake"


def test_the_run_records_that_it_was_approved(
    finished_run: dict[str, Any],
) -> None:
    """Decisions 0019 s2: one ordinary event, naming the draft and the actor."""
    paths = _paths(finished_run)
    events = read_events(paths.run_dir(finished_run["run_id"]) / "events.jsonl")

    approvals = [event for event in events if event.kind == RUN_APPROVED]

    assert len(approvals) == 1
    details = approvals[0].details
    assert details[DETAIL_ACTOR] == "operator_via_flag"
    assert details[DETAIL_DRAFT_DIGEST] == digest_object(finished_run["draft"])
    assert details[DETAIL_APPROVED_AT]


# ---------------------------------------------------------------------------
# Independence
# ---------------------------------------------------------------------------


def test_the_source_skill_and_the_draft_may_be_deleted(
    tmp_path: Path,
) -> None:
    """Spec §13: deleting the draft's source skill does not affect the run."""
    home = tmp_path / "home"
    home.mkdir()
    source = tmp_path / "candidate"
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "skills"
    source.mkdir()
    for item in sorted((fixture / "valid-procedure").rglob("*")):
        target = source / item.relative_to(fixture / "valid-procedure")
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item.read_bytes())

    paths, prepared = prepare_only(home, skill_path=source)
    started = start_through_the_cli(home, prepared)
    run_id = started.data()["run_id"]

    remove_tree(source)
    remove_tree(paths.drafts_dir)

    final = wait_for_terminal(home, run_id)
    result = run_cli(home, "run", "result", run_id)

    assert final["phase"] == "completed"
    assert result.exit_code == EXIT_OK
    assert json.loads(result.stdout)["data"]["report"]["run_id"] == run_id
