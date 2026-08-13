"""Compiling the shipped Campaign and asking the real engine. Spec §6.8, §6.14.

This module joins the two halves WP6a builds. The first half is pure: take the
Campaign this build actually ships, derive both variants, and compile each into
the strict evaluation configuration — twice, to prove the bytes do not move.
The second half is not pure at all: it installs the real managed engine and
hands it those bytes with ``--dry-run``, so the pinned Verifiers build gives its
own verdict rather than Techtree checking its own homework.

The install downloads the pinned Verifiers commit, so the module is marked
``integration`` and excluded from the default run::

    uv run pytest tests/integration/test_eval_compile.py -m integration

The dry-run half is gated on the installed engine actually exposing the
named-subject environment spec section 6.5 requires. It does not yet: the
shipped reference package exports a taskset and no environment, so a compiled
``[env.subject]`` table is rejected at parse time
(``docs/verifiers-eval.md``, finding E0). That is a frozen-bundle change and a
STOP-AND-NOTE on the WP6a ticket, not something this module can route around.
The gate is a probe of the engine rather than a hard-coded skip, so the tests
start running the moment the bundle carries the environment.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from techtree.canonical import digest_object
from techtree.catalog.repository import EmbeddedCatalogRepository
from techtree.constants import SKILL_SCHEMA_VERSION
from techtree.engines.installer import EngineInstaller, find_uv
from techtree.engines.registry import EngineRegistry
from techtree.engines.runner import EngineRunner
from techtree.manifests.builder import (
    build_baseline_manifest,
    build_candidate_manifest,
    skill_content_digest,
)
from techtree.models.campaign import CampaignSpec
from techtree.models.engine import EngineStatus
from techtree.models.skill import SkillArtifact, SkillFile
from techtree.paths import TechtreePaths, ensure_path_layout, paths_from_root
from techtree.settings import Settings
from techtree.verifiers.compiler import (
    compile_plans,
    compile_variant_config,
    write_variant_config,
)
from techtree.verifiers.config import EvalToml, config_to_toml_bytes
from techtree.verifiers.credentials import credential_status
from techtree.verifiers.models import RunPaths, VariantName
from techtree.verifiers.verify import dry_run_variant_config

pytestmark = pytest.mark.integration

DEV_CLIMB = "procedure-transfer-dev"
PINNED_TIME = datetime(2026, 1, 1, tzinfo=UTC)
SUBJECT_SEAT = "subject"


# ---------------------------------------------------------------------------
# The shipped Campaign, compiled
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def campaign() -> CampaignSpec:
    """The Campaign this build ships, read from the packaged catalog."""
    repository = EmbeddedCatalogRepository.packaged()
    climb = repository.load_climb(DEV_CLIMB)
    return repository.load_campaign(climb.campaign_spec_digest)


@pytest.fixture(scope="module")
def candidate_skill() -> SkillArtifact:
    """A small candidate skill, identified the way a prepared draft would be."""
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


def compile_both(
    campaign: CampaignSpec, skill: SkillArtifact, run_paths: RunPaths
) -> dict[VariantName, EvalToml]:
    """Compile both variants of the shipped Campaign."""
    digest = digest_object(campaign)
    manifests = {
        VariantName.BASELINE: build_baseline_manifest(
            campaign=campaign,
            campaign_digest=digest,
            public_context=None,
            created_at=PINNED_TIME,
        ),
        VariantName.CANDIDATE: build_candidate_manifest(
            campaign=campaign,
            campaign_digest=digest,
            skill=skill,
            public_context=None,
            created_at=PINNED_TIME,
        ),
    }
    return {
        variant: compile_variant_config(
            campaign=campaign,
            experiment=manifest,
            run_paths=run_paths,
            variant=variant,
            variant_max_concurrent=1,
        )
        for variant, manifest in manifests.items()
    }


def test_both_variants_of_the_shipped_campaign_compile(
    campaign: CampaignSpec, candidate_skill: SkillArtifact, tmp_path: Path
) -> None:
    run_paths = RunPaths(root=tmp_path / "runs" / "run_dev")

    configs = compile_both(campaign, candidate_skill, run_paths)

    for variant, config in configs.items():
        assert config.env.taskset.id == campaign.taskset.ref.id
        assert config.num_tasks == campaign.taskset.selection.num_tasks
        assert config.push is False
        assert config.rich is False
        assert config.shuffle is False
        assert config.num_rollouts == 1
        assert config.output_dir == str(run_paths.variant_output_dir(variant))
    assert configs[VariantName.BASELINE].env.subject.harness.skills == []
    assert len(configs[VariantName.CANDIDATE].env.subject.harness.skills) == 1


def test_the_shipped_campaign_compiles_to_the_same_bytes_every_time(
    campaign: CampaignSpec, candidate_skill: SkillArtifact, tmp_path: Path
) -> None:
    run_paths = RunPaths(root=tmp_path / "runs" / "run_dev")

    first = compile_both(campaign, candidate_skill, run_paths)
    second = compile_both(campaign, candidate_skill, run_paths)

    for variant in VariantName:
        assert config_to_toml_bytes(first[variant]) == config_to_toml_bytes(
            second[variant]
        )


def test_no_credential_value_appears_in_either_compiled_document(
    campaign: CampaignSpec,
    candidate_skill: SkillArtifact,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "sk-integration-test-secret"
    monkeypatch.setenv(campaign.subject.model.credential_env, secret)
    run_paths = RunPaths(root=tmp_path / "runs" / "run_dev")

    configs = compile_both(campaign, candidate_skill, run_paths)

    for config in configs.values():
        data = config_to_toml_bytes(config)
        assert secret.encode("utf-8") not in data
        assert campaign.subject.model.credential_env.encode("utf-8") in data


def test_the_campaign_concurrency_bound_is_divided_between_the_plans(
    campaign: CampaignSpec, candidate_skill: SkillArtifact, tmp_path: Path
) -> None:
    run_paths = RunPaths(root=tmp_path / "runs" / "run_dev")
    digest = digest_object(campaign)

    baseline, candidate = compile_plans(
        campaign=campaign,
        baseline=build_baseline_manifest(
            campaign=campaign,
            campaign_digest=digest,
            public_context=None,
            created_at=PINNED_TIME,
        ),
        candidate=build_candidate_manifest(
            campaign=campaign,
            campaign_digest=digest,
            skill=candidate_skill,
            public_context=None,
            created_at=PINNED_TIME,
        ),
        run_paths=run_paths,
    )

    bound = campaign.execution.max_concurrent
    assert baseline.max_concurrent <= bound
    assert candidate.max_concurrent <= bound
    assert baseline.task_count == campaign.taskset.selection.num_tasks
    assert candidate.task_count == campaign.taskset.selection.num_tasks


def test_the_evaluation_credential_is_diagnosed_on_its_own(
    campaign: CampaignSpec, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Spec sections 6.9 and 6.18: the subject's model credential is not the
    # operator's own sign-in, and a run says so before it provisions anything.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv(campaign.subject.model.credential_env, raising=False)
    absent = credential_status(campaign.subject.model)

    monkeypatch.setenv(campaign.subject.model.credential_env, "sk-not-a-real-key")
    present = credential_status(campaign.subject.model)

    assert absent.available is False
    assert absent.source == "missing"
    assert present.available is True
    assert "sk-not-a-real-key" not in present.model_dump_json()


# ---------------------------------------------------------------------------
# The real engine's own verdict
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine_paths(tmp_path_factory: pytest.TempPathFactory) -> TechtreePaths:
    paths = paths_from_root(tmp_path_factory.mktemp("techtree-home"))
    ensure_path_layout(paths)
    return paths


@pytest.fixture(scope="module")
def installed_engine(engine_paths: TechtreePaths) -> EngineStatus:
    """Install the shipped engine once, for real."""
    registry = EngineRegistry(engine_paths, Settings())
    installer = EngineInstaller(engine_paths, registry, find_uv())
    return installer.install()


@pytest.fixture(scope="module")
def engine_runner(
    engine_paths: TechtreePaths, installed_engine: EngineStatus
) -> EngineRunner:
    return EngineRunner(
        EngineRegistry(engine_paths, Settings()), installed_engine.digest
    )


@pytest.fixture(scope="module")
def named_subject_engine(
    engine_paths: TechtreePaths,
    installed_engine: EngineStatus,
    campaign: CampaignSpec,
) -> EngineStatus:
    """The engine, once it is known to expose the named-subject environment.

    Probing beats hard-coding: the day the reference package exports the
    environment, these tests begin running without anyone remembering to
    remove a skip.
    """
    registry = EngineRegistry(engine_paths, Settings())
    runner = EngineRunner(registry, installed_engine.digest)
    source = (
        "import json;"
        "from verifiers.v1.utils.loaders import env_config_type;"
        f"print(json.dumps(sorted(env_config_type({campaign.taskset.ref.id!r})"
        ".model_fields)))"
    )
    result = runner.run("python", ["-c", source], timeout=120.0)
    seats = json.loads(result.stdout) if result.exit_code == 0 else []
    if SUBJECT_SEAT not in seats:
        pytest.skip(
            "the installed engine's reference package exports no named-subject "
            "environment (spec 6.5); the bundle change is a STOP-AND-NOTE on "
            f"WP6a. Seats resolved: {seats}"
        )
    return installed_engine


@pytest.mark.parametrize("variant", list(VariantName))
def test_each_compiled_variant_dry_runs_against_the_installed_engine(
    campaign: CampaignSpec,
    candidate_skill: SkillArtifact,
    named_subject_engine: EngineStatus,
    engine_runner: EngineRunner,
    tmp_path: Path,
    variant: VariantName,
) -> None:
    run_paths = RunPaths(root=tmp_path / "runs" / "run_dev")
    config = compile_both(campaign, candidate_skill, run_paths)[variant]
    input_path = run_paths.variant_input_config(variant)
    write_variant_config(config, input_path)

    outcome = dry_run_variant_config(
        engine_runner=engine_runner,
        variant=variant,
        compiled=config,
        input_config_path=input_path,
        dry_run_dir=run_paths.variant_dry_run_dir(variant),
        model=campaign.subject.model,
    )

    configuration_checks = [
        check
        for check in outcome.checks
        if check.id != "evaluation_credential_available"
    ]
    assert [check for check in configuration_checks if check.status == "failed"] == []
    assert outcome.resolved_config is not None
    assert outcome.resolved_config["push"] is False
    assert SUBJECT_SEAT in outcome.resolved_config["env"]
