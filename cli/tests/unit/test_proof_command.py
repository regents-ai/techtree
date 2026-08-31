"""What ``techtree proof verify`` puts in front of a person. Spec section 7.12.

Three hundred and thirty-nine checks run on an ordinary proof bundle, and every
one of them is named, in the machine contract, for the failure it would have
reported. That vocabulary is right for a caller that branches on it and wrong
for a reader being told that nothing is wrong: a person who is handed three
hundred rows headed ``signature_verification_failed``, each marked passed, has
been handed an alarm rather than an answer.

So this module tests the two halves of that separately, because they pull in
opposite directions.

*A proof that holds together is counted, never enumerated.* Its checks are
grouped under headings that say what was confirmed, the counts add up to every
check that ran, and no identifier and no error code reaches the page at all.
The full list is there for whoever asks for it, and it is named the same way.

*A proof that does not hold together is enumerated, whole.* Every failure keeps
its exact identifier and its exact code, verbatim, and gains the heading and
the subject that say where in the bundle the trouble is. A failing verification
is the one place more detail is always the right answer.
"""

from __future__ import annotations

import io
import re

import pytest
from rich.console import Console
from typer.testing import CliRunner

from techtree.cli.app import create_app
from techtree.cli.commands.proof import (
    _HEADINGS,
    ProofVerificationPayload,
    _grouped,
    _renderer,
)
from techtree.identity.models import VerificationMessage, VerificationStatus

ANSI = re.compile(r"\x1b\[[0-9;]*m")

# ---------------------------------------------------------------------------
# The checks a real bundle runs, in the shapes their identifiers really take
# ---------------------------------------------------------------------------

#: One of every identifier shape ``verify.py`` builds, taken from a verified
#: certification bundle. A shape this list forgets is a shape the headings
#: would silently sweep into "Other checks", so the census below reads the
#: headings back out and insists every one of them was exercised.
IDENTIFIER_SHAPES: tuple[str, ...] = (
    "bundle.payload_digest",
    "bundle.signature_key",
    "bundle.signature",
    "bundle.public_key",
    "bundle.root_report_digest",
    "artifact.campaign.json",
    "artifact.receipts/baseline/0000.json",
    "linkage.manifest_campaign",
    "linkage.taskset_membership",
    "receipt_set.baseline",
    "receipt_set.baseline.experiment",
    "receipts/baseline/0000.json.payload_digest",
    "receipts/baseline/0000.json.signature_key",
    "receipts/baseline/0000.json.signature",
    "uplift-report.payload_digest",
    "uplift-report.signature",
    "execution-record.signature_key",
    "execution_record.run",
    "execution_record.present",
    "aggregate.recomputed",
    "publication.not_requested",
    "publication.not_eligible",
    "p1.artifact_digests_verify",
    "p1.grade",
    "document.campaign.json",
    "identity.present",
)

SUMMARY: tuple[VerificationMessage, ...] = (
    VerificationMessage(
        id="integrity",
        status="passed",
        code="proof_bundle_invalid",
        detail="Cryptographic integrity: every file still matches what was signed.",
    ),
    VerificationMessage(
        id="independent_reproduction",
        status="warning",
        code="proof_bundle_invalid",
        detail="No independent reproduction: nobody else has run this comparison.",
    ),
)


def check(
    identifier: str,
    *,
    status: VerificationStatus = "passed",
    code: str = "proof_bundle_invalid",
    detail: str = "this part of the proof holds",
) -> VerificationMessage:
    return VerificationMessage(id=identifier, status=status, code=code, detail=detail)


def payload(
    checks: tuple[VerificationMessage, ...], *, verified: bool = True
) -> ProofVerificationPayload:
    return ProofVerificationPayload(
        target="/proofs/one",
        kind="bundle",
        verified=verified,
        summary=list(SUMMARY),
        checks=list(checks),
    )


def rendered(data: ProofVerificationPayload, *, every_check: bool = False) -> str:
    console = Console(
        file=io.StringIO(),
        width=100,
        no_color=True,
        highlight=False,
        emoji=False,
        markup=False,
    )
    _renderer(every_check=every_check)(data, console)
    text = console.file.getvalue()  # type: ignore[attr-defined]
    assert isinstance(text, str)
    return text


PASSING: tuple[VerificationMessage, ...] = tuple(
    check(identifier) for identifier in IDENTIFIER_SHAPES
)


# ---------------------------------------------------------------------------
# The headings account for every check
# ---------------------------------------------------------------------------


def test_every_check_lands_under_exactly_one_heading() -> None:
    """A count a reader cannot add up is a count they cannot trust."""
    grouped = _grouped(PASSING)

    counted = [message for _, checks in grouped for message in checks]
    assert len(counted) == len(PASSING)
    assert {message.id for message in counted} == set(IDENTIFIER_SHAPES)


def test_the_headings_read_in_the_order_the_checks_were_run() -> None:
    assert [heading for heading, _ in _grouped(PASSING)] == [
        heading for heading, _ in _HEADINGS if heading != "Other checks"
    ]


def test_no_identifier_a_real_bundle_produces_falls_through_to_the_remainder() -> None:
    """The remainder heading is a promise that the counts add up, not a bin."""
    grouped = dict(_grouped(PASSING))

    assert "Other checks" not in grouped


def test_an_identifier_nobody_anticipated_is_still_counted() -> None:
    unknown = check("something.this.build.never.wrote")

    grouped = dict(_grouped((*PASSING, unknown)))

    assert [message.id for message in grouped["Other checks"]] == [unknown.id]


