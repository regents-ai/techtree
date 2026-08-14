"""The executor that actually evaluates something. Spec section 6.17.

Everything the development executor invented, this one measures. What it does
*not* do is decide what the measurements mean: it returns a
:class:`~techtree.verifiers.models.RealExecutionResult` — two variants, their
raw evidence, and the engine's own normalized projection of it — and WP7 turns
that into receipts, a comparison and a report. Spec section 6.22 states the
boundary as a rule: WP6 does not invent final uplift.

The sequence in :meth:`RealVerifiersExecutor.execute` is section 6.17's,
unchanged, and its order is the whole safety argument. Every cheap refusal
happens before every expensive one. The staged inputs are verified before the
engine is resolved; the engine is resolved before the credential is required;
the credential is required before the taskset is validated; the taskset is
validated before a configuration is compiled; and both configurations survive a
model-free dry run against the real engine before a single container starts. A
run that is going to fail should fail while it is still free.

Two things this module owns that the specification's sketch leaves implicit.

*The skill mount is materialized at its content address.* The run stages the
candidate's skill tree as the artifact describes it; the compiler mounts a
skill from a directory named after its root digest, because the folder name is
part of what the subject sees and must therefore be a property of the skill
rather than of whoever prepared it. Reconciling the two is a verified copy
inside the run's own input tree, never a link to anything a participant could
still edit.

*A development-placeholder Campaign is refused here, not warned about.* Spec
section 16 requires that the fake executor stop being what a real Campaign
gets; the converse is that the real executor must not be what a placeholder
Campaign gets. One predicate answers both questions, and
:func:`campaign_is_executable` is it.
"""

from __future__ import annotations

import contextlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from techtree.canonical import sha256_digest_bytes, to_json_value
from techtree.doctor.execution_checks import check_live_campaign
from techtree.engines.bundle import default_engine_digest, read_engine_descriptor
from techtree.engines.registry import EngineRegistry
from techtree.engines.runner import EngineRunner
from techtree.errors import (
    EngineError,
    PrerequisiteError,
    ValidationError,
    VerificationError,
)
from techtree.fs import atomic_write_json, ensure_private_directory, open_exclusive
from techtree.models.base import Digest, JsonValue
from techtree.models.campaign import (
    SUBJECT_AGENT,
    AgentSpec,
    CampaignSpec,
    ModelSpec,
    VariantSchedule,
)
from techtree.models.cli import CheckStatus
from techtree.models.engine import EngineDescriptor, EngineInstallation
from techtree.models.evaluation_backend import SUPPORTED_EVALUATION_BACKEND_KINDS
from techtree.models.experiment import ExperimentManifest
from techtree.models.run import ExecutorKind, RunPhase, RunRequest
from techtree.models.skill import SkillArtifact
from techtree.paths import TechtreePaths
from techtree.runs.artifacts import RunInputBundle
from techtree.runs.child_registry import ChildRegistry, EvaluationChild, execution_dir
from techtree.runs.executor import ExecutionContext
from techtree.runs.validation import TasksetValidationOutcome
from techtree.runs.variants import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    VariantPair,
    VariantPairOutcome,
    VariantScheduler,
    require_concurrency_budget,
)
from techtree.tasksets.service import TASKSET_DIRECTORY
from techtree.verifiers.child import (
    DEFAULT_GRACE_SECONDS,
    VerifiersChild,
    eval_argv,
)
from techtree.verifiers.compiler import (
    compile_plans,
    compile_variant_config,
    skill_directory_name,
    write_variant_config,
)
from techtree.verifiers.credentials import (
    require_credentials,
    scrubbed_child_environment,
)
from techtree.verifiers.image import resolve_subject_image
from techtree.verifiers.models import (
    ChildProcessOutcome,
    RealExecutionResult,
    RunPaths,
    SubjectImageResolution,
    VariantExecutionPlan,
    VariantExecutionResult,
    VariantName,
)
from techtree.verifiers.outputs import (
    DEFAULT_NORMALIZE_TIMEOUT_SECONDS,
    build_variant_result,
)
from techtree.verifiers.verify import (
    DEFAULT_DRY_RUN_TIMEOUT_SECONDS,
    dry_run_variant_config,
    verify_variant_execution,
)

