"""The draft graph on disk. Spec PR6 §6.7 and §6.11.

A draft has to be checkable by a process that has never seen the catalog, so
these tests load one, break exactly one link in it, and require the specific
typed failure that link is protected by. Breaking one thing at a time is what
distinguishes "the verification catches this" from "something failed".

The drafts are prepared by the real preparation service against the complete
synthetic catalog fixture. A store test that hand-assembled its own draft would
be asserting that the store agrees with the test, which is not the question.

Two behaviours here belong to PR8 but are owned by this store: the exactly-once
start claim, and what happens when a launch fails after the confirmation has
been spent. They are tested now because getting them wrong later would be
invisible until two runs came out of one draft.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fixtures.drafts.support import (
    COMPLETE_CATALOG,
    VALID_SKILL,
    preparation_service,
    prepare_draft,
)
from techtree.canonical import canonical_json_bytes, digest_object
from techtree.drafts.store import DraftStartStatus, DraftStore
from techtree.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    VerificationError,
)
from techtree.ids import new_id
from techtree.paths import paths_from_root
from techtree.skills.service import PreparedDraft


@pytest.fixture
def draft(
    temp_techtree_home: Path,
) -> tuple[DraftStore, PreparedDraft, Path]:
    """Return a real prepared draft and the directory it occupies."""
    store, prepared, _ = prepare_draft(temp_techtree_home)
    return store, prepared, store.draft_dir(prepared.draft.id)


def rewrite(path: Path, mutate: Any) -> None:
    """Replace one snapshotted JSON document with an altered copy."""
    document = json.loads(path.read_text("utf-8"))
    path.write_text(json.dumps(mutate(document)), encoding="utf-8")


# ---------------------------------------------------------------------------
# The layout
# ---------------------------------------------------------------------------


def test_a_created_draft_holds_the_whole_documented_layout(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    """Spec PR6 §5, including the evidence decisions 0003 A4 requires."""
    _, _, directory = draft

    for relative in (
        "draft.json",
        "confirmation.json",
        "comparison.json",
        "public/climb.json",
        "public/campaign.json",
        "public/data-policy.json",
        "public/publisher-validation.json",
        "public/publisher-validation-evidence.json",
        "manifests/baseline.json",
        "manifests/candidate.json",
        "skill/artifact.json",
        "skill/bundle.tar",
        "skill/files/SKILL.md",
    ):
        assert (directory / relative).is_file(), relative

    assert not (directory / "start.json").exists()


def test_no_staging_directory_survives_a_successful_prepare(
    temp_techtree_home: Path,
) -> None:
    store, prepared, paths = prepare_draft(temp_techtree_home)

    leftovers = [
        entry.name for entry in paths.drafts_dir.iterdir() if entry.name.startswith(".")
    ]
    assert leftovers == []
    assert store.draft_dir(prepared.draft.id).is_dir()


def test_the_raw_token_is_nowhere_on_disk(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    _, prepared, directory = draft

    for path in directory.rglob("*"):
        if path.is_file():
            assert prepared.confirmation_token not in path.read_bytes().decode(
                "utf-8", errors="replace"
            )


# ---------------------------------------------------------------------------
# Loading and verifying, without the catalog
# ---------------------------------------------------------------------------


def test_a_draft_verifies_from_its_own_bytes_alone(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    """No catalog is consulted; the draft is the whole evidence."""
    store, prepared, _ = draft

    snapshot = store.load_snapshot(prepared.draft.id)

    assert snapshot.draft == prepared.draft
    assert snapshot.comparison.controlled
    assert snapshot.resolved_climb.climb_digest == prepared.resolved_climb.climb_digest
    assert digest_object(snapshot.validation_evidence) == (
        snapshot.resolved_climb.publisher_validation.normalized_evidence.digest  # type: ignore[union-attr]
    )


def test_the_snapshot_survives_the_catalog_disappearing(
    temp_techtree_home: Path,
    tmp_path: Path,
) -> None:
    """Decisions 0003 A4: a draft outlives the build that shipped its Climb."""
    disposable = tmp_path / "catalog"
    disposable.mkdir()
    for source in COMPLETE_CATALOG.rglob("*"):
        target = disposable / source.relative_to(COMPLETE_CATALOG)
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.write_bytes(source.read_bytes())

    paths = paths_from_root(temp_techtree_home)
    service, store = preparation_service(paths, catalog_root=disposable)
    prepared = service.prepare(
        climb_reference="synthetic-development",
        skill_path=VALID_SKILL,
        candidate_label="candidate-under-test",
    )

    for path in sorted(disposable.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    disposable.rmdir()

    snapshot = store.load_snapshot(prepared.draft.id)
    assert snapshot.draft.id == prepared.draft.id


def test_the_manifests_and_comparison_load_back(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, prepared, _ = draft

    baseline, candidate = store.get_manifests(prepared.draft.id)
    comparison = store.get_comparison(prepared.draft.id)

    assert digest_object(baseline) == prepared.draft.baseline_manifest_digest
    assert digest_object(candidate) == prepared.draft.candidate_manifest_digest
    assert comparison == prepared.manifest_comparison


def test_the_file_list_in_the_draft_is_the_skill_artifacts(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, prepared, _ = draft

    skill = store.get_skill(prepared.draft.id)

    assert list(prepared.draft.included_files) == [file.path for file in skill.files]
    assert "SKILL.md" in prepared.draft.included_files


def test_an_unknown_draft_is_reported_as_missing(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, _, _ = draft

    with pytest.raises(NotFoundError) as caught:
        store.get(new_id("draft"))

    assert caught.value.code == "draft_not_found"


# ---------------------------------------------------------------------------
# One broken link at a time
# ---------------------------------------------------------------------------


def test_a_tampered_campaign_is_caught(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, prepared, directory = draft
    rewrite(
        directory / "public" / "campaign.json",
        lambda document: {
            **document,
            "execution": {**document["execution"], "timeout_seconds": 1},
        },
    )

    with pytest.raises(VerificationError) as caught:
        store.load_snapshot(prepared.draft.id)

    assert caught.value.code in {"campaign_digest_mismatch", "catalog_graph_invalid"}


def test_a_tampered_data_policy_is_caught(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, prepared, directory = draft
    rewrite(
        directory / "public" / "data-policy.json",
        lambda document: {
            **document,
            "raw_episodes": {**document["raw_episodes"], "training_use": "allowed"},
        },
    )

    with pytest.raises(VerificationError) as caught:
        store.load_snapshot(prepared.draft.id)

    assert caught.value.code in {
        "data_policy_digest_mismatch",
        "catalog_graph_invalid",
    }


def test_tampered_validation_evidence_is_caught(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, prepared, directory = draft
    rewrite(
        directory / "public" / "publisher-validation-evidence.json",
        lambda document: {
            **document,
            "summary": {**document["summary"], "valid": 3, "invalid": 1},
        },
    )

    with pytest.raises(VerificationError) as caught:
        store.load_snapshot(prepared.draft.id)

    assert caught.value.code == "publisher_validation_evidence_missing"


def test_a_tampered_skill_file_is_caught(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, prepared, directory = draft
    (directory / "skill" / "files" / "SKILL.md").write_text(
        "# Rewritten after the fact\n", encoding="utf-8"
    )

    with pytest.raises(VerificationError) as caught:
        store.load_snapshot(prepared.draft.id)

    assert caught.value.code == "skill_invalid"


def test_a_tampered_bundle_is_caught(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, prepared, directory = draft
    (directory / "skill" / "bundle.tar").write_bytes(b"not a tar file")

    with pytest.raises(VerificationError) as caught:
        store.get_skill(prepared.draft.id)

    assert caught.value.code == "skill_invalid"


def test_a_draft_whose_file_list_disagrees_with_its_artifact_is_caught(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, prepared, directory = draft
    snapshot = store.load_snapshot(prepared.draft.id)
    lying = snapshot.draft.model_copy(update={"included_files": ["SKILL.md"]})

    with pytest.raises(VerificationError) as caught:
        store.verify_snapshot(
            type(snapshot)(
                draft=lying,
                resolved_climb=snapshot.resolved_climb,
                validation_evidence=snapshot.validation_evidence,
                baseline=snapshot.baseline,
                candidate=snapshot.candidate,
                comparison=snapshot.comparison,
                skill=snapshot.skill,
                skill_archive=snapshot.skill_archive,
                skill_files=snapshot.skill_files,
            )
        )

    assert caught.value.code == "skill_invalid"
    assert directory.is_dir()


def test_a_receipt_with_no_evidence_cannot_become_a_draft(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    """A draft referencing evidence it does not hold would not be checkable."""
    store, prepared, _ = draft
    snapshot = store.load_snapshot(prepared.draft.id)
    resolved = snapshot.resolved_climb
    dangling = resolved.model_copy(
        update={
            "publisher_validation": resolved.publisher_validation.model_copy(
                update={"normalized_evidence": None}
            )
        }
    )
    second = snapshot.draft.model_copy(update={"id": new_id("draft")})

    with pytest.raises(VerificationError) as caught:
        store.create(
            draft=second,
            confirmation=store.get_confirmation(prepared.draft.id),
            baseline=snapshot.baseline,
            candidate=snapshot.candidate,
            comparison=snapshot.comparison,
            resolved_climb=dangling,
            validation_evidence=snapshot.validation_evidence,
            staged_skill_dir=snapshot.skill_files,
            staged_skill_archive=snapshot.skill_archive,
        )

    assert caught.value.code == "publisher_validation_evidence_missing"
    assert not store.draft_dir(second.id).exists()
    leftovers = [
        entry.name
        for entry in store.draft_dir(second.id).parent.iterdir()
        if entry.name.startswith(".")
    ]
    assert leftovers == []


# ---------------------------------------------------------------------------
# Creation refusals
# ---------------------------------------------------------------------------


def test_a_second_draft_under_the_same_identifier_is_refused(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, prepared, _ = draft
    snapshot = store.load_snapshot(prepared.draft.id)

    with pytest.raises(ConflictError) as caught:
        store.create(
            draft=snapshot.draft,
            confirmation=store.get_confirmation(prepared.draft.id),
            baseline=snapshot.baseline,
            candidate=snapshot.candidate,
            comparison=snapshot.comparison,
            resolved_climb=snapshot.resolved_climb,
            validation_evidence=snapshot.validation_evidence,
            staged_skill_dir=snapshot.skill_files,
            staged_skill_archive=snapshot.skill_archive,
        )

    assert caught.value.code == "draft_already_exists"


# ---------------------------------------------------------------------------
# The one-time start claim
# ---------------------------------------------------------------------------


def test_claiming_a_start_consumes_the_confirmation_once(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, prepared, directory = draft
    run_id = new_id("run")

    claim = store.claim_start(
        draft_id=prepared.draft.id, token=prepared.confirmation_token, run_id=run_id
    )

    assert claim.status is DraftStartStatus.CLAIMED
    assert claim.run_id == run_id
    assert (directory / "start.json").is_file()
    assert store.get_confirmation(prepared.draft.id).consumed_at is not None


def test_claiming_twice_returns_the_first_run_rather_than_a_second(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    """A retried start is not a second start."""
    store, prepared, _ = draft
    first = store.claim_start(
        draft_id=prepared.draft.id,
        token=prepared.confirmation_token,
        run_id=new_id("run"),
    )

    second = store.claim_start(
        draft_id=prepared.draft.id,
        token=prepared.confirmation_token,
        run_id=new_id("run"),
    )

    assert second.run_id == first.run_id
    assert second.claimed_at == first.claimed_at


def test_a_wrong_token_claims_nothing(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, prepared, directory = draft

    with pytest.raises(AuthenticationError):
        store.claim_start(
            draft_id=prepared.draft.id, token="not-the-token", run_id=new_id("run")
        )

    assert not (directory / "start.json").exists()
    assert store.get_confirmation(prepared.draft.id).consumed_at is None
    assert store.start_record(prepared.draft.id) is None


def test_a_launch_is_recorded_against_the_claimed_run(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, prepared, _ = draft
    claim = store.claim_start(
        draft_id=prepared.draft.id,
        token=prepared.confirmation_token,
        run_id=new_id("run"),
    )

    launched = store.mark_launched(
        draft_id=prepared.draft.id,
        run_id=claim.run_id,
        launched_at=claim.claimed_at,
    )

    assert launched.status is DraftStartStatus.LAUNCHED
    assert launched.launched_at == claim.claimed_at
    assert store.start_record(prepared.draft.id) == launched


def test_a_failed_launch_stays_visible(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    """The confirmation is already spent, so the failure must not vanish."""
    store, prepared, _ = draft
    claim = store.claim_start(
        draft_id=prepared.draft.id,
        token=prepared.confirmation_token,
        run_id=new_id("run"),
    )

    failed = store.mark_launch_failed(
        draft_id=prepared.draft.id,
        run_id=claim.run_id,
        error_code="worker_launch_failed",
    )

    assert failed.status is DraftStartStatus.LAUNCH_FAILED
    assert failed.launch_error_code == "worker_launch_failed"


def test_another_run_cannot_take_over_a_claim(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, prepared, _ = draft
    store.claim_start(
        draft_id=prepared.draft.id,
        token=prepared.confirmation_token,
        run_id=new_id("run"),
    )

    with pytest.raises(ConflictError) as caught:
        store.mark_launched(
            draft_id=prepared.draft.id,
            run_id=new_id("run"),
            launched_at=prepared.confirmation_expires_at,
        )

    assert caught.value.code == "draft_start_conflict"


def test_marking_a_launch_before_a_claim_is_refused(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, prepared, _ = draft

    with pytest.raises(NotFoundError) as caught:
        store.mark_launched(
            draft_id=prepared.draft.id,
            run_id=new_id("run"),
            launched_at=prepared.confirmation_expires_at,
        )

    assert caught.value.code == "draft_not_started"


def test_a_start_record_round_trips_through_canonical_bytes(
    draft: tuple[DraftStore, PreparedDraft, Path],
) -> None:
    store, prepared, directory = draft
    claim = store.claim_start(
        draft_id=prepared.draft.id,
        token=prepared.confirmation_token,
        run_id=new_id("run"),
    )

    stored = (directory / "start.json").read_bytes()

    assert stored == canonical_json_bytes(claim)
