"""Cross-coordinate release verification. Spec sections 9.5 and 9.7.

A release verification is only worth running if each of its checks can fail on
its own. Every test below breaks exactly one coordinate and asserts two things:
that the check which owns that coordinate failed, and that no other check did.
A check that never fails, or one that fails whenever its neighbour does, would
survive a weaker test file and hide a real drift.
"""

from __future__ import annotations

from typing import Any

import pytest

from techtree.release.checks import (
    RELEASE_COORDINATE_MISMATCH,
    RELEASE_CORE_DIGEST_MISMATCH,
    RELEASE_CORE_INVALID,
    RELEASE_CORE_NOT_CANONICAL,
    RELEASE_PLACEHOLDER_INDISTINCT,
    ReleaseCheck,
    ReleaseFacts,
    ReleaseVerification,
    verify_release_core,
)
from techtree.release.document import document_digest, render_release_core
from techtree.release.models import (
    PLACEHOLDER_COMMIT,
    PLACEHOLDER_DIGEST,
    PLACEHOLDER_VERSION,
    ReleaseCore,
)

ENGINE_DIGEST = "sha256:" + "1a" * 32
CATALOG_DIGEST = "sha256:" + "2b" * 32
SKILL_DIGEST = "sha256:" + "3c" * 32
SOURCE_COMMIT = "d" * 40
INTRO_CLIMB = "hello-world-climb@1"


def bound_core(**overrides: Any) -> ReleaseCore:
    """Return a release with every coordinate bound to a real value."""
    fields: dict[str, Any] = {
        "schema_version": "techtree.release-core.v1",
        "placeholder_release": False,
        "placeholder_fields": [],
        "release_id": "climb-v0.1.0",
        "cli_version": "0.1.0",
        "cli_source_commit": SOURCE_COMMIT,
        "protocol_version": "v1alpha1",
        "engine_digest": ENGINE_DIGEST,
        "catalog_digest": CATALOG_DIGEST,
        "intro_climb_reference": INTRO_CLIMB,
        "starter_skill_digest": SKILL_DIGEST,
        "skill_improver_digest": SKILL_DIGEST,
        "minimum_host_hermes_version": "0.19.0",
        "maximum_tested_host_hermes_version": "0.19.3",
        "subject_hermes_version": "0.19.0",
    }
    return ReleaseCore(**{**fields, **overrides})


def placeholder_core(**overrides: Any) -> ReleaseCore:
    """Return a release whose founder-owned coordinates are still blank."""
    return bound_core(
        placeholder_release=True,
        placeholder_fields=[
            "cli_source_commit",
            "cli_version",
            "maximum_tested_host_hermes_version",
            "release_id",
            "skill_improver_digest",
            "starter_skill_digest",
        ],
        cli_source_commit=PLACEHOLDER_COMMIT,
        cli_version=PLACEHOLDER_VERSION,
        maximum_tested_host_hermes_version=PLACEHOLDER_VERSION,
        release_id=PLACEHOLDER_VERSION,
        skill_improver_digest=PLACEHOLDER_DIGEST,
        starter_skill_digest=PLACEHOLDER_DIGEST,
        **overrides,
    )


def agreeing_facts(**overrides: Any) -> ReleaseFacts:
    """Return the machine facts a bound release agrees with completely."""
    values: dict[str, Any] = {
        "package_version": "0.1.0",
        "protocol_version": "v1alpha1",
        "engine_digest": ENGINE_DIGEST,
        "catalog_digest": CATALOG_DIGEST,
        "climb_references": (INTRO_CLIMB,),
        "subject_hermes_versions": {INTRO_CLIMB: "0.19.0"},
    }
    return ReleaseFacts(**{**values, **overrides})


def run(core: ReleaseCore, facts: ReleaseFacts, **kwargs: Any) -> ReleaseVerification:
    """Verify a release against a set of facts."""
    return verify_release_core(render_release_core(core), facts, **kwargs)


def by_id(result: ReleaseVerification) -> dict[str, ReleaseCheck]:
    """Return every check the verification ran, keyed by its identifier."""
    checks = {check.id: check for check in result.checks}
    assert len(checks) == len(result.checks), "check identifiers must be unique"
    return checks


def assert_only_failure(
    result: ReleaseVerification, identifier: str, code: str
) -> None:
    """Assert exactly one check failed, that it is this one, and why."""
    assert [check.id for check in result.failures] == [identifier]
    assert by_id(result)[identifier].code == code
    assert result.verified is False


# ---------------------------------------------------------------------------
# The agreeing case
# ---------------------------------------------------------------------------


def test_a_release_that_agrees_with_its_machine_verifies() -> None:
    result = run(bound_core(), agreeing_facts())
    assert result.verified is True
    assert result.failures == []


def test_every_coordinate_is_checked_by_a_named_check() -> None:
    result = run(bound_core(), agreeing_facts())
    assert set(by_id(result)) == {
        "release_core_document",
        "release_core_canonical_bytes",
        "release_core_digest",
        "cli_version",
        "protocol_version",
        "engine_digest",
        "catalog_digest",
        "intro_climb_reference",
        "subject_hermes_version",
        "starter_skill_digest",
        "skill_improver_digest",
    }


# ---------------------------------------------------------------------------
# One broken coordinate at a time
# ---------------------------------------------------------------------------


def test_a_drifted_engine_fails_only_the_engine_check() -> None:
    result = run(bound_core(), agreeing_facts(engine_digest="sha256:" + "9f" * 32))
    assert_only_failure(result, "engine_digest", RELEASE_COORDINATE_MISMATCH)


