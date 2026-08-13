"""Turning one resolved experiment into one evaluation. Spec section 6.8.

The compiler is a translation, so the tests come in two kinds. The first kind
asks whether the translation is faithful and repeatable: the same manifest, the
same paths, the same bytes, with every Campaign value landing where the engine
will read it. The second kind asks whether a manifest that disagrees with its
Campaign is refused rather than reconciled, because a compiler that quietly
splits the difference between two documents produces a run nobody can interpret
afterwards.

The Campaign under test is the complete synthetic one from the catalog fixture,
for the same reason the manifest-builder tests use it: it is the object the CLI
actually resolves, including the fields nobody thinks about.
"""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fixtures.drafts.support import SyntheticGraph, synthetic_graph
from techtree.canonical import digest_object
from techtree.constants import SKILL_SCHEMA_VERSION
from techtree.errors import ConflictError, ValidationError
from techtree.manifests.builder import (
    build_baseline_manifest,
    build_candidate_manifest,
    skill_content_digest,
)
from techtree.models.campaign import CampaignSpec, VariantSchedule
from techtree.models.experiment import ExperimentManifest
from techtree.models.skill import SkillArtifact, SkillFile
from techtree.verifiers.compiler import (
    EVAL_CONFIG_MEDIA_TYPE,
    compile_plans,
    compile_variant_config,
    divide_concurrency,
    skill_directory_name,
    write_variant_config,
)
from techtree.verifiers.config import config_to_toml_bytes
from techtree.verifiers.models import RunPaths, VariantName

PINNED_TIME = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def graph() -> SyntheticGraph:
    return synthetic_graph()


@pytest.fixture
def run_paths(tmp_path: Path) -> RunPaths:
    return RunPaths(root=tmp_path / "runs" / "run_synthetic")


def candidate_skill() -> SkillArtifact:
    """Return a small candidate skill with a content-addressed root."""
    files = [
        SkillFile(
            path="SKILL.md",
            media_type="text/markdown",
            size=64,
            digest=f"sha256:{'a' * 64}",
        )
    ]
    return SkillArtifact(
        schema_version=SKILL_SCHEMA_VERSION,
        name="branch-code-procedure",
        root_digest=skill_content_digest(files),
        archive_digest=f"sha256:{'c' * 64}",
        files=files,
        source_kind="manual",
        parent_skill_digest=None,
    )


def manifests(graph: SyntheticGraph) -> tuple[ExperimentManifest, ExperimentManifest]:
    """Return the baseline and candidate the run would execute."""
    baseline = build_baseline_manifest(
        campaign=graph.campaign,
        campaign_digest=graph.campaign_digest,
        public_context=graph.public_context,
        created_at=PINNED_TIME,
    )
    candidate = build_candidate_manifest(
        campaign=graph.campaign,
        campaign_digest=graph.campaign_digest,
        skill=candidate_skill(),
        public_context=graph.public_context,
        created_at=PINNED_TIME,
    )
    return baseline, candidate


# ---------------------------------------------------------------------------
# A faithful translation
# ---------------------------------------------------------------------------


def test_the_campaign_values_land_where_the_engine_reads_them(
    graph: SyntheticGraph, run_paths: RunPaths
) -> None:
    baseline, _ = manifests(graph)
    subject = graph.campaign.subject

    config = compile_variant_config(
        campaign=graph.campaign,
        experiment=baseline,
        run_paths=run_paths,
        variant=VariantName.BASELINE,
        variant_max_concurrent=1,
    )

    assert config.model == subject.model.model_id
    assert config.client.api_key_var == subject.model.credential_env
    assert config.sampling.temperature == subject.sampling.temperature
    assert config.sampling.max_tokens == subject.sampling.max_tokens
    assert config.env.taskset.id == graph.campaign.taskset.ref.id
    assert config.env.subject.harness.version == subject.harness.version
    assert config.env.subject.runtime.image == subject.runtime.image
    assert config.env.subject.runtime.cpu == subject.runtime.cpu
    assert config.env.subject.runtime.memory == subject.runtime.memory_gb
    assert config.num_tasks == graph.campaign.taskset.selection.num_tasks
    assert config.output_dir == str(run_paths.variant_output_dir(VariantName.BASELINE))


def test_a_restricted_campaign_runtime_compiles_to_framework_only_egress(
    graph: SyntheticGraph, run_paths: RunPaths
) -> None:
    # Upstream's Docker default is unrestricted, so a Campaign that says
    # "restricted" only means something if the compiler says so explicitly.
    assert graph.campaign.subject.runtime.network_policy == "restricted"
    baseline, _ = manifests(graph)

    config = compile_variant_config(
        campaign=graph.campaign,
        experiment=baseline,
        run_paths=run_paths,
        variant=VariantName.BASELINE,
        variant_max_concurrent=1,
    )

    # Upstream rewrites an empty allow-list to this pair, so the compiler emits
    # the rewritten form and the two documents agree at every key.
    assert config.env.subject.runtime.allow == []
    assert config.env.subject.runtime.block == ["*"]
    assert config.env.subject.runtime.network_is_restricted is True


