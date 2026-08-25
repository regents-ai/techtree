"""Preparing a real draft, end to end. Spec PR6 §6.11 and spec §27.4.

This is the whole of ``techtree climb prepare`` against a real filesystem: a
temporary Techtree home, the complete synthetic catalog injected the way the
PR4A command tests inject it, and a real candidate skill directory on disk.

Four properties are what this file exists to establish, and none of them can be
shown by a unit test.

*The snapshot is a snapshot.* Editing — or deleting — the source directory
after preparing changes nothing about the draft. That is the difference between
a scientific input and a pointer at somebody's working copy.

*Nothing reaches the outside world.* Sockets are made unusable and process
creation is made to fail for the duration of a prepare. If preparation ever
grows a network call or a subprocess, this test stops passing.

*A refusal leaves nothing behind.* A skill holding a credential, or a symlink,
is refused, and the drafts directory afterwards holds no draft and no staging
leftovers.

*Both output modes carry the whole story.* The machine envelope and the human
rendering each have to show everything spec PR6 §6.9 lists, including the
rights summary and the development-only caveat.
"""

from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from fixtures.drafts.support import (
    COMPLETE_CATALOG,
    SKILL_FIXTURES,
    VALID_SKILL,
    catalog_service,
    preparation_service,
    prepare_draft,
)
from techtree.canonical import digest_object
from techtree.cli.app import create_app
from techtree.drafts.store import DraftStore
from techtree.errors import EXIT_OK, EXIT_VALIDATION, PolicyError, ValidationError
from techtree.manifests.builder import SKILL_MEDIA_TYPE
from techtree.models.campaign import SKILL_MUTATION_POINTER
from techtree.models.catalog import EngineCompatibilityStatus
from techtree.paths import paths_from_root
from techtree.skills.service import PreparedDraft

pytestmark = pytest.mark.integration

INVALID_SECRET = SKILL_FIXTURES / "invalid-secret"
INVALID_SYMLINK = SKILL_FIXTURES / "invalid-symlink"


@pytest.fixture
def prepared(temp_techtree_home: Path) -> tuple[DraftStore, PreparedDraft, Path]:
    """Prepare one draft from the fixture skill in an isolated home."""
    store, draft, paths = prepare_draft(temp_techtree_home)
    return store, draft, paths.drafts_dir


def assert_no_draft(drafts_dir: Path) -> None:
    """Require that a refusal left neither a draft nor a staging directory."""
    if not drafts_dir.exists():
        return
    assert list(drafts_dir.iterdir()) == []


def copy_skill(source: Path, destination: Path) -> Path:
    """Copy a skill fixture so a test can edit its own copy."""
    for item in sorted(source.rglob("*")):
        target = destination / item.relative_to(source)
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item.read_bytes())
    return destination


# ---------------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------------