__all__ = [
    "REAL_EXECUTION_RESULT_FILENAME",
    "REAL_EXECUTION_UNSUPPORTED",
    "TASKSET_LOCK_FILENAME",
    "VARIANT_NOT_USABLE",
    "ChildFactory",
    "RealVerifiersExecutor",
    "campaign_is_executable",
    "executor_kind_for",
    "keep_evaluation_private",
    "real_execution_result_path",
    "require_live_campaign",
]

#: Stable error codes. Spec section 6.17's failure policy reports through these.
REAL_EXECUTION_UNSUPPORTED: Final = "real_execution_unsupported"
VARIANT_NOT_USABLE: Final = "variant_execution_not_usable"

#: The run's own copy of the membership the normalizer joins episodes onto.
#: Spec section 6.19.
TASKSET_LOCK_FILENAME: Final = "taskset-lock.json"

#: What WP6 hands WP7, written where WP7 will look for it. Spec section 6.19.
REAL_EXECUTION_RESULT_FILENAME: Final = "real-execution-result.json"

#: Owner read and write only, matching every other file Techtree writes.
_PRIVATE_FILE_MODE: Final = 0o600

#: Owner traversal only, matching every directory Techtree creates.
_PRIVATE_DIRECTORY_MODE: Final = 0o700

#: Both sides, always in comparison order.
_VARIANT_ORDER: Final[tuple[VariantName, ...]] = (
    VariantName.BASELINE,
    VariantName.CANDIDATE,
)


class ChildFactory(Protocol):
    """How one variant's evaluation child is constructed.

    :class:`~techtree.verifiers.child.VerifiersChild` is the implementation and
    the default. The seam exists so that the executor's own sequence can be
    exercised without a container or a provider, which is the only way to test
    a code path whose real form spends money.
    """

    def __call__(
        self,
        *,
        variant: VariantName,
        argv: Sequence[str],
        cwd: Path,
        env: Mapping[str, str],
        stdout_path: Path,
        stderr_path: Path,
    ) -> EvaluationChild:
        """Build one unstarted child."""
        ...


@dataclass(frozen=True)
class _ResolvedEngine:
    """The engine this run will execute, and the facts read back from it."""

    digest: Digest
    installation: EngineInstallation
    descriptor: EngineDescriptor
    runner: EngineRunner


# ---------------------------------------------------------------------------
# Which executor a Campaign gets
# ---------------------------------------------------------------------------


def campaign_is_executable(campaign: CampaignSpec) -> bool:
    """Whether this Campaign names a subject that may be executed for real.

    One predicate, consulted both by the worker choosing an executor and by the
    real executor refusing to start. The Campaign this build ships names a
    development-placeholder model and image on purpose, and the founder
    ratifies the real release coordinates at WP11h; until then a placeholder
    Campaign is a thing to compile and dry-run, never a thing to run.
    """
    return check_live_campaign(campaign).status is CheckStatus.PASS


def executor_kind_for(campaign: CampaignSpec) -> ExecutorKind:
    """Return the name of the executor this Campaign will be run by.

    The same predicate that routes the worker, answered early enough to be
    written down. A run records this when it is created, which is the moment a
    person is shown what is about to happen, so the request says whether real
    containers and a real provider are about to be used or whether this is the
    development executor inventing numbers.

    Recording it does not make it true — the worker re-reads the run's own
    staged Campaign and asks this same question again, and the fake executor
    refuses a request that names anything but itself. What recording it buys
    is that nobody has to run a Campaign through a predicate to find out what a
    finished run was.
    """
    return "verifiers" if campaign_is_executable(campaign) else "fake"


def require_live_campaign(campaign: CampaignSpec) -> None:
    """Refuse a Campaign whose coordinates are development placeholders."""
    check = check_live_campaign(campaign)
    if check.status is CheckStatus.PASS:
        return
    raise PrerequisiteError(
        f"this Campaign cannot be executed for real: {check.detail}",
        code=REAL_EXECUTION_UNSUPPORTED,
        details={"campaign_id": campaign.metadata.id},
    )


def real_execution_result_path(run_root: Path) -> Path:
    """Return where one run records what WP6 hands WP7."""
    return execution_dir(run_root) / REAL_EXECUTION_RESULT_FILENAME


