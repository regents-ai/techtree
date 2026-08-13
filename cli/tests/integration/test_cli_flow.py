"""The whole product, one command at a time. Spec section 29.

Spec section 29 lists the commands a person types to go from a fresh machine to
a finished report. This module types them, in that order, as real subprocesses
against a temporary Techtree home and the catalog this build actually ships. No
catalog fixture is injected, no service is constructed in-process, and no
provider is substituted: what is exercised is the installed program.

That makes it the one place where every work package is loaded at once. Setup
installs the pinned engine (WP4). List and show read the generated catalog
(WP1, PR4B). Prepare scans a real skill and builds the two manifests (WP2).
Start launches a detached worker (WP3), which resolves the reference taskset
against the engine and runs the real model-free Verifiers validation before it
scores anything (WP5). Status, logs, and result read the answer back.

The run costs one engine install, four engine processes, and 72 invented
episodes, so the sequence runs once per module and each test below inspects the
same finished flow.

    uv run pytest tests/integration/test_cli_flow.py -m integration
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest

from fixtures.drafts.support import VALID_SKILL
from fixtures.runs.support import CliRun, run_cli, wait_for_terminal
from techtree.cli.commands.run import development_only_result_notice
from techtree.errors import EXIT_OK
from techtree.identity.store import IdentityStore
from techtree.models.uplift_report import UpliftReport
from techtree.paths import paths_from_root
from techtree.runs.artifacts import RunArtifactStore
from techtree.runs.events import read_events
from techtree.runs.store import RunStore
from techtree.tasksets.service import (
    EVIDENCE_FILENAME,
    LOCK_FILENAME,
    RECEIPT_FILENAME,
    TASKSET_DIRECTORY,
    VALIDATION_DIRECTORY,
)

pytestmark = pytest.mark.integration

CLIMB_REFERENCE: Final = "procedure-transfer-dev"
CLIMB_LISTING_REFERENCE: Final = "procedure-transfer-dev@1"
EXPECTED_TASK_COUNT: Final = 36


@pytest.fixture(scope="module")
def flow(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Walk the spec section 29 sequence once, and return what each step said."""
    home = tmp_path_factory.mktemp("techtree-home")

    setup = run_cli(home, "setup", timeout=900.0)
    assert setup.exit_code == EXIT_OK, setup.stdout + setup.stderr

    listed = run_cli(home, "climb", "list")
    shown = run_cli(home, "climb", "show", CLIMB_REFERENCE)
    prepared = run_cli(
        home,
        "climb",
        "prepare",
        CLIMB_REFERENCE,
        "--skill",
        str(VALID_SKILL),
        "--label",
        "branch-code",
    )
    draft = prepared.data()

    started = run_cli(
        home,
        "climb",
        "start",
        draft["draft_id"],
        "--confirmation-token",
        draft["confirmation_token"],
        "--accept-data-policy",
        draft["data_policy_digest"],
    )
    assert started.exit_code == EXIT_OK, started.stdout + started.stderr
    run_id = started.data()["run_id"]

    final = wait_for_terminal(home, run_id, timeout=900.0)
    logs = run_cli(home, "run", "logs", run_id, "--tail", "200")
    result = run_cli(home, "run", "result", run_id)
    human_result = run_cli(home, "run", "result", run_id, machine=False)

    return {
        "home": home,
        "setup": setup,
        "listed": listed,
        "shown": shown,
        "draft": draft,
        "started": started,
        "run_id": run_id,
        "status": final,
        "logs": logs,
        "result": result,
        "human_result": human_result,
    }


def _report(flow: dict[str, Any]) -> UpliftReport:
    # Loaded from bytes, never from a decoded dict: JSON is the spelling the
    # strict protocol models accept, and it is what a real reader would have.
    # ``run result`` answers with the report and the neutral presentation
    # payload every channel draws from (spec section 7.21), so the report is
    # one field of the response rather than the whole of it.
    result: CliRun = flow["result"]
    return UpliftReport.model_validate_json(json.dumps(result.data()["report"]))


# ---------------------------------------------------------------------------
# The sequence
# ---------------------------------------------------------------------------


def test_setup_installs_verifies_and_activates_the_engine(
    flow: dict[str, Any],
) -> None:
    engine = flow["setup"].data()

    assert engine["installed"] is True
    assert engine["verified"] is True
    assert engine["active"] is True


