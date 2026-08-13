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
named-subject environment spec section 6.5 requires. It does, since the bundle
addendum: without it a compiled ``[env.subject]`` table is rejected at parse
time (``docs/verifiers-eval.md``, finding E0). The gate stays because it is a
probe of the installed engine rather than a hard-coded skip — an engine built
from a package that forgot to export its environment says so here, clearly,
instead of failing with an upstream parse error nobody can place.
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
from techtree.models.base import ArtifactRef
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

    Probing beats hard-coding: an engine whose reference package lost its
    environment export says so in one legible sentence rather than through an
    upstream parse error.
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
            "environment (spec 6.5), so nothing here could be dry-run. "
            f"Seats resolved: {seats}"
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


# ---------------------------------------------------------------------------
# The engine's normalizer, over a real wire record
# ---------------------------------------------------------------------------

WIRE_EPISODE_GENERATOR = '''
"""Write a traces.jsonl the pinned engine itself considers well formed."""

import json
import sys

from verifiers.v1.cli.output import save_config, write_episode
from verifiers.v1.configs.agent import WireAgentConfig
from verifiers.v1.configs.harness import WireHarnessConfig
from verifiers.v1.episode import Episode, EnvInfo
from verifiers.v1.runtimes.docker import DockerRuntimeInfo
from verifiers.v1.task import WireTaskData
from verifiers.v1.trace import AgentInfo, Reward, Trace, TraceTask

output_dir, image, model, *hashes = sys.argv[1:]
from pathlib import Path

directory = Path(output_dir)
directory.mkdir(parents=True, exist_ok=True)
(directory / "config.toml").write_text("push = false\\n")
(directory / "traces.jsonl").write_text("")
(directory / "eval.log").write_text("INFO results\\n")

# Written in reverse membership order on purpose: line order is completion
# order, and the normalizer is what puts the projection back into the
# Campaign's committed order.
for position, task_hash in reversed(list(enumerate(hashes))):
    trace = Trace(
        task=TraceTask(
            type="ProcedureTransferTask",
            data=WireTaskData(idx=position, name="task-%d" % position),
            hash=task_hash,
        ),
        agent=AgentInfo(
            config=WireAgentConfig(
                harness=WireHarnessConfig(
                    id="hermes-agent", version="0.19.0", use_bundled_skill=False
                ),
                runtime={"type": "docker", "image": image},
                model=model,
            ),
            runtime=DockerRuntimeInfo(
                id="container-%d" % position, image=image, cpu=2.0, memory=4.0
            ),
            name="subject",
            trainable=False,
        ),
        rewards={"exact_match": Reward(score=1.0, weight=1.0)},
        is_completed=True,
        ok=True,
    )
    write_episode(
        directory,
        Episode(
            env=EnvInfo(id="procedure-transfer-v1"), ok=True, traces=[trace]
        ),
    )
print(json.dumps({"written": len(hashes)}))
'''