def keep_evaluation_private(run_paths: RunPaths) -> Path:
    """Make everything one run's engine produced readable by its owner only.

    Spec section 6.19: raw Verifiers artifacts are mode ``0600`` and remain
    local. Techtree writes its own capture files that way, but the engine
    writes ``traces.jsonl``, ``eval.log``, the resolved configuration and the
    taskset validator's output under the operator's ordinary umask — and
    ``traces.jsonl`` is the participant's complete subject transcripts.
    Tightening them afterwards is the only moment available: the files belong
    to the child while it is running, and a run that never reached them has
    nothing to tighten.

    Both trees the engine writes into are swept, not just the evaluation one.
    ``taskset/validation/`` is the validator's output and was left at the
    operator's umask until WP11g S6 noticed; a task hash is not a transcript,
    but "which of these two directories a stranger may read" is not a
    distinction worth maintaining.

    Directories are swept as well as files, because a directory the engine
    created inside one of these trees carries the umask exactly as its
    contents do.

    Applied whether the run succeeded, failed or was cancelled: a partial
    transcript is exactly as private as a complete one.
    """
    root = run_paths.verifiers_dir
    for tree in (root, run_paths.root / TASKSET_DIRECTORY):
        if not tree.is_dir():
            continue
        _make_private(tree)
        for path in tree.rglob("*"):
            _make_private(path)
    return root


def _make_private(path: Path) -> None:
    """Tighten one path the engine left behind, whatever kind it is."""
    if path.is_symlink():
        # Never chmod through a link: the target may not be the run's.
        return
    with contextlib.suppress(OSError):
        if path.is_dir():
            path.chmod(_PRIVATE_DIRECTORY_MODE)
        elif path.is_file():
            path.chmod(_PRIVATE_FILE_MODE)


# ---------------------------------------------------------------------------
# The executor
# ---------------------------------------------------------------------------


