"""The sanitized improvement context. Spec sections 7.18 and 7.22.

Two questions are asked here and the first one matters more.

*What is not in it.* Spec section 11.5 names six categories of material a
context excludes, and the exclusion matrix below proves each one absent against
a context built from evidence that actually carries it. The subject's final
reply is the one worth reading closely: it is the participant's own text and
not the verifier's, but for a taskset scored by matching an answer, a reply the
subject got right *is* the expected answer, so it stays out and
``prohibited_material`` says so.

*Whether it is the same every time.* A context is derived rather than measured,
and a derived artifact that varied between two builds of one run would make the
loop it feeds unreproducible.

The evidence is the recorded probes of 2026-08-13 — real ``exact_match``
measurements of 0/2 against 2/2 — so the context under test describes something
that was measured.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest

from fixtures.receipts.pair import RecordedPair, recorded_pair, recorded_report
from techtree.canonical import canonical_json_bytes, digest_object
from techtree.errors import ValidationError
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.skill import SkillArtifact, SkillFile
from techtree.models.uplift_report import TaskDelta, UpliftReport
from techtree.uplift.context import (
    EXAMPLE_CONTRAST_LIMIT,
    EXAMPLE_LIMIT,
    PROHIBITED_MATERIAL,
    SkillImprovementContext,
    TaskPublicProjection,
    build_improvement_context,
)
from techtree.verifiers.models import NormalizedEpisode, VariantName

#: A hidden expected answer, spelled distinctively so a leak of it anywhere in
#: the context is unmistakable.
HIDDEN_ANSWER = "GOLDANSWER-4417-QQ"

#: What a grader's own material would look like if it reached this far.
GRADER_SOURCE = "def grade(reply): return reply == 'GOLDANSWER-4417-QQ'"


def parent_skill() -> SkillArtifact:
    """Return the Skill a context is built about."""
    return SkillArtifact(
        schema_version="techtree.skill.v1alpha1",
        name="branch-code-v1",
        root_digest=f"sha256:{'a' * 64}",
        archive_digest=f"sha256:{'b' * 64}",
        files=[
            SkillFile(
                path="SKILL.md",
                media_type="text/markdown",
                size=1024,
                digest=f"sha256:{'c' * 64}",
            )
        ],
        source_kind="manual",
        parent_skill_digest=None,
    )


@pytest.fixture(scope="module")
def pair() -> RecordedPair:
    return recorded_pair()


@pytest.fixture(scope="module")
def receipts(pair: RecordedPair) -> dict[VariantName, list[EpisodeReceipt]]:
    return {
        variant: pair.receipts(variant)
        for variant in (VariantName.BASELINE, VariantName.CANDIDATE)
    }


@pytest.fixture(scope="module")
def report(pair: RecordedPair) -> UpliftReport:
    return recorded_report(pair)


def build(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
    **overrides: object,
) -> SkillImprovementContext:
    """Build a context from the recorded evidence, with test overrides."""
    arguments: dict[str, object] = {
        "report": report,
        "candidate_receipts": receipts[VariantName.CANDIDATE],
        "baseline_receipts": receipts[VariantName.BASELINE],
        "campaign": pair.campaign,
        "parent_skill": parent_skill(),
    }
    arguments.update(overrides)
    return build_improvement_context(**arguments)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# What it says
# ---------------------------------------------------------------------------


def test_the_context_pins_the_run_the_campaign_and_the_skill(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """Spec section 7.22: the source Skill digest is pinned."""
    context = build(pair, receipts, report)

    assert context.schema_version == "techtree.skill-improvement-context.v1"
    assert context.source_run_id == report.run_id
    assert context.campaign_spec_digest == digest_object(pair.campaign)
    assert context.parent_skill_digest == parent_skill().root_digest
    assert context.data_policy_digest == report.data_policy_digest
    assert context.current_result == report.primary_result


def test_the_objective_names_the_reward_and_the_threshold(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """A model asked to improve something must be told against what."""
    context = build(pair, receipts, report)

    assert pair.primary_reward in context.objective
    assert f"{report.primary_result.candidate_mean:.3f}" in context.objective
    assert str(len(pair.ordered_task_hashes)) in context.objective


def test_a_context_cannot_be_built_from_another_campaigns_report(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """The report and the Campaign must be about one experiment."""
    other = pair.campaign.model_copy(
        update={
            "metadata": pair.campaign.metadata.model_copy(update={"version": 99}),
        }
    )

    with pytest.raises(ValidationError) as raised:
        build(pair, receipts, report, campaign=other)

    assert raised.value.code == "improvement_context_invalid"


# ---------------------------------------------------------------------------
# The exclusion matrix. Spec section 11.5, one test per excluded category.
# ---------------------------------------------------------------------------


def _rendered(context: SkillImprovementContext) -> str:
    """Return the exact bytes a consumer would be handed, as text."""
    return canonical_json_bytes(context).decode("utf-8")


def test_no_hidden_expected_answer_reaches_the_context(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """The evidence holds the answers; the shape gives them nowhere to go."""
    context = build(pair, receipts, report)
    evidence = json.dumps(
        [episode.model_dump(mode="json") for episode in _episodes(pair)]
    )

    # The recorded evidence really does carry the subject's own answers, so
    # this is a check against material that is present rather than absent.
    assert any(
        trace.last_reply for episode in _episodes(pair) for trace in episode.traces
    ), "the recorded evidence should carry replies for this test to mean anything"
    assert HIDDEN_ANSWER not in evidence  # the fixture answer, not the real one
    assert all(example.subject_reply is None for example in context.examples)
    for episode in _episodes(pair):
        for trace in episode.traces:
            if trace.last_reply:
                assert trace.last_reply not in _rendered(context)


def test_a_reply_offered_through_the_projection_seat_is_still_excluded(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """``subject_reply`` has no source in this build, and cannot acquire one."""
    context = build(
        pair,
        receipts,
        report,
        task_public_projection=lambda *, task_hash, position: TaskPublicProjection(
            task_label=f"task {position}",
            public_prompt=f"Answer the question. The answer is {HIDDEN_ANSWER}.",
        ),
    )

    # A caller who puts an answer in the *prompt* has leaked it into the
    # prompt, and that is the caller's projection to get right. What cannot
    # happen is a reply appearing: no code path assigns one.
    assert all(example.subject_reply is None for example in context.examples)


def test_no_grader_material_reaches_the_context(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """A grader's source has no field, and nothing in the shape resembles one."""
    rendered = _rendered(build(pair, receipts, report))

    assert GRADER_SOURCE not in rendered
    assert "def grade" not in rendered
    assert "reward_function" not in rendered


