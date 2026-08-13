"""What the engine actually resolved and ran. Spec section 7.8.

The two recorded variants are the ideal subject for this: they were executed
minutes apart, on the same machine, against the same model, image, harness and
sampling parameters, and exactly one thing was changed between them — the Skill
that was mounted. So the strongest assertion available is also the simplest
one: fingerprint both, and require the two to be identical everywhere the
mutation does not reach.

Where it reaches turns out to be two fields rather than one, and finding that
out is the sort of thing recorded evidence is for. Mounting a Skill also
changes one tool description, because the harness advertises the Skills it can
see inside its own ``skill_manage`` tool. That is measured here rather than
assumed either way.

The rest of the file provokes drift. Each edit changes one thing the two
sources are supposed to agree about, and each must be refused, because a
comparison whose two sides silently ran different configurations is not a
comparison.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from fixtures.receipts.support import RecordedVariant, recorded_variant
from techtree.canonical import digest_object
from techtree.errors import TechtreeError
from techtree.receipts.observed import (
    OBSERVED_CONFIGURATION_MISMATCH,
    ObservedSubjectConfiguration,
    observed_from_episodes,
    read_resolved_config,
)
from techtree.verifiers.models import VariantName


@pytest.fixture(params=[VariantName.BASELINE, VariantName.CANDIDATE])
def recorded(request: pytest.FixtureRequest) -> RecordedVariant:
    """Return one recorded variant's evaluation."""
    variant: VariantName = request.param
    return recorded_variant(variant)


def observed_of(
    recorded: RecordedVariant,
    *,
    resolved_config: dict[str, Any] | None = None,
) -> ObservedSubjectConfiguration:
    """Fingerprint one recorded variant."""
    return observed_from_episodes(
        recorded.episodes,
        resolved_config=(
            recorded.resolved_config if resolved_config is None else resolved_config
        ),
    )


# ---------------------------------------------------------------------------
# What was observed
# ---------------------------------------------------------------------------


def test_the_fingerprint_reports_what_the_evidence_records(
    recorded: RecordedVariant,
) -> None:
    """Every field is read off the traces and the resolved configuration."""
    trace = recorded.episodes[0].traces[0]
    observed = observed_of(recorded)

    assert observed.model_id == trace.model_id
    assert observed.harness_id == trace.harness_id
    assert observed.harness_version == trace.harness_version
    assert observed.use_bundled_skill is False
    assert observed.runtime_kind == "docker"
    assert observed.runtime_image == trace.runtime.image
    assert observed.runtime_image_digest == trace.runtime.resolved_image_digest
    assert observed.runtime_image_digest_source == trace.runtime.image_digest_source
    assert observed.verifiers_version == trace.verifiers_version
    assert observed.verifiers_revision == trace.verifiers_revision


def test_the_mounted_skills_are_read_back_by_content(
    recorded: RecordedVariant,
) -> None:
    """The mount directory is named after the skill, so it can be verified."""
    declared = recorded.experiment.configuration.agents["subject"].harness.skills
    observed = observed_of(recorded)

    assert observed.skill_root_digests == [skill.digest for skill in declared]


def test_only_the_skill_differed_between_the_two_recorded_variants() -> None:
    """The whole controlled comparison, stated as one assertion.

    Two fields move when a Skill is inserted, not one. The second is the tool
    inventory, and the reason is measured rather than assumed: see
    :func:`test_inserting_a_skill_changes_exactly_one_tool_description`.
    """
    baseline = observed_of(recorded_variant(VariantName.BASELINE))
    candidate = observed_of(recorded_variant(VariantName.CANDIDATE))

    assert baseline.skill_root_digests == []
    assert len(candidate.skill_root_digests) == 1
    assert (
        baseline.model_copy(
            update={
                "skill_root_digests": candidate.skill_root_digests,
                "tool_inventory_digest": candidate.tool_inventory_digest,
            }
        )
        == candidate
    )


def test_the_fingerprint_is_stable(recorded: RecordedVariant) -> None:
    """Same evidence, same fingerprint, so it can be compared by digest."""
    assert digest_object(observed_of(recorded)) == digest_object(observed_of(recorded))


def test_the_sampling_digest_follows_the_resolved_sampling(
    recorded: RecordedVariant,
) -> None:
    """Sampling is only in the resolved configuration, and it is committed to."""
    warmer = deepcopy(recorded.resolved_config)
    warmer["sampling"]["temperature"] = 0.7

    assert (
        observed_of(recorded, resolved_config=warmer).sampling_digest
        != observed_of(recorded).sampling_digest
    )


def test_both_variants_were_scored_under_the_same_reward_contract() -> None:
    """The same rewards, at the same weights, on both sides."""
    baseline = observed_of(recorded_variant(VariantName.BASELINE))
    candidate = observed_of(recorded_variant(VariantName.CANDIDATE))

    assert baseline.reward_contract_digest == candidate.reward_contract_digest


def test_inserting_a_skill_changes_exactly_one_tool_description() -> None:
    """A measured fact about Hermes, pinned here because it looks like drift.

    Inserting a Skill changes the subject's tool surface. Hermes 0.19.0 renders
    the index of available Skills into the description of its ``skill_manage``
    tool, so a candidate that mounts one is offered the same fifteen tools by
    the same names, with one of their descriptions different. The recorded
    probes show it: every other description and every parameter schema is
    byte-identical across the two variants.

    It is stated as a test rather than left as a surprise because a controlled
    comparison that required identical tool inventories would reject a
    perfectly controlled run, and the honest reading is that the tool
    inventory is downstream of the mutation rather than independent of it.
    """
    inventories = {
        variant.value: {
            tool.name: (tool.description_digest, tool.parameters_digest)
            for tool in recorded_variant(variant).episodes[0].traces[0].tools
        }
        for variant in (VariantName.BASELINE, VariantName.CANDIDATE)
    }
    baseline, candidate = inventories["baseline"], inventories["candidate"]

    assert sorted(baseline) == sorted(candidate)
    differing = sorted(name for name in baseline if baseline[name] != candidate[name])
    assert differing == ["skill_manage"]
    assert baseline["skill_manage"][1] == candidate["skill_manage"][1], (
        "only the description moved; the parameter schema is the same"
    )


