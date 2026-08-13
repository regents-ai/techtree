"""The committed protocol goldens. Spec sections 8, 24.4, 27.3.

A golden is a representative instance of a protocol object, generated from
typed Python and committed. These tests hold four things in place:

* Exactly the expected files exist, so a golden cannot quietly disappear.
* Each one still validates against its model, loaded the way stored documents
  are loaded — from bytes, in JSON mode.
* The formatting is deterministic, so a regeneration produces a diff only when
  the content actually changed.
* The fixture graph is internally consistent: the Climb's Campaign digest is
  the digest of the committed Campaign, and so on down.

The last one is the reason the goldens are worth having. A set of unrelated
example documents would prove that each model parses. A consistent graph proves
that the digests joining them mean what the protocol says they mean.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from techtree.canonical import canonical_json_bytes, digest_object, sha256_digest_bytes
from techtree.models.campaign import CampaignSpec
from techtree.models.catalog import ClimbSummary
from techtree.models.cli import CliEnvelope
from techtree.models.climb import ClimbManifest
from techtree.models.data_policy import DataPolicy
from techtree.models.experiment import ExperimentManifest, ExperimentVariant
from techtree.models.skill import SkillArtifact
from techtree.models.uplift_report import UpliftReport
from techtree.models.validation import TasksetLock, TasksetValidationReceipt

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIRECTORY = REPOSITORY_ROOT / "tests" / "golden"

#: Spec section 8. One representative instance per protocol object that a
#: reviewer should be able to read in a diff.
GOLDEN_MODELS: dict[str, type[BaseModel]] = {
    "campaign": CampaignSpec,
    "cli-envelope": CliEnvelope[ClimbSummary],
    "climb": ClimbManifest,
    "data-policy": DataPolicy,
    "experiment-baseline": ExperimentManifest,
    "experiment-candidate": ExperimentManifest,
    "fake-uplift-report": UpliftReport,
    "skill-artifact": SkillArtifact,
    "taskset-lock": TasksetLock,
    "taskset-validation-receipt": TasksetValidationReceipt,
}


def golden_text(name: str) -> str:
    """Return one committed golden as text."""
    return (GOLDEN_DIRECTORY / f"{name}.json").read_text(encoding="utf-8")


def golden_document(name: str) -> dict[str, Any]:
    """Return one committed golden as a parsed document."""
    document: dict[str, Any] = json.loads(golden_text(name))
    return document


def load(name: str) -> Any:
    """Validate one committed golden the way a stored document is loaded."""
    return GOLDEN_MODELS[name].model_validate_json(golden_text(name))


def test_exactly_the_expected_goldens_are_committed() -> None:
    committed = {path.name for path in GOLDEN_DIRECTORY.iterdir()}

    assert committed == {f"{name}.json" for name in GOLDEN_MODELS}


@pytest.mark.parametrize("name", sorted(GOLDEN_MODELS))
def test_each_golden_validates_against_its_model(name: str) -> None:
    assert isinstance(load(name), BaseModel)


@pytest.mark.parametrize("name", sorted(GOLDEN_MODELS))
def test_each_golden_is_deterministically_formatted(name: str) -> None:
    text = golden_text(name)
    expected = json.dumps(
        json.loads(text), indent=2, sort_keys=True, ensure_ascii=False
    )

    assert text == f"{expected}\n"


@pytest.mark.parametrize("name", sorted(GOLDEN_MODELS))
def test_each_golden_round_trips_through_its_model(name: str) -> None:
    """Parsing and re-canonicalizing must reproduce the same bytes."""
    parsed = load(name)
    reparsed = GOLDEN_MODELS[name].model_validate_json(
        canonical_json_bytes(parsed).decode("utf-8")
    )

    assert canonical_json_bytes(reparsed) == canonical_json_bytes(parsed)


@pytest.mark.parametrize("name", sorted(GOLDEN_MODELS))
def test_each_golden_has_a_stable_digest(name: str) -> None:
    assert digest_object(load(name)) == digest_object(load(name))


@pytest.mark.parametrize("name", sorted(GOLDEN_MODELS))
def test_no_golden_mentions_relay(name: str) -> None:
    """Decisions 0001: no Relay package, field, exporter, or status."""
    assert "relay" not in golden_text(name).lower()


@pytest.mark.parametrize("name", sorted(GOLDEN_MODELS))
def test_no_golden_contains_a_local_path(name: str) -> None:
    """Absolute paths are host detail and never enter a protocol document."""
    text = golden_text(name)

    assert "/Users/" not in text
    assert "/home/" not in text
    assert "/private/var/" not in text


@pytest.mark.parametrize("name", sorted(GOLDEN_MODELS))
def test_no_golden_carries_a_credential_value(name: str) -> None:
    """A credential is named by an environment variable, never carried."""
    text = golden_text(name)

    assert "sk-" not in text
    assert "Bearer " not in text


# ---------------------------------------------------------------------------
# The fixture graph
# ---------------------------------------------------------------------------


def test_the_climb_points_at_the_committed_campaign() -> None:
    climb: ClimbManifest = load("climb")

    assert climb.campaign_spec_digest == digest_object(load("campaign"))


def test_the_campaign_points_at_the_committed_data_policy() -> None:
    campaign: CampaignSpec = load("campaign")

    assert campaign.data_policy_digest == digest_object(load("data-policy"))


def test_the_campaign_points_at_the_committed_validation_receipt() -> None:
    campaign: CampaignSpec = load("campaign")

    assert campaign.taskset.validation_receipt_digest == digest_object(
        load("taskset-validation-receipt")
    )


def test_the_receipt_points_at_the_committed_lock() -> None:
    receipt: TasksetValidationReceipt = load("taskset-validation-receipt")

    assert receipt.taskset_lock_digest == digest_object(load("taskset-lock"))


def test_the_lock_and_the_campaign_commit_to_the_same_tasks() -> None:
    lock: TasksetLock = load("taskset-lock")
    campaign: CampaignSpec = load("campaign")

    assert lock.ordered_task_hashes == campaign.taskset.membership.ordered_task_hashes
    assert lock.membership_digest == campaign.taskset.membership.membership_digest


def test_both_experiments_reference_the_same_campaign_and_policy() -> None:
    baseline: ExperimentManifest = load("experiment-baseline")
    candidate: ExperimentManifest = load("experiment-candidate")

    assert baseline.campaign_spec_digest == candidate.campaign_spec_digest
    assert (
        baseline.configuration.data_policy_digest
        == candidate.configuration.data_policy_digest
    )
    assert (
        baseline.configuration.evaluation_backend
        == candidate.configuration.evaluation_backend
    )
    assert baseline.public_context == candidate.public_context
    assert baseline.program_ref == candidate.program_ref


def test_the_two_experiments_are_the_two_variants() -> None:
    assert load("experiment-baseline").variant is ExperimentVariant.BASELINE
    assert load("experiment-candidate").variant is ExperimentVariant.CANDIDATE


def test_the_candidate_carries_the_committed_skill_archive() -> None:
    candidate: ExperimentManifest = load("experiment-candidate")
    skill: SkillArtifact = load("skill-artifact")

    inserted = candidate.configuration.agents["subject"].harness.skills

    assert [reference.digest for reference in inserted] == [skill.archive_digest]


def test_the_fake_report_compares_the_committed_experiments() -> None:
    report: UpliftReport = load("fake-uplift-report")

    assert report.baseline_manifest_digest == digest_object(load("experiment-baseline"))
    assert report.candidate_manifest_digest == digest_object(
        load("experiment-candidate")
    )
    assert report.campaign_spec_digest == digest_object(load("campaign"))


def test_the_fake_report_is_unmistakably_a_development_artifact() -> None:
    report: UpliftReport = load("fake-uplift-report")

    assert report.proof_grade == "development_only"
    assert report.decision.value == "development_only"
    assert report.statuses.score.value == "development_only"
    assert report.statuses.evidence.value == "development_only"
    assert report.statuses.comparison.value == "development_only"
    assert report.statuses.publication.value == "blocked"
    assert report.publication_eligible is False


def test_the_cli_envelope_golden_carries_the_committed_climb_summary() -> None:
    envelope: CliEnvelope[ClimbSummary] = load("cli-envelope")
    climb: ClimbManifest = load("climb")

    assert envelope.ok is True
    assert envelope.error is None
    assert envelope.data is not None
    assert envelope.data.climb_digest == digest_object(climb)
    assert envelope.data.campaign_spec_digest == climb.campaign_spec_digest
    assert len(envelope.next_actions) <= 3


# ---------------------------------------------------------------------------
# Digest sensitivity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "pointer"),
    [
        ("campaign", ("scoring", "minimum_absolute_delta")),
        ("climb", ("metadata", "title")),
        ("data-policy", ("raw_episodes", "reproduction_access")),
        ("taskset-lock", ("engine_digest",)),
    ],
)
def test_one_changed_field_changes_the_digest(
    name: str, pointer: tuple[str, ...]
) -> None:
    original = load(name)
    document = golden_document(name)

    target: Any = document
    for key in pointer[:-1]:
        target = target[key]
    current = target[pointer[-1]]
    target[pointer[-1]] = (
        sha256_digest_bytes(b"changed")
        if isinstance(current, str) and current.startswith("sha256:")
        else _changed(current)
    )

    changed = GOLDEN_MODELS[name].model_validate_json(json.dumps(document))

    assert digest_object(changed) != digest_object(original)


def _changed(value: Any) -> Any:
    """Return a different but still valid value of the same kind."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int | float):
        return value + 1
    if value == "prohibited":
        return "allowed"
    if value == "consent_required":
        return "prohibited"
    return f"{value} (changed)"
