"""One real variant, executed end to end. Spec sections 6.10, 6.13, 6.14, 6.19.

This is the only test in the repository that spends money. It provisions a real
Docker container, installs Hermes Agent 0.19.0 into it, and drives thirty-six
real subject rollouts against a real provider. It is marked ``real_model``,
excluded from the default selection and from every ``make`` target that runs
unattended, and started only by somebody who meant to start it.

What it proves is the WP6 definition-of-done rows that no mock can answer:
Hermes really installs into a clean runtime home, its bundled skill catalogue
really stays off, the raw upstream evidence is really retained, and the
normalized projection really comes back in committed task-membership order
rather than in the completion order the file was written in.

The Campaign it executes is derived locally by ``fixtures.verifiers.support``,
because the shipped one names development placeholders on purpose and the real
release coordinates are the founder's to ratify at WP11h.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Final

import pytest

from fixtures.verifiers.support import (
    SUBJECT_INPUT_USD_PER_MTOK,
    SUBJECT_OUTPUT_USD_PER_MTOK,
    ExecutableCampaign,
    executable_campaign,
)
from techtree.canonical import digest_object
from techtree.engines.bundle import default_engine_digest, read_engine_descriptor
from techtree.engines.registry import EngineRegistry
from techtree.engines.runner import EngineRunner
from techtree.fs import ensure_private_directory
from techtree.models.campaign import SUBJECT_AGENT
from techtree.models.engine import EngineInstallation
from techtree.models.validation import TasksetLock
from techtree.paths import default_paths
from techtree.settings import Settings
from techtree.verifiers.child import VerifiersChild, eval_argv
from techtree.verifiers.compiler import compile_variant_config, write_variant_config
from techtree.verifiers.credentials import (
    require_credentials,
    scrubbed_child_environment,
)
from techtree.verifiers.image import resolve_subject_image
from techtree.verifiers.models import (
    NormalizedEpisode,
    RunPaths,
    VariantExecutionPlan,
    VariantName,
)
from techtree.verifiers.outputs import (
    EVAL_LOG_PATH,
    RESOLVED_CONFIG_PATH,
    TRACES_FILENAME,
    build_variant_result,
)
from techtree.verifiers.progress import inspect_progress
from techtree.verifiers.verify import dry_run_variant_config, verify_variant_execution

pytestmark = pytest.mark.real_model

#: Thirty-six agentic rollouts against a small model, one at a time, with a
#: container to provision first. Generous, because a timeout that fired would
#: waste the money the run had already spent.
_RUN_TIMEOUT_SECONDS: Final = 3600.0

#: How often the poller reads the trace file while the child works.
_POLL_INTERVAL_SECONDS: Final = 5.0

_TASKSET_LOCK_SCHEMA: Final = "techtree.taskset-lock.v1alpha1"

#: Prices for whichever subject model the local Campaign currently names, read
#: from the same fixture that names it so the two can never drift apart. Used
#: only to report what the run cost; nothing here bills anything.
_INPUT_USD_PER_MTOK: Final = SUBJECT_INPUT_USD_PER_MTOK
_OUTPUT_USD_PER_MTOK: Final = SUBJECT_OUTPUT_USD_PER_MTOK

#: Decisions document 0006. The run is abandoned rather than allowed to exceed
#: this, and the assertion is on the observed spend after the fact.
_MAXIMUM_RUN_USD: Final = 1.00


@pytest.fixture(scope="module")
def engine() -> tuple[EngineRegistry, EngineRunner, str]:
    """The installed, verified engine this machine will execute."""
    if shutil.which("docker") is None:
        pytest.skip("a real subject runs in a container; docker is not on PATH")
    if not os.environ.get("PRIME_API_KEY"):
        pytest.skip("no evaluation credential is exported in this shell")

    registry = EngineRegistry(default_paths(), Settings())
    digest = default_engine_digest()
    status = registry.status(digest)
    if not status.installed or not status.verified:
        pytest.skip("run `techtree engine install` before the real-model run")
    return registry, EngineRunner(registry, digest), digest


@pytest.fixture(scope="module")
def campaign() -> ExecutableCampaign:
    """A locally derived Campaign carrying real subject coordinates."""
    return executable_campaign()


def stage(paths: RunPaths, campaign: ExecutableCampaign) -> Path:
    """Write the run's own copies of what it executes, and return the lock path."""
    ensure_private_directory(paths.inputs_dir)
    manifest_path = paths.manifest_path(VariantName.BASELINE)
    ensure_private_directory(manifest_path.parent)
    manifest_path.write_bytes(campaign.baseline.model_dump_json().encode())

    membership = campaign.campaign.taskset.membership
    lock = TasksetLock(
        schema_version=_TASKSET_LOCK_SCHEMA,
        taskset_ref=campaign.campaign.taskset.ref,
        engine_digest=default_engine_digest(),
        resolved_package_digest=campaign.campaign.taskset.ref.package.digest,
        ordered_task_hashes=list(membership.ordered_task_hashes),
        membership_digest=membership.membership_digest,
        task_count=len(membership.ordered_task_hashes),
    )
    lock_path = paths.inputs_dir / "taskset-lock.json"
    lock_path.write_bytes(lock.model_dump_json().encode())
    return lock_path