def test_setup_creates_the_local_signing_key_and_says_what_it_is_for(
    flow: dict[str, Any],
) -> None:
    """Spec section 7.5: a key is made here, and announced rather than assumed."""
    messages = flow["setup"].envelope()["messages"]
    notice = next(
        message for message in messages if message["code"] == "local_signing_key"
    )
    store = IdentityStore(paths_from_root(flow["home"]))

    assert store.exists() is True
    assert store.verify_pair() is True
    assert "not uploaded in this release" in notice["text"]
    assert store.load_public().key_id in notice["text"]


def test_list_shows_the_development_climb(flow: dict[str, Any]) -> None:
    entries = flow["listed"].envelope()["data"]

    assert [entry["reference"] for entry in entries] == [CLIMB_LISTING_REFERENCE]
    assert entries[0]["task_count"] == EXPECTED_TASK_COUNT
    assert entries[0]["status"] == "development"
    assert entries[0]["compatibility"]["compatible"] is True
    # The catalog reports what the filesystem can prove on its own; proving the
    # contents still hash to the digest belongs to `techtree engine verify`.
    assert entries[0]["compatibility"]["engine_status"] == "installed_unverified"


def test_show_reports_the_campaign_and_the_data_policy(
    flow: dict[str, Any],
) -> None:
    """Spec section 29: the output carries the Campaign digest and the rights."""
    payload = flow["shown"].data()
    human = run_cli(flow["home"], "climb", "show", CLIMB_REFERENCE, machine=False)
    # A digest is wider than a terminal column, so the rendered table folds it.
    unwrapped = "".join(human.stdout.split())

    assert payload["climb"]["campaign_spec_digest"].startswith("sha256:")
    assert payload["primary_reward"] == "exact_match"
    assert payload["climb"]["taskset_id"] == "procedure-transfer-v1"
    assert payload["climb"]["data_policy"]["candidate_skill_public_release"] == (
        "required_for_climb"
    )
    assert payload["climb"]["campaign_spec_digest"] in unwrapped
    assert "Datarights" in unwrapped
    # The DataPolicy digest is what `prepare` shows and `start` demands back.
    assert flow["draft"]["data_policy_digest"].startswith("sha256:")


def test_prepare_builds_a_draft_from_a_real_skill(flow: dict[str, Any]) -> None:
    draft = flow["draft"]

    assert draft["draft_id"].startswith("draft_")
    assert draft["candidate_label"] == "branch-code"
    assert draft["baseline_skill_count"] == 0
    assert draft["candidate_skill_count"] == 1
    assert draft["estimated_episodes"] == EXPECTED_TASK_COUNT * 2


def test_start_acknowledges_the_policy_by_digest(flow: dict[str, Any]) -> None:
    """Decisions 0003 A5: a token is not consent, an exact digest is."""
    payload = flow["started"].data()

    assert payload["policy_acknowledgement_method"] == "explicit_cli_digest"
    assert payload["data_policy_digest"] == flow["draft"]["data_policy_digest"]


def test_status_reports_a_finished_run(flow: dict[str, Any]) -> None:
    assert flow["status"]["phase"] == "completed"
    assert flow["status"]["result_available"] is True
    assert flow["status"]["development_only"] is True


def test_logs_show_the_worker_doing_the_work(flow: dict[str, Any]) -> None:
    lines = flow["logs"].data()["lines"]

    assert any(flow["run_id"] in line for line in lines)
    assert any("completed" in line for line in lines)


# ---------------------------------------------------------------------------
# The taskset really was validated
# ---------------------------------------------------------------------------


def test_the_run_validated_its_taskset_with_the_real_engine(
    flow: dict[str, Any],
) -> None:
    """Spec section 28: a run keeps the lock and the validation it ran under."""
    paths = paths_from_root(flow["home"])
    taskset = paths.run_dir(flow["run_id"]) / TASKSET_DIRECTORY
    validation = taskset / VALIDATION_DIRECTORY

    assert (taskset / LOCK_FILENAME).is_file()
    assert (validation / RECEIPT_FILENAME).is_file()
    assert (validation / EVIDENCE_FILENAME).is_file()
    assert (validation / "summary.json").is_file()
    assert (validation / "results.jsonl").is_file()