# ---------------------------------------------------------------------------
# Drift
# ---------------------------------------------------------------------------


def test_rollouts_that_ran_different_models_are_refused(
    recorded: RecordedVariant,
) -> None:
    """One variant is one configuration executed many times."""
    first, *rest = recorded.episodes
    if not rest:
        pytest.skip("this recorded variant has one episode, so it cannot drift")
    drifted = first.model_copy(
        update={
            "traces": [first.traces[0].model_copy(update={"model_id": "other/model"})]
        }
    )

    with pytest.raises(TechtreeError) as failure:
        observed_from_episodes(
            [drifted, *rest], resolved_config=recorded.resolved_config
        )

    assert failure.value.code == OBSERVED_CONFIGURATION_MISMATCH
    assert failure.value.details["field"] == "model"


def test_rollouts_that_ran_different_images_are_refused(
    recorded: RecordedVariant,
) -> None:
    """A second container image is a second experiment."""
    first, *rest = recorded.episodes
    if not rest:
        pytest.skip("this recorded variant has one episode, so it cannot drift")
    elsewhere = first.traces[0].runtime.model_copy(update={"image": "python:3.12-slim"})
    drifted = first.model_copy(
        update={"traces": [first.traces[0].model_copy(update={"runtime": elsewhere})]}
    )

    with pytest.raises(TechtreeError) as failure:
        observed_from_episodes(
            [drifted, *rest], resolved_config=recorded.resolved_config
        )

    assert failure.value.code == OBSERVED_CONFIGURATION_MISMATCH


def test_a_configuration_that_resolved_a_different_model_is_refused(
    recorded: RecordedVariant,
) -> None:
    """What the engine understood and what the runtime did must agree."""
    other = deepcopy(recorded.resolved_config)
    other["model"] = "someone/else"

    with pytest.raises(TechtreeError) as failure:
        observed_of(recorded, resolved_config=other)

    assert failure.value.code == OBSERVED_CONFIGURATION_MISMATCH
    assert failure.value.details["field"] == "model"


def test_a_configuration_that_mounted_a_different_skill_is_refused() -> None:
    """The strongest check available: the mount is compared to the declaration."""
    recorded = recorded_variant(VariantName.CANDIDATE)
    substituted = deepcopy(recorded.resolved_config)
    substituted["env"]["subject"]["harness"]["skills"] = [f"/tmp/sha256-{'cd' * 32}"]

    with pytest.raises(TechtreeError) as failure:
        observed_of(recorded, resolved_config=substituted)

    assert failure.value.code == OBSERVED_CONFIGURATION_MISMATCH


def test_a_skill_mounted_from_a_directory_that_is_not_its_content_is_refused() -> None:
    """A folder named by a person is a folder nobody can verify."""
    recorded = recorded_variant(VariantName.CANDIDATE)
    renamed = deepcopy(recorded.resolved_config)
    renamed["env"]["subject"]["harness"]["skills"] = ["/tmp/my-favourite-skill"]

    with pytest.raises(TechtreeError) as failure:
        observed_of(recorded, resolved_config=renamed)

    assert failure.value.code == OBSERVED_CONFIGURATION_MISMATCH
    assert failure.value.details["directory"] == "my-favourite-skill"


def test_a_configuration_without_a_subject_seat_is_refused(
    recorded: RecordedVariant,
) -> None:
    """Without the named seat there is no evaluation of a subject."""
    seatless = deepcopy(recorded.resolved_config)
    del seatless["env"]["subject"]

    with pytest.raises(TechtreeError) as failure:
        observed_of(recorded, resolved_config=seatless)

    assert failure.value.code == OBSERVED_CONFIGURATION_MISMATCH


def test_a_configuration_without_sampling_is_refused(
    recorded: RecordedVariant,
) -> None:
    """How the subject was sampled is part of what it means to have run it."""
    unsampled = deepcopy(recorded.resolved_config)
    del unsampled["sampling"]

    with pytest.raises(TechtreeError) as failure:
        observed_of(recorded, resolved_config=unsampled)

    assert failure.value.code == OBSERVED_CONFIGURATION_MISMATCH


def test_no_episodes_means_no_observed_configuration(
    recorded: RecordedVariant,
) -> None:
    """Nothing ran, so nothing can be said about what ran."""
    with pytest.raises(TechtreeError) as failure:
        observed_from_episodes([], resolved_config=recorded.resolved_config)

    assert failure.value.code == OBSERVED_CONFIGURATION_MISMATCH


# ---------------------------------------------------------------------------
# Reading the resolved configuration
# ---------------------------------------------------------------------------


def test_the_recorded_configuration_reads_back(recorded: RecordedVariant) -> None:
    """The configuration the engine wrote is TOML this code can read."""
    document = read_resolved_config(recorded.resolved_config_path)

    assert document["push"] is False
    assert document["env"]["subject"]["harness"]["id"] == "hermes-agent"


def test_an_unreadable_configuration_is_refused(tmp_path: Path) -> None:
    """A configuration that cannot be read cannot establish what ran."""
    with pytest.raises(TechtreeError) as failure:
        read_resolved_config(tmp_path / "config.toml")

    assert failure.value.code == OBSERVED_CONFIGURATION_MISMATCH