def test_one_real_baseline_variant_runs_end_to_end(
    tmp_path_factory: pytest.TempPathFactory,
    engine: tuple[EngineRegistry, EngineRunner, str],
    campaign: ExecutableCampaign,
) -> None:
    """Execute the baseline variant for real and check every WP6 claim on it."""
    registry, runner, engine_digest = engine
    variant = VariantName.BASELINE
    home = tmp_path_factory.mktemp("real-run-home")
    paths = RunPaths(root=home / "runs" / "run_real_wp6b")
    ensure_private_directory(paths.root)
    lock_path = stage(paths, campaign)

    subject = campaign.campaign.agents[SUBJECT_AGENT]
    status = require_credentials(subject.model)
    assert status.available

    # -- compile ---------------------------------------------------------
    compiled = compile_variant_config(
        campaign=campaign.campaign,
        experiment=campaign.baseline,
        run_paths=paths,
        variant=variant,
        variant_max_concurrent=campaign.campaign.execution.max_concurrent,
    )
    assert compiled.num_tasks == campaign.task_count
    assert compiled.env.subject.harness.version == "0.19.0"
    assert compiled.env.subject.harness.use_bundled_skill is False
    assert compiled.env.subject.harness.skills == []
    assert compiled.push is False
    assert compiled.rich is None

    input_path = paths.variant_input_config(variant)
    write_variant_config(compiled, input_path)

    # -- dry run ---------------------------------------------------------
    dry_run = dry_run_variant_config(
        engine_runner=runner,
        variant=variant,
        compiled=compiled,
        input_config_path=input_path,
        dry_run_dir=paths.variant_dry_run_dir(variant),
        model=subject.model,
    )
    assert dry_run.ok, [check.model_dump() for check in dry_run.failures]
    assert paths.variant_dry_run_command_log(variant).is_file()

    # -- execute ---------------------------------------------------------
    child = VerifiersChild(
        variant=variant,
        argv=eval_argv(
            eval_executable=registry.executable(engine_digest, "eval"),
            input_config_path=input_path,
        ),
        cwd=paths.variant_output_dir(variant),
        env=scrubbed_child_environment(
            model=subject.model,
            engine=_installation(registry, engine_digest),
        ),
        stdout_path=paths.variant_stdout_log(variant),
        stderr_path=paths.variant_stderr_log(variant),
        supervision_record_path=paths.variant_supervision_record(variant),
    )

    traces_path = paths.variant_output_dir(variant) / TRACES_FILENAME
    started = time.monotonic()
    child.start()
    try:
        while child.poll() is None:
            if time.monotonic() - started > _RUN_TIMEOUT_SECONDS:
                child.terminate(grace_seconds=60.0)
                pytest.fail("the real run did not finish inside its timeout")
            progress = inspect_progress(
                variant=variant,
                traces_path=traces_path,
                total=campaign.task_count,
                child_exit_code=None,
                max_concurrent=compiled.max_concurrent,
            )
            print(
                f"[{time.monotonic() - started:6.0f}s] {progress.state} "
                f"{progress.completed}/{progress.total}"
            )
            time.sleep(_POLL_INTERVAL_SECONDS)
    finally:
        if child.poll() is None:
            child.terminate(grace_seconds=60.0)

    outcome = child.outcome()
    assert outcome.exit_code == 0, _tail(paths.variant_stderr_log(variant))
    assert not outcome.cancelled

    # -- raw evidence is retained ----------------------------------------
    output_dir = paths.variant_output_dir(variant)
    for name in (RESOLVED_CONFIG_PATH, TRACES_FILENAME, EVAL_LOG_PATH):
        assert (output_dir / name).is_file(), f"{name} was not retained"
    assert paths.variant_stdout_log(variant).is_file()
    assert paths.variant_stderr_log(variant).is_file()

    raw_lines = traces_path.read_text().splitlines()
    assert len(raw_lines) == campaign.task_count

    # -- normalize -------------------------------------------------------
    plan_progress = inspect_progress(
        variant=variant,
        traces_path=traces_path,
        total=campaign.task_count,
        child_exit_code=outcome.exit_code,
    )
    assert plan_progress.state == "completed"

    result = build_variant_result(
        plan=_plan(paths, campaign, variant, compiled.max_concurrent),
        outcome=outcome,
        image_resolution=resolve_subject_image(
            campaign.campaign.subject.runtime, variant
        ),
        engine_registry=registry,
        engine_digest=engine_digest,
        engine_runner=runner,
        taskset_lock_path=lock_path,
    )

    # -- the normalized projection is in membership order ----------------
    committed = list(campaign.campaign.taskset.membership.ordered_task_hashes)
    assert [episode.task_hash for episode in result.episodes] == committed
    assert [episode.task_position for episode in result.episodes] == list(
        range(len(committed))
    )

    # Completion order and membership order genuinely differ under any real
    # concurrency; when they happen to agree the ordering claim is untested but
    # not false, so this is reported rather than asserted.
    raw_order = [json.loads(line)["traces"][0]["task"]["hash"] for line in raw_lines]
    print(f"completion order equals membership order: {raw_order == committed}")

    # -- one named subject trace per task, with a real reward -------------
    assert len(result.episodes) == campaign.task_count
    for episode in result.episodes:
        assert len(episode.traces) == 1
        trace = episode.traces[0]
        assert trace.agent_role == "subject"
        assert trace.harness_id == "hermes-agent"
        assert trace.harness_version == "0.19.0"
        assert trace.use_bundled_skill is False
        assert trace.skill_root_digests == []
        assert trace.runtime.kind == "docker"
        assert trace.model_id == subject.model.model_id
        assert trace.reward("exact_match") is not None

    # -- every WP6 verification check passes ------------------------------
    lock = TasksetLock.model_validate_json(lock_path.read_bytes())
    checks = verify_variant_execution(
        result=result,
        experiment=campaign.baseline,
        taskset_lock=lock,
        primary_reward=campaign.campaign.scoring.primary_reward,
        # The pin is recorded per trace by the run itself, so the check is
        # against the engine's own descriptor rather than against a claim.
        engine=read_engine_descriptor(registry.path(engine_digest)),
    )
    failed = [check for check in checks if check.status == "failed"]
    assert not failed, [check.model_dump() for check in failed]

    # -- what it cost ------------------------------------------------------
    spend = _report_spend(result.episodes)
    assert spend <= _MAXIMUM_RUN_USD