def test_a_regenerated_catalog_fails_only_the_catalog_check() -> None:
    result = run(bound_core(), agreeing_facts(catalog_digest="sha256:" + "8e" * 32))
    assert_only_failure(result, "catalog_digest", RELEASE_COORDINATE_MISMATCH)


def test_a_protocol_bump_fails_only_the_protocol_check() -> None:
    result = run(bound_core(), agreeing_facts(protocol_version="v1beta1"))
    assert_only_failure(result, "protocol_version", RELEASE_COORDINATE_MISMATCH)


def test_a_package_of_the_wrong_version_fails_only_the_version_check() -> None:
    result = run(bound_core(), agreeing_facts(package_version="0.2.0"))
    assert_only_failure(result, "cli_version", RELEASE_COORDINATE_MISMATCH)


def test_a_catalog_without_the_intro_climb_fails_only_the_climb_check() -> None:
    result = run(
        bound_core(),
        agreeing_facts(climb_references=("something-else@1",)),
    )
    assert_only_failure(result, "intro_climb_reference", RELEASE_COORDINATE_MISMATCH)


def test_a_harness_that_cannot_be_looked_up_is_a_failure_not_a_pass() -> None:
    """A whole different catalog breaks the Climb and the harness it pins."""
    result = run(
        bound_core(),
        agreeing_facts(
            climb_references=("something-else@1",),
            subject_hermes_versions={"something-else@1": "0.19.0"},
        ),
    )
    assert [check.id for check in result.failures] == [
        "intro_climb_reference",
        "subject_hermes_version",
    ]
    assert "cannot be compared" in by_id(result)["subject_hermes_version"].detail


def test_a_recut_campaign_fails_only_the_harness_check() -> None:
    result = run(
        bound_core(),
        agreeing_facts(subject_hermes_versions={INTRO_CLIMB: "0.20.0"}),
    )
    assert_only_failure(result, "subject_hermes_version", RELEASE_COORDINATE_MISMATCH)


def test_an_unexpected_digest_fails_only_the_digest_check() -> None:
    result = run(
        bound_core(),
        agreeing_facts(),
        expected_digest="sha256:" + "7d" * 32,
    )
    assert_only_failure(result, "release_core_digest", RELEASE_CORE_DIGEST_MISMATCH)


def test_the_expected_digest_is_the_digest_of_the_stored_bytes() -> None:
    raw = render_release_core(bound_core())
    result = verify_release_core(
        raw, agreeing_facts(), expected_digest=document_digest(raw)
    )
    assert result.verified is True
    assert by_id(result)["release_core_digest"].status == "passed"


def test_a_reindented_document_fails_the_spelling_check() -> None:
    raw = render_release_core(bound_core()).replace(b"\n  ", b"\n\t")
    result = verify_release_core(raw, agreeing_facts())
    assert_only_failure(
        result, "release_core_canonical_bytes", RELEASE_CORE_NOT_CANONICAL
    )


def test_a_document_that_is_not_a_release_stops_the_verification() -> None:
    result = verify_release_core(b"{}", agreeing_facts())
    assert [check.id for check in result.checks] == ["release_core_document"]
    assert result.failures[0].code == RELEASE_CORE_INVALID


# ---------------------------------------------------------------------------
# Placeholders are checked, not excused
# ---------------------------------------------------------------------------


def test_a_placeholder_release_still_verifies() -> None:
    result = run(placeholder_core(), agreeing_facts())
    assert result.verified is True


def test_a_declared_placeholder_version_is_reported_as_unbound() -> None:
    result = run(placeholder_core(), agreeing_facts())
    assert "declared unbound" in by_id(result)["cli_version"].detail


def test_a_placeholder_that_matches_the_installed_version_is_a_failure() -> None:
    """A blank that happens to equal reality cannot be told from a binding."""
    result = run(
        placeholder_core(), agreeing_facts(package_version=PLACEHOLDER_VERSION)
    )
    assert_only_failure(result, "cli_version", RELEASE_PLACEHOLDER_INDISTINCT)


def test_unbound_skill_digests_pass_and_bound_ones_are_left_to_the_plugin() -> None:
    unbound = by_id(run(placeholder_core(), agreeing_facts()))
    assert unbound["starter_skill_digest"].status == "passed"

    bound = by_id(run(bound_core(), agreeing_facts()))
    assert bound["starter_skill_digest"].status == "skipped"
    assert "carries no Skill bytes" in bound["starter_skill_digest"].detail


def test_a_check_that_could_not_run_is_never_reported_as_a_pass() -> None:
    result = run(bound_core(), agreeing_facts())
    assert {check.id for check in result.skipped} == {
        "release_core_digest",
        "starter_skill_digest",
        "skill_improver_digest",
    }
    assert all(check.status != "passed" for check in result.skipped)


# ---------------------------------------------------------------------------
# The verdict follows the checks
# ---------------------------------------------------------------------------


def test_a_verdict_the_checks_do_not_support_is_refused() -> None:
    with pytest.raises(ValueError, match="verifies exactly when no check failed"):
        ReleaseVerification(
            verified=True,
            checks=[
                ReleaseCheck(
                    id="engine_digest",
                    status="failed",
                    code=RELEASE_COORDINATE_MISMATCH,
                    detail="the engine moved.",
                )
            ],
        )


def test_skipped_checks_do_not_prevent_a_verdict() -> None:
    result = ReleaseVerification(
        verified=True,
        checks=[
            ReleaseCheck(
                id="release_core_digest",
                status="skipped",
                code="release_check_not_applicable",
                detail="no expected digest was given.",
            )
        ],
    )
    assert result.verified is True
    assert len(result.skipped) == 1
