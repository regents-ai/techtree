"""The whole product, one command at a time. Spec section 29.

Spec section 29 lists the commands a person types to go from a fresh machine to
a finished report. This module types them, in that order, as real subprocesses
against a temporary Techtree home and the catalog this build actually ships. No
catalog fixture is injected, no service is constructed in-process, and no
provider is substituted: what is exercised is the installed program.

That makes it the one place where every work package is loaded at once. Setup
installs the pinned engine (WP4). List and show read the generated catalog
(WP1, PR4B). Prepare scans a real skill and builds the two manifests (WP2).
Start launches a detached worker (WP3). Status and logs read the answer back.

The sequence stops where it now costs money. Decisions document 0025 put the
release subject into the shipped Campaign, so starting the Hello World Climb
asks for a real evaluation: real containers, a real provider, a real bill. This
module therefore hands ``start`` an environment with no evaluation credential
in it — which is also the first-run environment of everybody who has not signed
in yet — and requires the product to stop there with a stated reason instead of
provisioning anything. The complete journey past that point is a paid run and
is certification evidence, not a test.

The development loop that used to be observed here, all the way to a report,
is observed in full by ``test_fake_run.py`` against the synthetic development
catalog, which is where a fake executor belongs.

    uv run pytest tests/integration/test_cli_flow.py -m integration
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest
from typer.testing import CliRunner

import techtree
from fixtures.drafts.support import VALID_SKILL
from fixtures.runs.support import run_cli, wait_for_terminal
from fixtures.starter import STARTER_FIXTURE, release_pinning, tree_digest
from techtree.cli.app import create_app
from techtree.cli.commands.climb import abbreviated_digest
from techtree.constants import STARTER_SKILL_CANDIDATE_LABEL, STARTER_SKILL_NAME
from techtree.errors import EXIT_OK
from techtree.identity.store import IdentityStore
from techtree.models.campaign import CampaignSpec
from techtree.paths import paths_from_root
from techtree.release.document import render_release_core
from techtree.runs.artifacts import RunArtifactStore
from techtree.runs.events import read_events
from techtree.runs.store import RunStore
from techtree.tasksets.service import LOCK_FILENAME, TASKSET_DIRECTORY
from techtree.verifiers.credentials import PRIME_CREDENTIAL_ENV

pytestmark = pytest.mark.integration

CLIMB_REFERENCE: Final = "hello-world-climb"
CLIMB_LISTING_REFERENCE: Final = "hello-world-climb@1"
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

    # The detached worker inherits this environment, and the Campaign it is
    # about to run names a real subject. A machine that happens to be signed in
    # to the provider would spend money here, so the worker is given a HOME
    # with no provider configuration under it; ``run_cli`` drops the credential
    # variable on every call already.
    started = run_cli(
        home,
        "climb",
        "start",
        draft["draft_id"],
        "--yes",
        environment={"HOME": str(tmp_path_factory.mktemp("signed-out"))},
    )
    assert started.exit_code == EXIT_OK, started.stdout + started.stderr
    run_id = started.data()["run_id"]

    final = wait_for_terminal(home, run_id, timeout=900.0)
    logs = run_cli(home, "run", "logs", run_id, "--tail", "200")

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
    }


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
    assert "Datarights" in unwrapped
    # Decisions 0007 R3: the person gets the summary and shortened IDs, the
    # machine payload gets both digests complete.
    assert payload["data_policy_digest"] == flow["draft"]["data_policy_digest"]
    assert "TechnicalIDs" in unwrapped
    assert abbreviated_digest(payload["climb"]["campaign_spec_digest"]) in unwrapped
    assert abbreviated_digest(payload["data_policy_digest"]) in unwrapped
    assert payload["climb"]["campaign_spec_digest"] not in unwrapped
    # The complete DataPolicy digest is what `prepare` shows and `start`
    # demands back, and that has not changed.
    assert flow["draft"]["data_policy_digest"].startswith("sha256:")


def _shipped_campaign() -> CampaignSpec:
    """Return the Campaign this build ships, read from the catalog it ships in."""
    document = (
        Path(techtree.__file__).parent
        / "resources"
        / "catalog"
        / "campaigns"
        / "hello-world-climb.json"
    )
    return CampaignSpec.model_validate_json(document.read_text(encoding="utf-8"))


def test_prepare_builds_a_draft_from_a_real_skill(flow: dict[str, Any]) -> None:
    draft = flow["draft"]

    assert draft["draft_id"].startswith("draft_")
    assert draft["candidate_label"] == "branch-code"
    assert draft["baseline_skill_count"] == 0
    assert draft["candidate_skill_count"] == 1
    assert draft["estimated_episodes"] == EXPECTED_TASK_COUNT * 2
    # Ticket 8vj: the most the shipped Campaign declares it may cost travels
    # with the draft, so a review surface that is not this terminal can print
    # the same figure this terminal prints instead of inventing one.
    assert draft["campaign_maximum_usd"] == _shipped_campaign().budgets.maximum_usd
    assert draft["campaign_maximum_usd"] is not None


def test_start_records_the_approval_and_who_gave_it(flow: dict[str, Any]) -> None:
    """Decisions 0019 s2: the review was accepted, and by an operator here."""
    payload = flow["started"].data()

    assert payload["policy_acknowledgement_method"] == "explicit_cli_review"
    assert payload["approved_by"] == "operator_via_flag"
    assert payload["data_policy_digest"] == flow["draft"]["data_policy_digest"]


def test_start_says_a_real_evaluation_is_what_was_approved(
    flow: dict[str, Any],
) -> None:
    """Decisions document 0025: the shipped Climb runs the release subject.

    The request written at approval time is where a person is told what is
    about to happen, and since the Campaign carries real release coordinates
    what is about to happen is a real evaluation. The old answer here was the
    development executor, and that was only ever true because the Campaign
    named a placeholder.
    """
    paths = paths_from_root(flow["home"])
    run_id = flow["run_id"]
    request = RunStore(paths).get_request(run_id)
    inputs = RunArtifactStore(paths).load_inputs(run_id, request)

    assert request.executor_kind == "verifiers"
    assert inputs.campaign.subject.model.provider == "prime"
    assert inputs.campaign.budgets.maximum_usd is not None


def test_start_tells_the_person_what_this_run_actually_does(
    flow: dict[str, Any],
) -> None:
    """Ticket ce9: the warning at the spending moment is read off the run.

    This is the seam where it can be checked without spending anything. The
    warnings are rendered before the worker resolves a credential, so a start
    in a signed-out home still produces the sentences a person reads before
    they agree — and under the shipped Campaign those are "this spends model
    tokens" and "this Climb's report is still not publication eligible", which
    are two separate facts. A literal here used to say the opposite of the
    first one.
    """
    envelope = flow["started"].envelope()
    codes = [warning["code"] for warning in envelope["warnings"]]
    text = " ".join(warning["text"] for warning in envelope["warnings"])

    assert flow["started"].data()["fake_executor"] is False
    assert codes == ["paid_evaluation_run", "not_publication_eligible"]
    assert "spends model tokens on inference with prime" in text
    assert (
        "If that provider charges for tokens, what you pay is whatever it "
        "charges" in text
    )
    assert "not publication eligible" in text
    assert "no model" not in text.lower()
    assert "fake" not in text.lower()


def test_the_run_stops_because_nothing_can_pay_for_it(flow: dict[str, Any]) -> None:
    """Spec section 6.9: no credential, no run — and said before anything starts.

    The credential is checked before the taskset is validated, before an image
    is looked for, and before a container exists, because every one of those is
    slower and none of them can succeed without it.
    """
    assert flow["status"]["phase"] == "failed"
    assert flow["status"]["error"]["code"] == "model_credentials_missing"
    assert flow["status"]["result_available"] is False


def test_the_refusal_is_a_stated_reason_rather_than_a_crash(
    flow: dict[str, Any],
) -> None:
    """The person is told which variable, where it is looked for, and what to do."""
    status = flow["status"]
    lines = flow["logs"].data()["lines"]

    assert PRIME_CREDENTIAL_ENV in status["error"]["message"]
    assert any(flow["run_id"] in line for line in lines)
    assert any("model_credentials_missing" in line for line in lines)


def test_nothing_was_provisioned_and_nothing_was_scored(
    flow: dict[str, Any],
) -> None:
    """A refused run leaves no taskset lock, no receipts, and no report."""
    paths = paths_from_root(flow["home"])
    run_dir = paths.run_dir(flow["run_id"])

    assert not (run_dir / TASKSET_DIRECTORY / LOCK_FILENAME).exists()
    assert not (run_dir / "receipts").exists()
    assert not (run_dir / "result").exists()


def test_the_run_walked_the_phases_it_got_to(flow: dict[str, Any]) -> None:
    paths = paths_from_root(flow["home"])
    events = read_events(paths.run_dir(flow["run_id"]) / "events.jsonl")

    phases = [event.phase.value for event in events]
    assert phases[-1] == "failed"
    for never_reached in ("running_baseline", "running_candidate", "completed"):
        assert never_reached not in phases


def test_the_flow_left_the_home_it_was_given(flow: dict[str, Any]) -> None:
    """Nothing in the sequence wrote outside the temporary home."""
    home: Path = flow["home"]
    paths = paths_from_root(home)

    assert paths.engines_dir.is_dir()
    assert paths.runs_dir.is_dir()
    assert paths.config_file.is_file()


# ---------------------------------------------------------------------------
# The guided first run, followed exactly as printed
# ---------------------------------------------------------------------------


def test_the_starter_skills_printed_next_step_runs_verbatim(
    flow: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decisions 0010 item 5, against the engine and catalog this build ships.

    ``skill starter`` prints the command to prepare what it just obtained. A
    person following the guided first run types that command, so it either
    works exactly as printed or the journey stops there. Here it is taken from
    the machine envelope and executed as a real subprocess, argument for
    argument, with nothing rewritten.

    Only the release document is substituted, so that the Skill named on the
    command line is the fixture Skill rather than the released one: what is
    under test is the command, not the contents of this release.
    """
    home: Path = flow["home"]
    document = render_release_core(release_pinning(tree_digest(STARTER_FIXTURE)))
    monkeypatch.setattr(
        "techtree.cli.commands.skill.packaged_release_core_bytes", lambda: document
    )

    obtained = CliRunner().invoke(
        create_app(),
        [
            "--home",
            str(home),
            "--json",
            "skill",
            "starter",
            "--from-file",
            str(STARTER_FIXTURE),
        ],
    )
    assert obtained.exit_code == EXIT_OK, obtained.stdout
    envelope = json.loads(obtained.stdout.splitlines()[-1])
    argv: list[str] = envelope["next_actions"][0]["cli"]

    assert argv[0] == "techtree"
    assert CLIMB_LISTING_REFERENCE in argv

    prepared = run_cli(home, *argv[1:])

    assert prepared.exit_code == EXIT_OK, prepared.stdout + prepared.stderr
    draft = prepared.data()
    assert draft["candidate_label"] == STARTER_SKILL_CANDIDATE_LABEL
    assert draft["climb_reference"] == CLIMB_LISTING_REFERENCE
    assert draft["skill_root_digest"] == envelope["data"]["skill_root_digest"]


def test_the_starter_skills_own_name_is_still_a_label_a_candidate_may_carry(
    flow: dict[str, Any],
) -> None:
    """The frontmatter name stays valid even though it is not the label used.

    Decisions 0010 item 5 files the starter candidate under a shorter label
    than the Skill's own name. That is a choice, not a workaround for a name
    the product would refuse, and this is the difference.
    """
    prepared = run_cli(
        flow["home"],
        "climb",
        "prepare",
        CLIMB_LISTING_REFERENCE,
        "--skill",
        str(STARTER_FIXTURE),
        "--label",
        STARTER_SKILL_NAME,
    )

    assert prepared.exit_code == EXIT_OK, prepared.stdout + prepared.stderr
    assert prepared.data()["candidate_label"] == STARTER_SKILL_NAME
