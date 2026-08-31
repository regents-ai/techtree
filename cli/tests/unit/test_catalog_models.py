"""The packaged catalog, summaries, and compatibility. Decisions 0003 A6/A7.

The index is generated, so the tests here are about what a hand-edit or a
buggy generator could produce: a repeated reference, a path that climbs out of
the package, two digests claiming the same file.

``CompatibilityResult`` gets the same treatment from the other direction. Its
``compatible`` flag is derived from the issues it lists, so the tests check that
it cannot claim to be runnable while naming the reason it is not — the failure
mode that turns a clear "install the engine first" into a confusing later crash.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import sha256_digest_bytes
from techtree.constants import CATALOG_SCHEMA_VERSION
from techtree.models.catalog import (
    CatalogClimbEntry,
    CatalogIndex,
    CatalogObjectLocation,
    ClimbSummary,
    CompatibilityIssue,
    CompatibilityResult,
    EngineCompatibilityStatus,
)
from techtree.models.cli import CliEnvelope
from techtree.models.evaluation_backend import EvaluationBackendKind

GOLDEN_DIRECTORY = Path(__file__).resolve().parents[1] / "golden"

CLIMB_DIGEST = sha256_digest_bytes(b"climb")
CAMPAIGN_DIGEST = sha256_digest_bytes(b"campaign")
POLICY_DIGEST = sha256_digest_bytes(b"policy")
ENGINE_DIGEST = sha256_digest_bytes(b"engine")


def index(**overrides: Any) -> CatalogIndex:
    """Build a catalog index with one Climb and one referenced object."""
    fields: dict[str, Any] = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "climbs": [
            CatalogClimbEntry(
                reference="hello-world-climb@1",
                digest=CLIMB_DIGEST,
                path="climbs/hello-world-climb.json",
            )
        ],
        "objects": {
            CAMPAIGN_DIGEST: CatalogObjectLocation(
                kind="campaign",
                path="campaigns/hello-world-climb.json",
                media_type="application/json",
            )
        },
    }
    fields.update(overrides)
    return CatalogIndex(**fields)


# ---------------------------------------------------------------------------
# The index
# ---------------------------------------------------------------------------


def test_an_index_maps_climbs_and_objects_to_files() -> None:
    catalog = index()

    assert catalog.climbs[0].reference == "hello-world-climb@1"
    assert catalog.objects[CAMPAIGN_DIGEST].kind == "campaign"


def test_the_empty_packaged_catalog_is_valid() -> None:
    """Decisions 0003 A2: the packaged catalog ships valid and empty."""
    catalog = CatalogIndex.model_validate_json(
        json.dumps(
            {
                "schema_version": CATALOG_SCHEMA_VERSION,
                "climbs": [],
                "objects": {},
            }
        )
    )

    assert catalog.climbs == []
    assert catalog.objects == {}


def test_index_rejects_a_repeated_climb_reference() -> None:
    entry = CatalogClimbEntry(
        reference="hello-world-climb@1",
        digest=sha256_digest_bytes(b"other climb"),
        path="climbs/other.json",
    )

    with pytest.raises(PydanticValidationError, match="reference appears once"):
        index(climbs=[*index().climbs, entry])


def test_index_rejects_a_repeated_climb_digest() -> None:
    entry = CatalogClimbEntry(
        reference="other@1",
        digest=CLIMB_DIGEST,
        path="climbs/other.json",
    )

    with pytest.raises(PydanticValidationError, match="digest appears once"):
        index(climbs=[*index().climbs, entry])


def test_index_rejects_two_digests_claiming_the_same_file() -> None:
    objects = dict(index().objects)
    objects[POLICY_DIGEST] = CatalogObjectLocation(
        kind="data_policy",
        path="campaigns/hello-world-climb.json",
        media_type="application/json",
    )

    with pytest.raises(PydanticValidationError, match="same file"):
        index(objects=objects)


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "../outside.json",
        "campaigns/../../outside.json",
        "campaigns\\windows.json",
        "campaigns//double.json",
        " campaigns/leading-space.json",
    ],
)
def test_index_rejects_a_path_that_leaves_the_catalog_root(path: str) -> None:
    with pytest.raises(PydanticValidationError):
        CatalogObjectLocation(
            kind="campaign",
            path=path,
            media_type="application/json",
        )


def test_index_rejects_an_unknown_object_kind() -> None:
    with pytest.raises(PydanticValidationError):
        CatalogObjectLocation(
            kind="episode_receipt",  # type: ignore[arg-type]
            path="receipts/one.json",
            media_type="application/json",
        )


def test_index_rejects_a_digest_key_that_is_not_a_digest() -> None:
    with pytest.raises(PydanticValidationError):
        index(
            objects={
                "campaign-1": CatalogObjectLocation(
                    kind="campaign",
                    path="campaigns/one.json",
                    media_type="application/json",
                )
            }
        )


# ---------------------------------------------------------------------------
# Compatibility
# ---------------------------------------------------------------------------


def compatibility(**overrides: Any) -> CompatibilityResult:
    """Build a compatibility result for a host with no engine installed."""
    fields: dict[str, Any] = {
        "compatible": False,
        "host_platform": "darwin/arm64",
        "host_supported": True,
        "required_engine_digest": ENGINE_DIGEST,
        "engine_status": EngineCompatibilityStatus.NOT_INSTALLED,
        "evaluation_backend_kind": EvaluationBackendKind.LOCAL_TECHTREE,
        "evaluation_backend_supported": True,
        "issues": [
            CompatibilityIssue(
                code="engine_not_installed",
                severity="error",
                message="The evaluation engine is not installed yet.",
                blocking=True,
            )
        ],
    }
    fields.update(overrides)
    return CompatibilityResult(**fields)


def test_a_missing_engine_blocks_compatibility() -> None:
    result = compatibility()

    assert result.compatible is False
    assert result.engine_status is EngineCompatibilityStatus.NOT_INSTALLED
    assert result.issues[0].blocking is True


def test_a_verified_engine_with_no_issues_is_compatible() -> None:
    result = compatibility(
        compatible=True,
        engine_status=EngineCompatibilityStatus.VERIFIED,
        issues=[],
    )

    assert result.compatible is True


def test_a_non_blocking_warning_does_not_make_a_result_incompatible() -> None:
    result = compatibility(
        compatible=True,
        engine_status=EngineCompatibilityStatus.INSTALLED_UNVERIFIED,
        issues=[
            CompatibilityIssue(
                code="engine_unverified",
                severity="warning",
                message="The installed engine has not been verified.",
                blocking=False,
            )
        ],
    )

    assert result.compatible is True


def test_a_result_cannot_be_compatible_while_listing_a_blocking_issue() -> None:
    with pytest.raises(PydanticValidationError, match="no listed issue is blocking"):
        compatibility(compatible=True)


def test_an_incompatible_result_must_say_what_blocked_it() -> None:
    with pytest.raises(PydanticValidationError, match="must list the blocking issue"):
        compatibility(issues=[])


def test_a_blocking_issue_cannot_be_a_warning() -> None:
    with pytest.raises(PydanticValidationError, match="is an error, not a warning"):
        CompatibilityIssue(
            code="engine_unverified",
            severity="warning",
            message="The installed engine has not been verified.",
            blocking=True,
        )


def test_compatibility_issue_codes_are_reported_once() -> None:
    issue = CompatibilityIssue(
        code="engine_not_installed",
        severity="error",
        message="The evaluation engine is not installed yet.",
        blocking=True,
    )

    with pytest.raises(PydanticValidationError, match="reported once"):
        compatibility(issues=[issue, issue])


# ---------------------------------------------------------------------------
# The Climb summary
# ---------------------------------------------------------------------------


def summary_from_golden() -> ClimbSummary:
    """Load the summary carried by the committed CLI envelope golden."""
    text = (GOLDEN_DIRECTORY / "cli-envelope.json").read_text(encoding="utf-8")
    envelope = CliEnvelope[ClimbSummary].model_validate_json(text)
    assert envelope.data is not None
    return envelope.data


def test_the_climb_summary_shows_identity_science_and_rights() -> None:
    summary = summary_from_golden()

    assert summary.reference == "hello-world-climb@1"
    assert summary.taskset_id == "procedure-transfer-v1"
    assert summary.task_count == 20
    assert summary.subject_harness == "hermes-agent"
    assert summary.mutation_kind == "skill_insertion"
    assert summary.proof_grade == "development_only"
    assert summary.data_policy.raw_episode_server_upload == "prohibited"
    assert summary.data_policy.candidate_skill_public_release == "required_for_climb"
    assert summary.compatibility.compatible is False


def test_the_climb_summary_carries_no_scientific_configuration() -> None:
    fields = set(ClimbSummary.model_fields)

    assert fields.isdisjoint({"agents", "execution", "scoring", "budgets", "taskset"})


def test_the_climb_summary_rejects_an_invented_status() -> None:
    document = json.loads(summary_from_golden().model_dump_json())
    document["status"] = "archived"

    with pytest.raises(PydanticValidationError):
        ClimbSummary.model_validate_json(json.dumps(document))