def test_preparing_produces_a_complete_verifiable_draft(
    prepared: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, draft, _ = prepared

    snapshot = store.load_snapshot(draft.draft.id)

    assert snapshot.draft.id == draft.draft.id
    assert digest_object(snapshot.draft) == draft.draft_digest
    assert snapshot.comparison.controlled


def test_the_two_variants_carry_zero_and_one_skill(
    prepared: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, draft, _ = prepared
    baseline, candidate = store.get_manifests(draft.draft.id)

    assert baseline.configuration.agents["subject"].harness.skills == []
    inserted = candidate.configuration.agents["subject"].harness.skills
    assert len(inserted) == 1
    assert inserted[0].digest == draft.draft.skill_artifact.root_digest
    assert inserted[0].media_type == SKILL_MEDIA_TYPE


def test_both_variants_share_the_campaign_policy_and_backend(
    prepared: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, draft, _ = prepared
    baseline, candidate = store.get_manifests(draft.draft.id)
    resolved = store.get_source(draft.draft.id)

    assert baseline.campaign_spec_digest == candidate.campaign_spec_digest
    assert baseline.campaign_spec_digest == resolved.campaign_digest
    assert (
        baseline.configuration.data_policy_digest
        == candidate.configuration.data_policy_digest
        == resolved.data_policy_digest
    )
    assert (
        baseline.configuration.evaluation_backend
        == candidate.configuration.evaluation_backend
    )
    assert baseline.public_context is not None
    assert baseline.public_context.climb_digest == resolved.climb_digest
    assert candidate.public_context == baseline.public_context


def test_the_only_difference_is_the_inserted_skill(
    prepared: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    _, draft, _ = prepared
    comparison = draft.manifest_comparison

    assert comparison.controlled
    assert comparison.allowed_differences == [SKILL_MUTATION_POINTER]
    assert [item.pointer for item in comparison.differences] == [
        f"{SKILL_MUTATION_POINTER}/0"
    ]


def test_the_draft_states_the_rights_that_have_to_be_accepted(
    prepared: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    """Decisions 0003 A5: the draft states the requirement, not the acceptance."""
    store, draft, _ = prepared
    acceptance = draft.draft.policy_acceptance
    resolved = store.get_source(draft.draft.id)

    assert acceptance.required is True
    assert acceptance.data_policy_digest == resolved.data_policy_digest
    assert "You own the candidate skill" in acceptance.summary
    assert (
        "Publishing the candidate skill is required in order to enter this Climb."
        in acceptance.summary
    )
    assert "Uploading raw episodes to a server is prohibited." in acceptance.summary
    assert "Training on raw episodes is prohibited." in acceptance.summary


def test_the_rights_summary_is_stable_across_preparations(
    temp_techtree_home: Path, tmp_path: Path
) -> None:
    first = prepare_draft(temp_techtree_home)[1]
    second = prepare_draft(tmp_path / "second-home")[1]

    assert (
        first.draft.policy_acceptance.summary == second.draft.policy_acceptance.summary
    )


def test_the_episode_estimate_covers_both_variants(
    prepared: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, draft, _ = prepared
    campaign = store.get_source(draft.draft.id).campaign
    selection = campaign.taskset.selection

    assert draft.draft.estimated_episodes == selection.num_tasks * 2


# ---------------------------------------------------------------------------
# The snapshot is a snapshot
# ---------------------------------------------------------------------------


def test_editing_the_source_after_preparing_changes_nothing(
    temp_techtree_home: Path, tmp_path: Path
) -> None:
    source = copy_skill(VALID_SKILL, tmp_path / "skill")
    store, draft, _ = prepare_draft(temp_techtree_home, skill_path=source)
    before = digest_object(store.load_snapshot(draft.draft.id).candidate_skill.artifact)

    (source / "SKILL.md").write_text("# Rewritten\n", encoding="utf-8")
    (source / "glossary.txt").write_text("different\n", encoding="utf-8")

    snapshot = store.load_snapshot(draft.draft.id)
    assert digest_object(snapshot.candidate_skill.artifact) == before
    assert "Rewritten" not in (snapshot.candidate_skill.files / "SKILL.md").read_text(
        "utf-8"
    )


def test_deleting_the_source_after_preparing_leaves_the_draft_valid(
    temp_techtree_home: Path, tmp_path: Path
) -> None:
    source = copy_skill(VALID_SKILL, tmp_path / "skill")
    store, draft, _ = prepare_draft(temp_techtree_home, skill_path=source)

    for path in sorted(source.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    source.rmdir()

    snapshot = store.load_snapshot(draft.draft.id)
    assert snapshot.draft.id == draft.draft.id
    assert (snapshot.candidate_skill.files / "SKILL.md").is_file()


# ---------------------------------------------------------------------------
# Nothing reaches the outside world
# ---------------------------------------------------------------------------


def test_preparing_opens_no_socket_and_starts_no_process(
    temp_techtree_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model call or a worker launch would have to go through one of these."""

    def refuse_socket(*arguments: object, **keywords: object) -> None:
        raise AssertionError("prepare opened a socket")

    def refuse_process(*arguments: object, **keywords: object) -> None:
        raise AssertionError("prepare started a process")

    monkeypatch.setattr(socket, "socket", refuse_socket)
    monkeypatch.setattr(socket, "create_connection", refuse_socket)
    monkeypatch.setattr(subprocess, "Popen", refuse_process)
    monkeypatch.setattr(subprocess, "run", refuse_process)

    store, draft, _ = prepare_draft(temp_techtree_home)

    assert store.load_snapshot(draft.draft.id).comparison.controlled


# ---------------------------------------------------------------------------
# Refusals leave nothing behind
# ---------------------------------------------------------------------------


def test_a_skill_holding_a_credential_leaves_no_draft(
    temp_techtree_home: Path,
) -> None:
    paths = paths_from_root(temp_techtree_home)
    service, _ = preparation_service(paths)

    with pytest.raises(ValidationError) as caught:
        service.prepare(
            climb_reference="synthetic-development",
            skill_path=INVALID_SECRET,
            candidate_label="leaky",
        )

    assert caught.value.code == "skill_secret_detected"
    assert_no_draft(paths.drafts_dir)


def test_a_skill_containing_a_symlink_leaves_no_draft(
    temp_techtree_home: Path,
) -> None:
    paths = paths_from_root(temp_techtree_home)
    service, _ = preparation_service(paths)

    with pytest.raises(ValidationError) as caught:
        service.prepare(
            climb_reference="synthetic-development",
            skill_path=INVALID_SYMLINK,
            candidate_label="linked",
        )

    assert caught.value.code == "skill_invalid"
    assert "symlink" in caught.value.message
    assert_no_draft(paths.drafts_dir)


def test_no_refusal_repeats_the_credential_it_found(
    temp_techtree_home: Path,
) -> None:
    paths = paths_from_root(temp_techtree_home)
    service, _ = preparation_service(paths)
    secret_body = (INVALID_SECRET / "notes.md").read_text("utf-8")

    with pytest.raises(ValidationError) as caught:
        service.prepare(
            climb_reference="synthetic-development",
            skill_path=INVALID_SECRET,
            candidate_label="leaky",
        )

    reported = f"{caught.value.message} {json.dumps(caught.value.details)}"
    for line in secret_body.splitlines():
        stripped = line.strip()
        if len(stripped) > 24:
            assert stripped not in reported


def test_a_label_that_is_not_a_name_is_refused(temp_techtree_home: Path) -> None:
    """The label reaches a public artifact, so it holds a name and nothing else."""
    paths = paths_from_root(temp_techtree_home)
    service, _ = preparation_service(paths)

    with pytest.raises(ValidationError) as caught:
        service.prepare(
            climb_reference="synthetic-development",
            skill_path=VALID_SKILL,
            candidate_label="../../etc/passwd",
        )

    assert caught.value.code == "skill_invalid"
    assert_no_draft(paths.drafts_dir)


def test_a_closed_climb_cannot_be_prepared(temp_techtree_home: Path) -> None:
    paths = paths_from_root(temp_techtree_home)
    service, _ = preparation_service(paths)

    with pytest.raises(PolicyError) as caught:
        service.prepare(
            climb_reference="synthetic-closed",
            skill_path=VALID_SKILL,
            candidate_label="too-late",
        )

    assert caught.value.code == "climb_not_preparable"
    assert_no_draft(paths.drafts_dir)


def test_an_absent_engine_blocks_preparing_but_not_resolving(
    temp_techtree_home: Path,
) -> None:
    """Decisions 0003 A6: list and show still work; prepare does not."""
    paths = paths_from_root(temp_techtree_home)
    service, _ = preparation_service(
        paths, engine=EngineCompatibilityStatus.NOT_INSTALLED
    )

    with pytest.raises(Exception) as caught:
        service.prepare(
            climb_reference="synthetic-development",
            skill_path=VALID_SKILL,
            candidate_label="too-early",
        )

    assert getattr(caught.value, "code", None) == "climb_not_preparable"
    resolved = catalog_service(
        paths, engine=EngineCompatibilityStatus.NOT_INSTALLED
    ).get_climb("synthetic-development")
    assert resolved.climb.metadata.slug == "synthetic-development"


# ---------------------------------------------------------------------------
# Through the command line
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_home(temp_techtree_home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the CLI at the complete fixture, with the engine present."""
    from techtree.cli.context import CliContext
    from techtree.skills.service import SkillPreparationService

    def service_over_the_fixture(context: CliContext) -> Any:
        return SkillPreparationService(
            paths=context.paths,
            catalog=catalog_service(context.paths, catalog_root=COMPLETE_CATALOG),
            draft_store=DraftStore(context.paths),
        )

    monkeypatch.setattr(
        "techtree.cli.commands.climb.build_preparation_service",
        service_over_the_fixture,
    )
    return temp_techtree_home


def test_the_machine_response_carries_everything_a_host_agent_needs(
    cli_home: Path,
) -> None:
    """Spec PR6 §6.9's machine response, and its start action."""
    result = CliRunner().invoke(
        create_app(),
        [
            "--home",
            str(cli_home),
            "--json",
            "climb",
            "prepare",
            "synthetic-development",
            "--skill",
            str(VALID_SKILL),
            "--label",
            "worked-examples",
        ],
    )

    assert result.exit_code == EXIT_OK, result.stdout
    envelope = json.loads(result.stdout.splitlines()[-1])
    payload = envelope["data"]

    assert envelope["ok"] is True
    assert envelope["command"] == "climb prepare"
    assert payload["draft_id"].startswith("draft_")
    assert payload["draft_digest"].startswith("sha256:")
    assert payload["climb_reference"] == "synthetic-development@1"
    assert payload["campaign_spec_digest"].startswith("sha256:")
    assert payload["data_policy_digest"].startswith("sha256:")
    assert payload["skill_root_digest"].startswith("sha256:")
    assert "SKILL.md" in payload["included_files"]
    assert payload["candidate_label"] == "worked-examples"
    assert payload["estimated_episodes"] == 8
    # This fixture Campaign declares no maximum, and the payload says so
    # rather than leaving a reader to supply a figure from elsewhere.
    assert payload["campaign_maximum_usd"] is None
    assert payload["baseline_skill_count"] == 0
    assert payload["candidate_skill_count"] == 1
    assert payload["candidate_ownership"] == "participant"
    assert payload["candidate_public_release"] == "required_for_climb"
    assert payload["raw_episode_server_upload"] == "prohibited"
    assert payload["raw_episode_training_use"] == "prohibited"
    assert payload["proof_grade"] == "development_only"
    assert payload["policy_acceptance"]["required"] is True
    assert payload["policy_acceptance"]["summary"]
    assert payload["comparison"]["controlled"] is True
    assert payload["comparison"]["differences"] == [f"{SKILL_MUTATION_POINTER}/0"]

    start = envelope["next_actions"][0]
    assert start["id"] == "start_climb"
    assert start["requires_user_confirmation"] is True
    assert start["cli"] == ["techtree", "climb", "start", payload["draft_id"]]


def test_the_human_rendering_shows_the_whole_display_list(cli_home: Path) -> None:
    """Spec PR6 §6.9's human output list, plus the rights summary."""
    result = CliRunner().invoke(
        create_app(),
        [
            "--home",
            str(cli_home),
            "climb",
            "prepare",
            "synthetic-development",
            "--skill",
            str(VALID_SKILL),
            "--label",
            "worked-examples",
        ],
    )

    assert result.exit_code == EXIT_OK, result.stdout
    output = " ".join(result.stdout.split())

    for expected in (
        "synthetic-development@1",
        "Climb digest",
        "Campaign digest",
        "Data policy digest",
        "worked-examples",
        "Skill content digest",
        "SKILL.md",
        SKILL_MUTATION_POINTER,
        "Baseline skills 0",
        "Candidate skills 1",
        "Estimated episodes 8",
        "Candidate ownership participant",
        "Public release required for climb",
        "Raw episode upload prohibited",
        "Training use prohibited",
        "Acceptance required before starting",
        "You own the candidate skill",
        "development Climb",
        "techtree climb start",
    ):
        assert expected in output, f"{expected!r} is missing from climb prepare"


def test_a_refused_preparation_reports_a_stable_code(cli_home: Path) -> None:
    result = CliRunner().invoke(
        create_app(),
        [
            "--home",
            str(cli_home),
            "--json",
            "climb",
            "prepare",
            "synthetic-development",
            "--skill",
            str(INVALID_SECRET),
        ],
    )

    assert result.exit_code == EXIT_VALIDATION
    envelope = json.loads(result.stdout.splitlines()[-1])
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "skill_secret_detected"
