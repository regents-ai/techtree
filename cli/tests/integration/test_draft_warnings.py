"""What the approval screen tells a person about how their money is spent.

A draft's warnings are the last thing a participant reads before authorising a
paid comparison, and one of them describes how the comparison is controlled:
whether the two sides run one after the other or at the same time. That
sentence used to be written out by hand, and it said the baseline runs first
and the candidate second. The Campaign this release ships runs them side by
side, so the sentence was false at the exact moment it mattered most.

The fix is that the sentence is read off the Campaign, and this module is what
holds it to that. What it checks is a property, not a wording: a draft prepared
from a Campaign that runs its two sides at the same time must not claim an
order, and a draft prepared from a Campaign that runs them in turn must not
claim simultaneity. Rewriting the copy in better words is free; describing the
wrong Campaign is not.

The two catalogs these tests prepare against are the committed synthetic
catalog rebuilt with one field changed — how the two sides are run — so a
failure can only ever be about that field.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Final

import pytest

from fixtures.drafts.support import (
    VALID_SKILL,
    catalog_fixture_builder,
    preparation_service,
)
from techtree.canonical import digest_object
from techtree.models.campaign import CampaignSpec, ExecutionSpec, VariantSchedule
from techtree.paths import paths_from_root
from techtree.skills.service import _comparison_warning
from techtree.verifiers.compiler import divide_concurrency

pytestmark = pytest.mark.integration

#: The Climb the drafts are prepared from. Its Campaign is the one being
#: varied; the Climb itself is the committed fixture's development wrapper.
CLIMB_REFERENCE: Final = "synthetic-development"

#: Enough permits for both sides to be live at once, so that neither Campaign
#: under test is one no executor would accept. The same value is used for both
#: so that the only difference between them is how the two sides are run.
CONCURRENCY_PERMITS: Final = 2

#: Ways a sentence can claim the two sides were running at the same time.
TOGETHER: Final[tuple[str, ...]] = (
    "in parallel",
    "at the same time",
    "side by side",
    "simultaneously",
    "together",
    "alongside",
)

#: Ways a sentence can claim one side ran and then the other.
IN_TURN: Final[tuple[str, ...]] = (
    "first",
    "second",
    "then",
    "after",
    "before",
    "one after",
    "in turn",
)


def claims(sentence: str, phrases: Iterable[str]) -> list[str]:
    """Return the claim phrases the sentence actually makes."""
    lowered = sentence.lower()
    return [
        phrase
        for phrase in phrases
        if re.search(rf"\b{re.escape(phrase)}\b", lowered) is not None
    ]


def campaign_running(order: VariantSchedule) -> CampaignSpec:
    """Return the synthetic Campaign, running its two sides the given way."""
    builder: Any = catalog_fixture_builder()
    lock = builder.build_taskset_lock()
    evidence = builder.build_validation_evidence(lock)
    campaign: CampaignSpec = builder.build_campaign(
        lock=lock,
        validation_receipt_digest=digest_object(
            builder.build_validation_receipt(lock, evidence)
        ),
        data_policy_digest=digest_object(builder.build_data_policy()),
    )
    return campaign.model_copy(
        update={
            "execution": ExecutionSpec(
                order=order,
                max_concurrent=CONCURRENCY_PERMITS,
                timeout_seconds=campaign.execution.timeout_seconds,
                retry_limit=campaign.execution.retry_limit,
            )
        }
    )


def catalog_running(destination: Path, order: VariantSchedule) -> None:
    """Write the synthetic catalog whose Campaign runs its two sides that way."""
    builder: Any = catalog_fixture_builder()
    data_policy = builder.build_data_policy()
    lock = builder.build_taskset_lock()
    evidence = builder.build_validation_evidence(lock)
    receipt = builder.build_validation_receipt(lock, evidence)
    campaign = campaign_running(order)

    builder.write_catalog(
        destination,
        climbs={
            f"climbs/{slug}.json": builder.build_climb(
                campaign_digest=digest_object(campaign),
                slug=slug,
                status=status,
                proof_grade=proof_grade,
            )
            for slug, status, proof_grade in builder.CLIMB_VARIANTS
        },
        objects=[
            builder.CatalogFile(
                kind="campaign", path=builder.CAMPAIGN_PATH, model=campaign
            ),
            builder.CatalogFile(
                kind="data_policy", path=builder.DATA_POLICY_PATH, model=data_policy
            ),
            builder.CatalogFile(
                kind="taskset_validation", path=builder.RECEIPT_PATH, model=receipt
            ),
            builder.CatalogFile(
                kind="validation_evidence", path=builder.EVIDENCE_PATH, model=evidence
            ),
        ],
    )


def comparison_sentence(home: Path, order: VariantSchedule) -> str:
    """Prepare a real draft and return what it says about the two sides.

    The sentence is found rather than indexed: it is the warning that talks
    about the baseline and the candidate. Nothing here depends on how the
    warnings are ordered or on how many of them there are.
    """
    catalog = home / "catalog"
    catalog_running(catalog, order)
    paths = paths_from_root(home / "techtree")
    service, _ = preparation_service(paths, catalog_root=catalog)
    prepared = service.prepare(
        climb_reference=CLIMB_REFERENCE,
        skill_path=VALID_SKILL,
        candidate_label="candidate-under-test",
    )
    about_both = [
        warning
        for warning in prepared.draft.warnings
        if "baseline" in warning.lower() and "candidate" in warning.lower()
    ]
    assert len(about_both) == 1, about_both
    return about_both[0]


def test_a_parallel_campaign_never_promises_an_order(tmp_path: Path) -> None:
    """A Campaign that runs both sides at once must not claim a running order."""
    sentence = comparison_sentence(tmp_path, VariantSchedule.PARALLEL)

    assert claims(sentence, TOGETHER), sentence
    assert claims(sentence, IN_TURN) == [], sentence


def test_a_sequential_campaign_never_promises_simultaneity(tmp_path: Path) -> None:
    """A Campaign that runs one side then the other must say so, and only so."""
    sentence = comparison_sentence(tmp_path, VariantSchedule.SEQUENTIAL)

    assert claims(sentence, IN_TURN), sentence
    assert claims(sentence, TOGETHER) == [], sentence


def test_the_sentence_agrees_with_how_the_permits_are_divided() -> None:
    """Tie the claim to machinery that also has to be right for a run to work.

    The executor divides the Campaign's concurrency permits between the two
    sides when and only when both are live at once; when they take turns each
    gets the whole allowance. So the division answers "are both sides running
    together?" from execution machinery rather than from the copy, and the
    sentence has to agree with it.
    """
    for order in VariantSchedule:
        campaign = campaign_running(order)
        baseline, candidate = divide_concurrency(
            campaign.execution.order, campaign.execution.max_concurrent
        )
        both_live_at_once = baseline + candidate <= campaign.execution.max_concurrent
        sentence = _comparison_warning(campaign)

        assert bool(claims(sentence, TOGETHER)) is both_live_at_once, sentence
        assert bool(claims(sentence, IN_TURN)) is not both_live_at_once, sentence


def test_every_way_of_running_a_comparison_gets_its_own_sentence() -> None:
    """No two ways of running the two sides may share a description.

    Exhaustiveness itself is enforced by the type checker — a Campaign that
    grows a third way of running its sides fails to typecheck in the service.
    What this adds is that none of them may quietly borrow another's sentence.
    """
    sentences = {
        _comparison_warning(campaign_running(order)) for order in VariantSchedule
    }

    assert len(sentences) == len(VariantSchedule)