def test_no_heading_repeats_the_vocabulary_of_a_failure() -> None:
    """A passing row is named by what it confirmed, never by a failure code."""
    for heading, _ in _HEADINGS:
        assert "fail" not in heading.lower()
        assert "invalid" not in heading.lower()


# ---------------------------------------------------------------------------
# A proof that holds together
# ---------------------------------------------------------------------------


def test_a_verified_proof_prints_counts_rather_than_every_check() -> None:
    text = rendered(payload(PASSING))

    assert f"What was checked, {len(PASSING)} checks in all" in text
    assert "Signatures" in text
    assert "Stored file digests" in text
    # Twenty-six checks, and not twenty-six rows of them.
    assert text.count("PASSED") == 1  # the one passing line of the summary


@pytest.mark.parametrize("identifier", IDENTIFIER_SHAPES)
def test_a_verified_proof_names_no_check_identifier(identifier: str) -> None:
    assert identifier not in rendered(payload(PASSING))


def test_a_verified_proof_names_no_error_code() -> None:
    text = rendered(
        payload(
            tuple(
                check(identifier, code="signature_verification_failed")
                for identifier in IDENTIFIER_SHAPES
            )
        )
    )

    assert "signature_verification_failed" not in text


def test_a_heading_with_one_check_says_how_it_came_out() -> None:
    """A lone check reads better as "passed" than as a count of one."""
    text = " ".join(rendered(payload(PASSING)).split())

    assert "Aggregate recomputation passed" in text


def test_a_heading_with_several_checks_counts_them() -> None:
    text = rendered(payload(PASSING))
    counts = {
        line.split()[-1]
        for line in text.splitlines()
        if line.startswith("  Signatures")
    }

    assert counts == {"9/9"}


def test_the_full_list_is_offered_rather_than_printed() -> None:
    assert "--checks" in rendered(payload(PASSING))


def test_the_full_list_names_every_check_by_what_it_confirmed() -> None:
    detailed = tuple(
        check(identifier, detail=f"detail for {identifier}")
        for identifier in IDENTIFIER_SHAPES
    )

    text = " ".join(rendered(payload(detailed), every_check=True).split())

    for identifier in IDENTIFIER_SHAPES:
        assert f"detail for {identifier}" in text
    assert "Add --checks" not in text


def test_the_full_list_names_the_envelope_a_signature_check_was_about() -> None:
    """Thirty-six receipts report one sentence, so the sentence is not enough."""
    signatures = (
        check(
            "receipts/baseline/0007.json.signature",
            detail="the signature verifies against the public key carried with it",
        ),
    )

    text = " ".join(rendered(payload(signatures), every_check=True).split())

    assert "receipts/baseline/0007.json the signature verifies" in text


# ---------------------------------------------------------------------------
# A proof that does not
# ---------------------------------------------------------------------------


BROKEN_RECEIPT = check(
    "receipts/baseline/0003.json.payload_digest",
    status="failed",
    code="signature_verification_failed",
    detail="the payload no longer matches the digest it was signed under",
)
BROKEN_DIGEST = check(
    "artifact.receipts/baseline/0003.json",
    status="failed",
    code="proof_bundle_invalid",
    detail="receipts/baseline/0003.json has changed since the bundle was written",
)


def broken() -> ProofVerificationPayload:
    return payload((*PASSING, BROKEN_RECEIPT, BROKEN_DIGEST), verified=False)


def test_a_failure_keeps_its_identifier_and_its_code_verbatim() -> None:
    text = " ".join(rendered(broken()).split())

    for failure in (BROKEN_RECEIPT, BROKEN_DIGEST):
        assert f"check {failure.id}, reported as {failure.code}" in text
        assert failure.detail in text


def test_a_failure_says_where_in_the_proof_it_is() -> None:
    """The heading and the subject are what the old rendering did not say."""
    text = " ".join(rendered(broken()).split())

    assert "Signatures — receipts/baseline/0003.json" in text
    assert "Stored file digests — receipts/baseline/0003.json" in text


def test_the_failures_are_counted_against_everything_that_ran() -> None:
    text = rendered(broken())

    assert f"What failed, 2 of {len(PASSING) + 2} checks" in text


def test_a_heading_holding_a_failure_says_so_beside_its_count() -> None:
    text = " ".join(rendered(broken()).split())

    assert "Signatures 9/10 1 failed" in text


def test_a_warning_is_counted_without_being_called_a_failure() -> None:
    weakened = check(
        "execution_record.present",
        status="warning",
        code="operational_evidence_unavailable",
        detail="this bundle carries no comparison execution record",
    )
    others = tuple(
        message for message in PASSING if message.id != "execution_record.present"
    )

    text = " ".join(rendered(payload((*others, weakened))).split())

    assert "1 warning" in text
    assert "1 failed" not in text


def test_nothing_is_carried_by_colour_alone() -> None:
    """The same text, with colour switched off, still says what happened."""
    text = rendered(broken())

    assert "\x1b[" not in text
    assert "failed" in text


# ---------------------------------------------------------------------------
# The command surface
# ---------------------------------------------------------------------------


def test_the_full_list_has_a_flag_to_ask_for_it() -> None:
    result = CliRunner().invoke(create_app(), ["proof", "verify", "--help"])

    assert result.exit_code == 0
    assert "--checks" in ANSI.sub("", result.stdout)