def _installation(registry: EngineRegistry, digest: str) -> EngineInstallation:
    """Return the recorded installation, or refuse to guess at one."""
    installation = registry.installation(digest)
    assert installation is not None, "the engine records no installation"
    return installation


def _plan(
    paths: RunPaths, campaign: ExecutableCampaign, variant: VariantName, permits: int
) -> VariantExecutionPlan:
    """Build the execution plan the normalizer and result assembler read."""
    return VariantExecutionPlan(
        variant=variant,
        experiment_manifest_digest=digest_object(campaign.baseline),
        experiment_manifest_path=str(paths.manifest_path(variant)),
        verifiers_input_config_path=str(paths.variant_input_config(variant)),
        verifiers_output_dir=str(paths.variant_output_dir(variant)),
        skill_paths=[],
        task_count=campaign.task_count,
        max_concurrent=permits,
    )


def _report_spend(episodes: list[NormalizedEpisode]) -> float:
    """Print and return the most this run can have cost.

    ``input_tokens`` counts cache reads back in, and the returned figure prices
    every one of them at the full input rate. That is deliberately the
    pessimistic reading: the Prime models endpoint publishes one input price and
    no cached-read price, so the cheaper interpretation is a guess and the
    expensive one is a bound. The cached share is printed beside it because on
    an agentic run it is most of the total, and the gap between the two readings
    is the difference between cents and most of a per-run budget.
    """
    input_tokens = 0
    cached_tokens = 0
    output_tokens = 0
    scored = 0
    for episode in episodes:
        for trace in episode.traces:
            reward = trace.reward("exact_match")
            scored += int(reward is not None and reward.score > 0)
            if trace.usage is not None:
                input_tokens += trace.usage.input_tokens
                cached_tokens += trace.usage.cached_input_tokens or 0
                output_tokens += trace.usage.output_tokens

    spend = (
        input_tokens / 1_000_000 * _INPUT_USD_PER_MTOK
        + output_tokens / 1_000_000 * _OUTPUT_USD_PER_MTOK
    )
    if_cached_free = (
        input_tokens - cached_tokens
    ) / 1_000_000 * _INPUT_USD_PER_MTOK + (
        output_tokens / 1_000_000 * _OUTPUT_USD_PER_MTOK
    )
    print(f"cached input: {cached_tokens} of {input_tokens}")
    print(f"spend if cached reads are not billed: USD {if_cached_free:.4f}")
    print(
        f"\nREAL RUN: {scored}/{len(episodes)} tasks scored exact_match\n"
        f"tokens: {input_tokens} input, {output_tokens} output\n"
        f"spend:  USD {spend:.4f} (cap {_MAXIMUM_RUN_USD:.2f})"
    )
    return spend


def _tail(path: Path, lines: int = 40) -> str:
    """Return the last lines of a capture file, for a failure message."""
    if not path.is_file():
        return f"{path.name} was never written"
    return "\n".join(path.read_text(errors="replace").splitlines()[-lines:])