class RealVerifiersExecutor:
    """Executes both variants of a real Campaign through the pinned engine."""

    def __init__(
        self,
        *,
        paths: TechtreePaths,
        engine_registry: EngineRegistry,
        child_registry: ChildRegistry,
        engine_digest: Digest | None = None,
        child_factory: ChildFactory | None = None,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        grace_seconds: float = DEFAULT_GRACE_SECONDS,
        dry_run_timeout_seconds: float = DEFAULT_DRY_RUN_TIMEOUT_SECONDS,
        normalize_timeout_seconds: float = DEFAULT_NORMALIZE_TIMEOUT_SECONDS,
    ) -> None:
        self._paths = paths
        self._registry = engine_registry
        self._child_registry = child_registry
        self._engine_digest = engine_digest or default_engine_digest()
        self._child_factory: ChildFactory = child_factory or VerifiersChild
        self._poll_interval = poll_interval_seconds
        self._grace = grace_seconds
        self._dry_run_timeout = dry_run_timeout_seconds
        self._normalize_timeout = normalize_timeout_seconds

    def execute(self, context: ExecutionContext) -> RealExecutionResult:
        """Execute one real Campaign's two variants. Spec section 6.17."""
        request = context.request
        run_id = request.run_id
        run_paths = RunPaths.for_run(self._paths, run_id)

        # 1-3. The run's own inputs, verified, and the rights it runs under.
        inputs = context.artifact_store.load_inputs(run_id, request)
        campaign = inputs.campaign
        self._require_acknowledged_policy(request, campaign)
        self._require_supported_backend(campaign)
        require_live_campaign(campaign)
        subject = self._subject(campaign)

        # 4-5. The engine, and the credential the subject's calls are paid with.
        engine = self._resolve_engine()
        require_credentials(subject.model)

        # 6-7. Local taskset validation, and the membership it commits to.
        validation = self._validate_taskset(context, inputs)
        lock_path = self._write_taskset_lock(run_paths, validation)

        # 8-11. Both configurations compiled and survived by the real engine,
        # and what this machine's daemon holds for the container they pin —
        # asked for both variants before either is launched, so that a missing
        # or unexpected image costs nothing rather than half a comparison.
        self._materialize_skill_mounts(inputs, run_paths)
        pair = self._compile_pair(campaign, inputs, run_paths, engine, subject.model)
        images = {
            variant: resolve_subject_image(subject.runtime, variant)
            for variant in _VARIANT_ORDER
        }

        try:
            # 12-15. Both children, started and watched.
            outcome = self._run_children(
                context, campaign=campaign, pair=pair, engine=engine, subject=subject
            )

            # 16-18. The engine's own reading of what each child left behind.
            results = self._normalize(
                pair=pair,
                outcome=outcome,
                images=images,
                inputs=inputs,
                validation=validation,
                engine=engine,
                lock_path=lock_path,
                primary_reward=campaign.scoring.primary_reward,
            )
            return self._record(run_paths, engine, outcome, results)
        finally:
            keep_evaluation_private(run_paths)

    # -- preconditions ------------------------------------------------------

    def _require_acknowledged_policy(
        self, request: RunRequest, campaign: CampaignSpec
    ) -> None:
        """Refuse to execute under rights nobody accepted for this Campaign."""
        acknowledged = request.policy_acknowledgement.data_policy_digest
        if acknowledged == campaign.data_policy_digest:
            return
        raise ValidationError(
            "the DataPolicy this run acknowledged is not the one its Campaign "
            "is governed by",
            code=REAL_EXECUTION_UNSUPPORTED,
            details={
                "run_id": request.run_id,
                "acknowledged": acknowledged,
                "campaign": campaign.data_policy_digest,
            },
        )

    def _require_supported_backend(self, campaign: CampaignSpec) -> None:
        """Refuse a Campaign this build has no evaluation backend for."""
        kind = campaign.evaluation_backend.kind
        if kind in SUPPORTED_EVALUATION_BACKEND_KINDS:
            return
        raise ValidationError(
            f"this Campaign is evaluated by {kind.value}, which this build "
            "does not run",
            code=REAL_EXECUTION_UNSUPPORTED,
            details={"evaluation_backend": kind.value},
        )

    def _subject(self, campaign: CampaignSpec) -> AgentSpec:
        """Return the evaluated agent, or refuse a Campaign that names none."""
        subject = campaign.agents.get(SUBJECT_AGENT)
        if subject is None:
            raise ValidationError(
                f"this Campaign defines no {SUBJECT_AGENT!r} agent to execute",
                code=REAL_EXECUTION_UNSUPPORTED,
                details={"campaign_id": campaign.metadata.id},
            )
        return subject

    def _resolve_engine(self) -> _ResolvedEngine:
        """Resolve the pinned engine and require it to be verified in place."""
        status = self._registry.status(self._engine_digest)
        if not status.installed or not status.verified:
            raise EngineError(
                "the pinned evaluation engine is not installed and verified on "
                "this machine",
                code="engine_not_verified",
                details={
                    "engine_digest": self._engine_digest,
                    "installed": status.installed,
                    "verified": status.verified,
                },
            )
        installation = self._registry.installation(self._engine_digest)
        if installation is None:
            raise EngineError(
                "the pinned evaluation engine records no installation",
                code="engine_not_verified",
                details={"engine_digest": self._engine_digest},
            )
        return _ResolvedEngine(
            digest=self._engine_digest,
            installation=installation,
            descriptor=read_engine_descriptor(self._registry.path(self._engine_digest)),
            runner=EngineRunner(self._registry, self._engine_digest),
        )

    # -- taskset ------------------------------------------------------------

    def _validate_taskset(
        self, context: ExecutionContext, inputs: RunInputBundle
    ) -> TasksetValidationOutcome:
        """Validate the taskset locally and require it to be the committed one."""
        run_id = context.request.run_id
        context.run_store.append(run_id, phase=RunPhase.VALIDATING_TASKSET)
        validation = context.validation_provider.validate(run_id=run_id, inputs=inputs)
        context.artifact_store.write_validation_marker(
            run_id, validation.marker_document()
        )

        if validation.receipt.status != "valid":
            raise VerificationError(
                "the taskset validation this run was given reports "
                f"{validation.receipt.status}, so nothing may be scored on it",
                code=VARIANT_NOT_USABLE,
                details={"run_id": run_id, "status": validation.receipt.status},
            )
        if validation.lock.ordered_task_hashes != inputs.ordered_task_hashes:
            raise VerificationError(
                "the validated taskset does not hold the tasks the Campaign commits to",
                code=VARIANT_NOT_USABLE,
                details={"run_id": run_id},
            )
        return validation

    def _write_taskset_lock(
        self, run_paths: RunPaths, validation: TasksetValidationOutcome
    ) -> Path:
        """Write the run's own copy of the membership the normalizer joins on."""
        path = run_paths.inputs_dir / TASKSET_LOCK_FILENAME
        if path.is_file():
            return path
        ensure_private_directory(path.parent)
        with open_exclusive(path) as handle:
            handle.write(validation.lock.model_dump_json().encode("utf-8"))
        return path

    # -- inputs the subject actually reads ----------------------------------

    def _materialize_skill_mounts(
        self, inputs: RunInputBundle, run_paths: RunPaths
    ) -> None:
        """Place each declared skill at the content address the compiler mounts.

        The bytes are re-verified against the artifact as they are copied, so
        what the subject reads is provably the tree the run's manifests name
        rather than whatever is sitting in the staged directory by then.

        A Skill insertion places one tree; a Skill replacement places two,
        because its baseline carries the Skill being revised. Which is which
        never has to be decided here: a skill is found by the content address
        the variant declares, among the skills the run owns, so a variant
        asking for anything the run did not stage stops the run.
        """
        owned = {
            staged.artifact.root_digest: staged for staged in inputs.declared_skills
        }
        for manifest in (inputs.baseline, inputs.candidate):
            subject = manifest.configuration.agents.get(SUBJECT_AGENT)
            if subject is None:
                continue
            for reference in subject.harness.skills:
                staged = owned.get(reference.digest)
                if staged is None:
                    raise VerificationError(
                        "a variant declares a skill this run does not own",
                        code=VARIANT_NOT_USABLE,
                        details={
                            "declared": reference.digest,
                            "staged": ", ".join(sorted(owned)),
                        },
                    )
                self._copy_skill_tree(
                    skill=staged.artifact,
                    source=staged.files,
                    destination=run_paths.skill_files_dir
                    / skill_directory_name(reference.digest),
                )

    def _copy_skill_tree(
        self, *, skill: SkillArtifact, source: Path, destination: Path
    ) -> None:
        """Copy one skill's files under a content-addressed directory name."""
        for entry in skill.files:
            target = destination / entry.path
            if target.is_file():
                continue
            ensure_private_directory(target.parent)
            data = (source / entry.path).read_bytes()
            if len(data) != entry.size or sha256_digest_bytes(data) != entry.digest:
                raise VerificationError(
                    f"this run's copy of the skill file {entry.path} is not "
                    "what the artifact says it is, so it is not what the "
                    "subject may be given",
                    code=VARIANT_NOT_USABLE,
                    details={"path": entry.path},
                )
            with open_exclusive(target) as handle:
                handle.write(data)

    # -- compilation --------------------------------------------------------

    def _compile_pair(
        self,
        campaign: CampaignSpec,
        inputs: RunInputBundle,
        run_paths: RunPaths,
        engine: _ResolvedEngine,
        model: ModelSpec,
    ) -> VariantPair:
        """Compile, write and dry-run both variants' configurations.

        ``compile_plans`` divides the Campaign's concurrency and returns the
        plans; the configuration itself is recompiled per variant from the
        permits the plan settled on. Compilation is a pure function of the
        manifest, the run paths and that number, so the two agree by
        construction rather than by assertion — and the recompilation is what
        gives the dry run the exact document that was written.
        """
        baseline_plan, candidate_plan = compile_plans(
            campaign=campaign,
            baseline=inputs.baseline,
            candidate=inputs.candidate,
            run_paths=run_paths,
        )
        pair = VariantPair(baseline=baseline_plan, candidate=candidate_plan)
        require_concurrency_budget(
            pair, max_concurrent=campaign.execution.max_concurrent
        )

        manifests = {
            VariantName.BASELINE: inputs.baseline,
            VariantName.CANDIDATE: inputs.candidate,
        }
        for variant in _VARIANT_ORDER:
            plan = pair.plan(variant)
            compiled = compile_variant_config(
                campaign=campaign,
                experiment=manifests[variant],
                run_paths=run_paths,
                variant=variant,
                variant_max_concurrent=plan.max_concurrent,
            )
            input_path = run_paths.variant_input_config(variant)
            write_variant_config(compiled, input_path)

            outcome = dry_run_variant_config(
                engine_runner=engine.runner,
                variant=variant,
                compiled=compiled,
                input_config_path=input_path,
                dry_run_dir=run_paths.variant_dry_run_dir(variant),
                model=model,
                timeout=self._dry_run_timeout,
            )
            if not outcome.ok:
                failures: list[JsonValue] = [
                    to_json_value(check) for check in outcome.failures
                ]
                raise ValidationError(
                    f"the {variant.value} configuration did not survive the "
                    "engine's own validation, so nothing was executed",
                    code=VARIANT_NOT_USABLE,
                    details={"variant": variant.value, "checks": failures},
                )
        return pair

    # -- execution ----------------------------------------------------------

    def _run_children(
        self,
        context: ExecutionContext,
        *,
        campaign: CampaignSpec,
        pair: VariantPair,
        engine: _ResolvedEngine,
        subject: AgentSpec,
    ) -> VariantPairOutcome:
        """Start and watch both variants under the Campaign's own schedule."""
        run_id = context.request.run_id
        run_paths = RunPaths.for_run(self._paths, run_id)
        environment = scrubbed_child_environment(
            model=subject.model, engine=engine.installation
        )
        executable = self._registry.executable(engine.digest, "eval")
        children = {
            variant: self._build_child(
                variant=variant,
                plan=pair.plan(variant),
                executable=executable,
                environment=environment,
                run_paths=run_paths,
            )
            for variant in _VARIANT_ORDER
        }
        scheduler = VariantScheduler(
            run_store=context.run_store,
            child_registry=self._child_registry,
            poll_interval_seconds=self._poll_interval,
            grace_seconds=self._grace,
        )
        run = (
            scheduler.execute_parallel
            if campaign.execution.order is VariantSchedule.PARALLEL
            else scheduler.execute_sequential
        )
        return run(
            run_id=run_id,
            run_root=run_paths.root,
            pair=pair,
            baseline_child=children[VariantName.BASELINE],
            candidate_child=children[VariantName.CANDIDATE],
        )

    def _build_child(
        self,
        *,
        variant: VariantName,
        plan: VariantExecutionPlan,
        executable: Path,
        environment: Mapping[str, str],
        run_paths: RunPaths,
    ) -> EvaluationChild:
        """Construct one unstarted evaluation child."""
        return self._child_factory(
            variant=variant,
            argv=eval_argv(
                eval_executable=executable,
                input_config_path=Path(plan.verifiers_input_config_path),
            ),
            cwd=Path(plan.verifiers_output_dir),
            env=environment,
            stdout_path=run_paths.variant_stdout_log(variant),
            stderr_path=run_paths.variant_stderr_log(variant),
        )

    # -- the engine's reading of the evidence -------------------------------

    def _normalize(
        self,
        *,
        pair: VariantPair,
        outcome: VariantPairOutcome,
        images: Mapping[VariantName, SubjectImageResolution],
        inputs: RunInputBundle,
        validation: TasksetValidationOutcome,
        engine: _ResolvedEngine,
        lock_path: Path,
        primary_reward: str,
    ) -> dict[VariantName, VariantExecutionResult]:
        """Normalize and verify both variants, or fail the whole execution."""
        outcomes: dict[VariantName, ChildProcessOutcome] = {
            VariantName.BASELINE: outcome.baseline,
            VariantName.CANDIDATE: outcome.candidate,
        }
        manifests: dict[VariantName, ExperimentManifest] = {
            VariantName.BASELINE: inputs.baseline,
            VariantName.CANDIDATE: inputs.candidate,
        }

        results: dict[VariantName, VariantExecutionResult] = {}
        for variant in _VARIANT_ORDER:
            result = build_variant_result(
                plan=pair.plan(variant),
                outcome=outcomes[variant],
                image_resolution=images[variant],
                engine_registry=self._registry,
                engine_digest=engine.digest,
                engine_runner=engine.runner,
                taskset_lock_path=lock_path,
                timeout=self._normalize_timeout,
            )
            checks = verify_variant_execution(
                result=result,
                experiment=manifests[variant],
                taskset_lock=validation.lock,
                primary_reward=primary_reward,
                engine=engine.descriptor,
            )
            failed = [check for check in checks if check.status == "failed"]
            if failed:
                detail: list[JsonValue] = [to_json_value(check) for check in failed]
                raise VerificationError(
                    f"the {variant.value} variant's execution is not "
                    "scientifically usable",
                    code=VARIANT_NOT_USABLE,
                    details={"variant": variant.value, "checks": detail},
                )
            results[variant] = result
        return results

    def _record(
        self,
        run_paths: RunPaths,
        engine: _ResolvedEngine,
        outcome: VariantPairOutcome,
        results: dict[VariantName, VariantExecutionResult],
    ) -> RealExecutionResult:
        """Assemble what WP6 hands WP7, and write it beside the run."""
        result = RealExecutionResult(
            execution_backend="verifiers",
            engine_digest=engine.digest,
            verifiers_revision=engine.descriptor.verifiers_revision,
            schedule=outcome.schedule,
            baseline=results[VariantName.BASELINE],
            candidate=results[VariantName.CANDIDATE],
        )
        path = real_execution_result_path(run_paths.root)
        ensure_private_directory(path.parent)
        atomic_write_json(path, to_json_value(result))
        return result