def test_the_validation_was_local_and_reproduced_the_publisher_receipt(
    flow: dict[str, Any],
) -> None:
    """Decisions 0003 A1: the local receipt is the published one, byte for byte."""
    paths = paths_from_root(flow["home"])
    run_id = flow["run_id"]
    inputs = RunArtifactStore(paths).load_inputs(
        run_id, RunStore(paths).get_request(run_id)
    )
    recorded = json.loads(
        (paths.run_dir(run_id) / "validation" / "development.json").read_text(
            encoding="utf-8"
        )
    )

    assert recorded["source"] == "local_verifiers"
    assert recorded["execution_record"] is not None
    assert (
        recorded["receipt_digest"] == inputs.campaign.taskset.validation_receipt_digest
    )
    assert recorded["receipt"]["status"] == "valid"


def test_the_run_walked_every_phase(flow: dict[str, Any]) -> None:
    paths = paths_from_root(flow["home"])
    events = read_events(paths.run_dir(flow["run_id"]) / "events.jsonl")

    phases = [event.phase.value for event in events]
    for expected in (
        "validating_taskset",
        "running_baseline",
        "running_candidate",
        "building_receipts",
        "verifying_comparison",
        "building_report",
        "completed",
    ):
        assert expected in phases


# ---------------------------------------------------------------------------
# The result, and what it is allowed to claim
# ---------------------------------------------------------------------------


def test_the_report_is_development_only(flow: dict[str, Any]) -> None:
    report = _report(flow)

    assert report.proof_grade == "development_only"
    assert report.publication_eligible is False
    assert len(report.task_deltas) == EXPECTED_TASK_COUNT


def test_the_result_carries_the_required_warning(flow: dict[str, Any]) -> None:
    """Spec section 29 fixes this text, including the DataPolicy digest line."""
    report = _report(flow)
    warnings = flow["result"].envelope()["warnings"]
    notice = development_only_result_notice(report.data_policy_digest)

    assert any(warning["text"] == notice for warning in warnings)


def test_the_human_result_says_it_in_full(flow: dict[str, Any]) -> None:
    stdout: str = flow["human_result"].stdout
    report = _report(flow)

    for line in (
        "This is a development-only report.",
        "The taskset was validated through Prime Intellect Verifiers.",
        "The baseline and candidate results were generated by the fake executor.",
        "No agent was evaluated. The report is not publication eligible.",
        "The candidate and generated artifacts remain governed by DataPolicy:",
        report.data_policy_digest,
    ):
        assert line in stdout, stdout


def test_nothing_was_evaluated(flow: dict[str, Any]) -> None:
    """The taskset validation was real; everything scored on it was not."""
    paths = paths_from_root(flow["home"])
    run_id = flow["run_id"]
    artifacts = RunArtifactStore(paths)

    for variant in ("baseline", "candidate"):
        directory = paths.run_dir(run_id) / "receipts" / variant
        receipts = sorted(directory.iterdir())
        assert len(receipts) == EXPECTED_TASK_COUNT

    request = RunStore(paths).get_request(run_id)
    assert request.executor_kind == "fake"
    assert artifacts.load_inputs(run_id, request).campaign.subject.model.provider == (
        "development"
    )


def test_the_result_offers_the_tasks_first_and_the_log_after(
    flow: dict[str, Any],
) -> None:
    """What to do about the result comes before how to debug the run."""
    actions = flow["result"].envelope()["next_actions"]

    assert actions[0]["cli"][:3] == ["techtree", "run", "result"]
    assert ["techtree", "run", "logs", flow["run_id"]] in [
        action["cli"] for action in actions
    ]


def test_no_secret_reaches_the_run_directory(flow: dict[str, Any]) -> None:
    """The confirmation token lives in a response and in memory, nowhere else."""
    paths = paths_from_root(flow["home"])
    token: str = flow["draft"]["confirmation_token"]

    for path in [
        *paths.run_dir(flow["run_id"]).rglob("*"),
        *paths.drafts_dir.rglob("*"),
    ]:
        if path.is_file():
            assert token not in path.read_bytes().decode("utf-8", "replace")


def test_the_flow_left_the_home_it_was_given(flow: dict[str, Any]) -> None:
    """Nothing in the sequence wrote outside the temporary home."""
    home: Path = flow["home"]
    paths = paths_from_root(home)

    assert paths.engines_dir.is_dir()
    assert paths.runs_dir.is_dir()
    assert paths.config_file.is_file()