def test_the_baseline_mounts_no_skill_and_the_candidate_mounts_exactly_one(
    graph: SyntheticGraph, run_paths: RunPaths
) -> None:
    baseline_manifest, candidate_manifest = manifests(graph)
    skill = candidate_skill()

    baseline = compile_variant_config(
        campaign=graph.campaign,
        experiment=baseline_manifest,
        run_paths=run_paths,
        variant=VariantName.BASELINE,
        variant_max_concurrent=1,
    )
    candidate = compile_variant_config(
        campaign=graph.campaign,
        experiment=candidate_manifest,
        run_paths=run_paths,
        variant=VariantName.CANDIDATE,
        variant_max_concurrent=1,
    )

    assert baseline.env.subject.harness.skills == []
    assert candidate.env.subject.harness.skills == [
        str(run_paths.skill_files_dir / skill_directory_name(skill.root_digest))
    ]


def test_the_only_difference_between_the_two_documents_is_the_skill_list(
    graph: SyntheticGraph, run_paths: RunPaths
) -> None:
    baseline_manifest, candidate_manifest = manifests(graph)
    baseline = tomllib.loads(
        config_to_toml_bytes(
            compile_variant_config(
                campaign=graph.campaign,
                experiment=baseline_manifest,
                run_paths=run_paths,
                variant=VariantName.BASELINE,
                variant_max_concurrent=1,
            )
        ).decode("utf-8")
    )
    candidate = tomllib.loads(
        config_to_toml_bytes(
            compile_variant_config(
                campaign=graph.campaign,
                experiment=candidate_manifest,
                run_paths=run_paths,
                variant=VariantName.CANDIDATE,
                variant_max_concurrent=1,
            )
        ).decode("utf-8")
    )

    # The output directory is per variant by construction; normalize it away so
    # the comparison is about the experiment rather than about bookkeeping.
    baseline["output_dir"] = candidate["output_dir"] = ""
    baseline_skills = baseline["env"]["subject"]["harness"].pop("skills")
    candidate_skills = candidate["env"]["subject"]["harness"].pop("skills")

    assert baseline == candidate
    assert baseline_skills == []
    assert len(candidate_skills) == 1


def test_the_same_manifest_always_compiles_to_the_same_bytes(
    graph: SyntheticGraph, run_paths: RunPaths
) -> None:
    baseline, _ = manifests(graph)
    compile_once = compile_variant_config(
        campaign=graph.campaign,
        experiment=baseline,
        run_paths=run_paths,
        variant=VariantName.BASELINE,
        variant_max_concurrent=1,
    )
    compile_again = compile_variant_config(
        campaign=graph.campaign,
        experiment=baseline,
        run_paths=run_paths,
        variant=VariantName.BASELINE,
        variant_max_concurrent=1,
    )

    assert config_to_toml_bytes(compile_once) == config_to_toml_bytes(compile_again)