def test_the_engine_normalizer_orders_episodes_by_committed_membership(
    campaign: CampaignSpec,
    candidate_skill: SkillArtifact,
    named_subject_engine: EngineStatus,
    engine_paths: TechtreePaths,
    engine_runner: EngineRunner,
    tmp_path: Path,
) -> None:
    from techtree.engines.bundle import read_engine_descriptor
    from techtree.models.validation import TasksetLock
    from techtree.verifiers.models import ChildProcessOutcome
    from techtree.verifiers.outputs import build_variant_result
    from techtree.verifiers.verify import verify_variant_execution

    variant = VariantName.CANDIDATE
    run_paths = RunPaths(root=tmp_path / "runs" / "run_dev")
    digest = digest_object(campaign)
    manifest = build_candidate_manifest(
        campaign=campaign,
        campaign_digest=digest,
        skill=candidate_skill,
        public_context=None,
        created_at=PINNED_TIME,
    )

    # The run's own copies of what it executed.
    lock_path = run_paths.inputs_dir / "taskset-lock.json"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    committed = list(campaign.taskset.membership.ordered_task_hashes)
    taskset_lock = TasksetLock(
        schema_version="techtree.taskset-lock.v1alpha1",
        taskset_ref=campaign.taskset.ref,
        engine_digest=named_subject_engine.digest,
        resolved_package_digest=campaign.taskset.ref.package.digest,
        ordered_task_hashes=committed,
        membership_digest=campaign.taskset.membership.membership_digest,
        task_count=len(committed),
    )
    lock_path.write_text(taskset_lock.model_dump_json())
    manifest_path = run_paths.manifest_path(variant)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest.model_dump_json())

    plan = compile_plans(
        campaign=campaign,
        baseline=build_baseline_manifest(
            campaign=campaign,
            campaign_digest=digest,
            public_context=None,
            created_at=PINNED_TIME,
        ),
        candidate=manifest,
        run_paths=run_paths,
    )[1]

    # A real wire record, written by the pinned models, in completion order.
    generator = tmp_path / "write_wire_episodes.py"
    generator.write_text(WIRE_EPISODE_GENERATOR)
    image = campaign.subject.runtime.image
    written = engine_runner.run_python_script(
        generator,
        [
            plan.verifiers_output_dir,
            image,
            campaign.subject.model.model_id,
            *(value.removeprefix("sha256:") for value in committed),
        ],
        timeout=120.0,
    )
    assert written.exit_code == 0, written.stderr

    outcome = ChildProcessOutcome(
        variant=variant,
        argv_digest=f"sha256:{'e' * 64}",
        exit_code=0,
        started_at=PINNED_TIME,
        finished_at=PINNED_TIME,
        stdout_artifact=ArtifactRef(
            digest=f"sha256:{'f' * 64}",
            media_type="text/plain",
            size=1,
            relative_path=None,
        ),
        stderr_artifact=ArtifactRef(
            digest=f"sha256:{'0' * 64}",
            media_type="text/plain",
            size=1,
            relative_path=None,
        ),
        cancelled=False,
    )

    result = build_variant_result(
        plan=plan,
        outcome=outcome,
        engine_registry=EngineRegistry(engine_paths, Settings()),
        engine_digest=named_subject_engine.digest,
        engine_runner=engine_runner,
        taskset_lock_path=lock_path,
    )

    # Written in reverse, projected in membership order.
    assert [episode.task_hash for episode in result.episodes] == committed
    assert [episode.task_position for episode in result.episodes] == list(
        range(len(committed))
    )
    assert {trace.agent_role for e in result.episodes for trace in e.traces} == {
        "subject"
    }
    # Raw evidence is retained alongside the projection.
    assert result.raw_traces.size > 0
    assert result.eval_log.size > 0
    assert result.normalized_episodes.size > 0

    descriptor = read_engine_descriptor(
        EngineRegistry(engine_paths, Settings()).path(named_subject_engine.digest)
    )
    checks = verify_variant_execution(
        result=result,
        experiment=manifest,
        taskset_lock=taskset_lock,
        primary_reward=campaign.scoring.primary_reward,
        engine=descriptor,
    )
    failed = [check for check in checks if check.status == "failed"]
    assert failed == [], [f"{check.id}: {check.detail}" for check in failed]
    assert "verifiers_pin_matches_engine" in {check.id for check in checks}


def test_normalization_is_deterministic_for_the_same_raw_output(
    campaign: CampaignSpec,
    named_subject_engine: EngineStatus,
    engine_paths: TechtreePaths,
    engine_runner: EngineRunner,
    tmp_path: Path,
) -> None:
    from techtree.models.validation import TasksetLock
    from techtree.verifiers.outputs import normalize_eval_output

    committed = list(campaign.taskset.membership.ordered_task_hashes)
    output_dir = tmp_path / "run"
    generator = tmp_path / "write_wire_episodes.py"
    generator.write_text(WIRE_EPISODE_GENERATOR)
    written = engine_runner.run_python_script(
        generator,
        [
            str(output_dir),
            campaign.subject.runtime.image,
            campaign.subject.model.model_id,
            *(value.removeprefix("sha256:") for value in committed),
        ],
        timeout=120.0,
    )
    assert written.exit_code == 0, written.stderr

    lock_path = tmp_path / "taskset-lock.json"
    lock_path.write_text(
        TasksetLock(
            schema_version="techtree.taskset-lock.v1alpha1",
            taskset_ref=campaign.taskset.ref,
            engine_digest=named_subject_engine.digest,
            resolved_package_digest=campaign.taskset.ref.package.digest,
            ordered_task_hashes=committed,
            membership_digest=campaign.taskset.membership.membership_digest,
            task_count=len(committed),
        ).model_dump_json()
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        build_baseline_manifest(
            campaign=campaign,
            campaign_digest=digest_object(campaign),
            public_context=None,
            created_at=PINNED_TIME,
        ).model_dump_json()
    )

    outputs = []
    for attempt in ("first", "second"):
        destination = tmp_path / f"{attempt}.jsonl"
        normalize_eval_output(
            engine_registry=EngineRegistry(engine_paths, Settings()),
            engine_digest=named_subject_engine.digest,
            engine_runner=engine_runner,
            output_dir=output_dir,
            taskset_lock_path=lock_path,
            experiment_manifest_path=manifest_path,
            destination=destination,
        )
        outputs.append(destination.read_bytes())

    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b"\n")