def test_no_sealed_task_content_reaches_the_context(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """A task is named by its committed hash, which the TasksetLock publishes."""
    context = build(pair, receipts, report)

    for example in context.examples:
        task_hash = example.task_hash
        assert task_hash in pair.ordered_task_hashes
        assert example.public_prompt is None
        assert task_hash.partition(":")[2][:8] in example.task_label


def test_no_provider_secret_reaches_the_context(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """A value that looks like a credential stops the context being produced."""
    with pytest.raises(ValidationError) as raised:
        build(
            pair,
            receipts,
            report,
            task_public_projection=lambda *, task_hash, position: TaskPublicProjection(
                task_label=f"task {position}",
                public_prompt="use sk-live-0123456789abcdefghijklmnopqrstuvwxyz",
            ),
        )

    assert raised.value.code == "improvement_context_forbidden_material"


def test_no_private_environment_value_reaches_the_context(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """No field carries environment, and the credential names never appear."""
    rendered = _rendered(build(pair, receipts, report))

    for name in ("TECHTREE_MODEL_API_KEY", "OPENAI_API_KEY", "Authorization"):
        assert name not in rendered


def test_no_unredacted_local_path_reaches_the_context(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """An absolute path is refused rather than shipped."""
    with pytest.raises(ValidationError) as raised:
        build(
            pair,
            receipts,
            report,
            task_public_projection=lambda *, task_hash, position: TaskPublicProjection(
                task_label=f"task {position}",
                public_prompt="see /Users/someone/techtree/runs/run_1/inputs",
            ),
        )

    assert raised.value.code == "improvement_context_forbidden_material"


def test_the_context_states_what_it_withholds(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """A consumer is told what it is not being given."""
    context = build(pair, receipts, report)

    assert list(context.prohibited_material) == list(PROHIBITED_MATERIAL)
    assert "subject final replies" in context.prohibited_material
    assert "hidden expected answers" in context.prohibited_material
    assert context.constraints, "a reviser is told what a revision may be"


# ---------------------------------------------------------------------------
# Determinism and selection
# ---------------------------------------------------------------------------


def test_two_builds_of_one_run_are_byte_identical(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """A derived artifact that varied would make the loop unreproducible."""
    first = canonical_json_bytes(build(pair, receipts, report))
    second = canonical_json_bytes(build(pair, receipts, report))

    assert first == second


def test_regressions_and_failures_come_before_anything_else(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """Spec section 7.18's selection order, over a synthesized spread."""
    context = build(pair, receipts, _with_deltas(report, _spread(report)))
    outcomes = [example.outcome for example in context.examples]

    assert outcomes[:2] == ["regressed", "regressed"]
    assert outcomes[2] == "stable_failure"
    assert outcomes.index("improved") > outcomes.index("stable_failure")
    assert outcomes.index("stable_success") > outcomes.index("improved")
    # Worst regression first, narrowest win first.
    regressions = _deltas(context, "regressed")
    assert regressions == sorted(regressions)
    wins = _deltas(context, "improved")
    assert wins == sorted(wins)


def test_stable_successes_are_only_a_small_contrast_sample(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """A context is about what did not work."""
    context = build(pair, receipts, _with_deltas(report, _spread(report)))

    successes = [
        example for example in context.examples if example.outcome == "stable_success"
    ]
    assert len(successes) <= EXAMPLE_CONTRAST_LIMIT


def test_a_long_run_is_bounded(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """A model has a finite window and the regressions must fit inside it."""
    many = [
        TaskDelta(
            task_hash=f"sha256:{position:064x}",
            baseline_reward=1.0,
            candidate_reward=0.0,
            delta=-1.0,
        )
        for position in range(EXAMPLE_LIMIT * 3)
    ]
    context = build(pair, receipts, _with_deltas(report, many))

    assert len(context.examples) == EXAMPLE_LIMIT
    assert all(example.outcome == "regressed" for example in context.examples)


def test_a_report_with_no_tasks_is_refused(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    report: UpliftReport,
) -> None:
    """There is nothing to improve against."""
    with pytest.raises(ValidationError) as raised:
        build(pair, receipts, _with_deltas(report, []))

    assert raised.value.code == "improvement_context_invalid"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _episodes(pair: RecordedPair) -> Sequence[NormalizedEpisode]:
    """Return the recorded candidate episodes, which carry the subject replies."""
    return pair.results[VariantName.CANDIDATE].episodes


def _deltas(context: SkillImprovementContext, outcome: str) -> list[float]:
    """Return the recorded margin of every example with one outcome, in order."""
    return [
        example.public_metrics["delta"] or 0.0
        for example in context.examples
        if example.outcome == outcome
    ]


def _spread(report: UpliftReport) -> list[TaskDelta]:
    """Return one task of every outcome, several of each, in committed order."""
    rows: list[tuple[float, float]] = [
        (1.0, 0.0),  # regressed, worst
        (1.0, 0.5),  # regressed, milder
        (0.0, 0.0),  # stable failure
        (0.0, 0.0),
        (0.0, 0.25),  # improved, narrowest
        (0.0, 1.0),  # improved, widest
        (1.0, 1.0),  # stable success
        (1.0, 1.0),
    ]
    return [
        TaskDelta(
            task_hash=f"sha256:{position:064x}",
            baseline_reward=baseline,
            candidate_reward=candidate,
            delta=candidate - baseline,
        )
        for position, (baseline, candidate) in enumerate(rows)
    ]


def _with_deltas(report: UpliftReport, deltas: list[TaskDelta]) -> UpliftReport:
    """Return the same report over a different set of paired tasks."""
    return report.model_construct(**{**dict(report), "task_deltas": deltas})