def test_no_credential_value_reaches_the_compiled_bytes(
    graph: SyntheticGraph, run_paths: RunPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "sk-compiler-unit-test-secret"
    monkeypatch.setenv(graph.campaign.subject.model.credential_env, secret)
    baseline, _ = manifests(graph)

    data = config_to_toml_bytes(
        compile_variant_config(
            campaign=graph.campaign,
            experiment=baseline,
            run_paths=run_paths,
            variant=VariantName.BASELINE,
            variant_max_concurrent=1,
        )
    )

    assert secret.encode("utf-8") not in data
    assert graph.campaign.subject.model.credential_env.encode("utf-8") in data


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def test_a_manifest_from_a_different_campaign_is_refused(
    graph: SyntheticGraph, run_paths: RunPaths
) -> None:
    baseline, _ = manifests(graph)
    other = _with_primary_reward(graph.campaign, "some_other_reward")

    with pytest.raises(ValidationError) as caught:
        compile_variant_config(
            campaign=other,
            experiment=baseline,
            run_paths=run_paths,
            variant=VariantName.BASELINE,
            variant_max_concurrent=1,
        )
    assert caught.value.code == "manifest_not_compilable"


def test_a_manifest_compiled_under_the_other_variants_name_is_refused(
    graph: SyntheticGraph, run_paths: RunPaths
) -> None:
    baseline, _ = manifests(graph)

    with pytest.raises(ValidationError) as caught:
        compile_variant_config(
            campaign=graph.campaign,
            experiment=baseline,
            run_paths=run_paths,
            variant=VariantName.CANDIDATE,
            variant_max_concurrent=1,
        )
    assert caught.value.code == "manifest_not_compilable"


def test_a_harness_wp6_cannot_execute_is_refused(
    graph: SyntheticGraph, run_paths: RunPaths
) -> None:
    campaign = _with_harness_id(graph.campaign, "bash")
    baseline = build_baseline_manifest(
        campaign=campaign,
        campaign_digest=digest_object(campaign),
        public_context=graph.public_context,
        created_at=PINNED_TIME,
    )

    with pytest.raises(ValidationError) as caught:
        compile_variant_config(
            campaign=campaign,
            experiment=baseline,
            run_paths=run_paths,
            variant=VariantName.BASELINE,
            variant_max_concurrent=1,
        )
    assert caught.value.code == "manifest_not_compilable"


def _with_harness_id(campaign: CampaignSpec, harness_id: str) -> CampaignSpec:
    """Return the same Campaign with the subject running another harness."""
    subject = campaign.subject
    harness = subject.harness.model_copy(update={"id": harness_id})
    return campaign.model_copy(
        update={"agents": {"subject": subject.model_copy(update={"harness": harness})}}
    )


def _with_primary_reward(campaign: CampaignSpec, reward: str) -> CampaignSpec:
    """Return a Campaign that is the same experiment scored differently."""
    scoring = campaign.scoring.model_copy(update={"primary_reward": reward})
    return campaign.model_copy(update={"scoring": scoring})


# ---------------------------------------------------------------------------
# Concurrency and plans
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("total", "expected"),
    [(2, (1, 1)), (3, (1, 2)), (4, (2, 2)), (7, (3, 4)), (8, (4, 4))],
)
def test_a_parallel_schedule_divides_the_campaign_bound(
    total: int, expected: tuple[int, int]
) -> None:
    assert divide_concurrency(VariantSchedule.PARALLEL, total) == expected
    assert sum(expected) == total


def test_a_sequential_schedule_gives_each_variant_the_whole_allowance() -> None:
    assert divide_concurrency(VariantSchedule.SEQUENTIAL, 5) == (5, 5)


def test_a_parallel_schedule_needs_a_permit_for_each_variant() -> None:
    with pytest.raises(ValidationError) as caught:
        divide_concurrency(VariantSchedule.PARALLEL, 1)
    assert caught.value.code == "manifest_not_compilable"


def test_both_plans_describe_run_owned_paths(
    graph: SyntheticGraph, run_paths: RunPaths
) -> None:
    baseline_manifest, candidate_manifest = manifests(graph)

    baseline, candidate = compile_plans(
        campaign=graph.campaign,
        baseline=baseline_manifest,
        candidate=candidate_manifest,
        run_paths=run_paths,
    )

    for plan in (baseline, candidate):
        assert Path(plan.verifiers_input_config_path).is_relative_to(run_paths.root)
        assert Path(plan.verifiers_output_dir).is_relative_to(run_paths.root)
        assert Path(plan.experiment_manifest_path).is_relative_to(run_paths.root)
        assert plan.task_count == graph.campaign.taskset.selection.num_tasks
    assert baseline.variant is VariantName.BASELINE
    assert candidate.variant is VariantName.CANDIDATE
    assert baseline.skill_paths == []
    assert len(candidate.skill_paths) == 1


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def test_a_written_config_is_hashed_from_the_bytes_on_disk(
    graph: SyntheticGraph, run_paths: RunPaths
) -> None:
    baseline, _ = manifests(graph)
    config = compile_variant_config(
        campaign=graph.campaign,
        experiment=baseline,
        run_paths=run_paths,
        variant=VariantName.BASELINE,
        variant_max_concurrent=1,
    )
    destination = run_paths.variant_input_config(VariantName.BASELINE)

    reference = write_variant_config(config, destination)

    data = destination.read_bytes()
    assert reference.size == len(data)
    assert reference.media_type == EVAL_CONFIG_MEDIA_TYPE
    assert data == config_to_toml_bytes(config)


def test_a_compiled_config_is_never_silently_overwritten(
    graph: SyntheticGraph, run_paths: RunPaths
) -> None:
    baseline, _ = manifests(graph)
    config = compile_variant_config(
        campaign=graph.campaign,
        experiment=baseline,
        run_paths=run_paths,
        variant=VariantName.BASELINE,
        variant_max_concurrent=1,
    )
    destination = run_paths.variant_input_config(VariantName.BASELINE)
    write_variant_config(config, destination)

    with pytest.raises(ConflictError):
        write_variant_config(config, destination)
