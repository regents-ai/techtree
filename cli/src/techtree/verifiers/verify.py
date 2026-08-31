"""Whether a compiled configuration survives the engine. Spec section 6.14.

The dry run is the only cheap way to ask the pinned engine what it thinks of a
Techtree configuration: it resolves the taskset plugin, narrows the environment
config to the real ``Env`` class, rejects any key the model does not declare,
and writes back the configuration it would actually run. It costs nothing, it
touches no provider, and it is where a mistyped taskset id or a seat the
environment does not declare surfaces in a second rather than after Docker has
been provisioned.

It is not, however, a validation of the *experiment*. Four things Techtree
cares about pass a dry run cleanly and fail later or never: a bundled skill
catalogue, ``disabled_tools``, a skill path that does not exist, and a config
with no taskset at all (``docs/verifiers-eval.md``, finding E3). Those are
rejected by :mod:`techtree.verifiers.config` and
:mod:`techtree.verifiers.compiler`, before anything is written. This module
asks the complementary question, and the two together are what section 6.14's
pre-execution half needs.

The resolved configuration is compared to the compiled one as a **projection**,
never byte for byte. The engine fills in ``client.base_url`` that Techtree
deliberately omitted, may add a routing header of its own, and writes out every
default Techtree never mentioned. It also records the ``--output-dir`` given on
argv rather than the one in the file, so the dry run's own redirection is
folded into the comparison instead of being excused from it. What must hold is
that nothing Techtree *did* declare came back changed.

Two settings are checked in the resolved document even though the compiled one
never mentions them, because for both the engine's default is the dangerous
answer and a flag is what turns it off: the platform upload, and whether the
rollouts are hosted through an env-server worker pool. The dry run carries the
same flags the run does, so what it resolves is what the run would do — and a
flag the engine stopped understanding is found here, before anything is spent,
rather than afterwards.

Section 6.14's post-execution half is :func:`verify_variant_execution`. It
answers one question — is this execution complete and scientifically usable —
as an ordered list of named verdicts rather than as an exception, so a caller
reads which rule failed instead of catching something and guessing. It raises
only on inputs too malformed to check at all.

A zero exit code is never sufficient. The output checks decide validity, and a
graceful cancellation maps to cancellation rather than to a scientific verdict:
a run somebody stopped did not produce a wrong answer, it produced no answer.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from techtree.engines.runner import EngineProcessResult, EngineRunner
from techtree.errors import ValidationError
from techtree.fs import ensure_private_directory
from techtree.models.campaign import SUBJECT_AGENT, AgentSpec, ModelSpec
from techtree.models.engine import EngineDescriptor
from techtree.models.experiment import ExperimentManifest
from techtree.models.validation import TasksetLock
from techtree.verifiers.child import (
    CANCELLATION_EXIT_CODE,
    DRY_RUN_NAME,
    EVAL_EXECUTABLE,
    dry_run_argv,
    write_command_log,
)
from techtree.verifiers.config import EvalToml, emitted_document
from techtree.verifiers.credentials import credential_status
from techtree.verifiers.models import (
    COMMAND_LOG_FILENAME,
    VERIFIERS_DIRECTORY,
    ExecutionCheck,
    NormalizedTrace,
    VariantExecutionResult,
    VariantName,
)
from techtree.verifiers.outputs import RESOLVED_CONFIG_PATH

__all__ = [
    "DEFAULT_DRY_RUN_TIMEOUT_SECONDS",
    "VARIANT_DRY_RUN_FAILED",
    "VARIANT_EXECUTION_UNCHECKABLE",
    "DryRunOutcome",
    "dry_run_variant_config",
    "verify_compiled_config",
    "verify_variant_execution",
]

#: Stable error code. Spec section 6.14.
VARIANT_DRY_RUN_FAILED: Final = "variant_dry_run_failed"

#: Stable error code for an execution nothing could be concluded about.
VARIANT_EXECUTION_UNCHECKABLE: Final = "variant_execution_uncheckable"

DEFAULT_DRY_RUN_TIMEOUT_SECONDS: Final = 300.0

#: The one key the engine fills in that Techtree deliberately left out, so a
#: difference there is not a disagreement. The routing header the engine may
#: also add needs no entry: Techtree declares no headers at all, so an added
#: one has nothing on the declared side to disagree with.
_ENGINE_RESOLVED_KEYS: Final[frozenset[str]] = frozenset({"client.base_url"})

#: Sentinel for "the key was not in the resolved document at all", which is a
#: different answer from "the key resolved to null" wherever null is the safe
#: value.
_MISSING: Final = object()


@dataclass(frozen=True)
class DryRunOutcome:
    """What one dry run established about one compiled configuration."""

    variant: VariantName
    process: EngineProcessResult
    resolved_config_path: Path | None
    resolved_config: dict[str, Any] | None
    checks: tuple[ExecutionCheck, ...]

    @property
    def ok(self) -> bool:
        """Whether every check passed or warned."""
        return all(check.status in ("passed", "warning") for check in self.checks)

    @property
    def failures(self) -> tuple[ExecutionCheck, ...]:
        """The checks that failed, in order."""
        return tuple(check for check in self.checks if check.status == "failed")


def dry_run_variant_config(
    *,
    engine_runner: EngineRunner,
    variant: VariantName,
    compiled: EvalToml,
    input_config_path: Path,
    dry_run_dir: Path,
    model: ModelSpec | None = None,
    timeout: float = DEFAULT_DRY_RUN_TIMEOUT_SECONDS,
) -> DryRunOutcome:
    """Resolve one compiled configuration against the installed engine.

    The child is given the engine's ordinary minimal environment. A dry run
    makes no model call, so it needs no credential, and a process that never
    receives one cannot leak one. When ``model`` is supplied the credential is
    *diagnosed* separately and reported as its own check, so that "the config
    is valid" and "the endpoint can authenticate" are two answers rather than
    one.
    """
    if not input_config_path.is_file():
        raise ValidationError(
            "the compiled evaluation config was not written before the dry run",
            code=VARIANT_DRY_RUN_FAILED,
            details={"variant": variant.value, "path": str(input_config_path)},
        )
    ensure_private_directory(dry_run_dir)

    argv = dry_run_argv(input_config_path=input_config_path, dry_run_dir=dry_run_dir)
    process = engine_runner.run(EVAL_EXECUTABLE, argv, timeout=timeout)
    # Spec section 6.19 keeps a record of the validation beside what it
    # validated, so a reviewer can see exactly what was asked and answered
    # before the run rather than inferring it from the resolved document.
    write_command_log(
        dry_run_dir / COMMAND_LOG_FILENAME,
        variant=variant,
        argv=process.argv,
        exit_code=process.exit_code,
        stdout=process.stdout,
        stderr=process.stderr,
    )

    checks: list[ExecutionCheck] = [_invocation_check(process)]
    resolved_path = dry_run_dir / DRY_RUN_NAME / RESOLVED_CONFIG_PATH
    resolved: dict[str, Any] | None = None

    if process.exit_code == 0 and resolved_path.is_file():
        resolved = _read_resolved_config(resolved_path)
        checks.append(
            ExecutionCheck(
                id="resolved_config_written",
                status="passed",
                detail=(
                    f"the engine wrote {RESOLVED_CONFIG_PATH} to the dry-run directory."
                ),
            )
        )
        # ``--output-dir`` on argv overrides the file, so the resolved document
        # names the dry-run directory rather than the real one. Comparing the
        # compiled config as it was actually handed over keeps the check exact
        # instead of excusing a whole key from it.
        checks.extend(
            verify_compiled_config(
                compiled=compiled.model_copy(update={"output_dir": str(dry_run_dir)}),
                resolved=resolved,
            )
        )
        checks.append(_output_directory_check(compiled))
    else:
        checks.append(
            ExecutionCheck(
                id="resolved_config_written",
                status="failed",
                detail=(
                    "the engine wrote no resolved configuration; the dry run "
                    "did not get far enough to resolve one."
                ),
            )
        )

    checks.append(_image_pinning_check(compiled))
    if model is not None:
        checks.append(_credential_check(model))

    return DryRunOutcome(
        variant=variant,
        process=process,
        resolved_config_path=resolved_path if resolved is not None else None,
        resolved_config=resolved,
        checks=tuple(checks),
    )


def verify_compiled_config(
    *, compiled: EvalToml, resolved: Mapping[str, Any]
) -> list[ExecutionCheck]:
    """Compare what the engine resolved against what Techtree declared.

    Declared means the document that was written, not the model behind it. The
    two differ in exactly one place and it is the place that matters: ``rich``
    is written as an explicit null, so comparing the emitted document is what
    makes the engine confirm the dashboard is off rather than leaving that
    unasked.
    """
    declared = _flatten(emitted_document(compiled))
    observed = _flatten(resolved)

    # A declared key that is simply *missing* from the resolved document is a
    # difference too, and it has to be spelled out rather than left to
    # ``get``: ``rich`` is declared as a null, so an engine that resolved it
    # into a table of dashboard settings would flatten to ``rich.show_logs``
    # and a plain ``get`` would read the absent ``rich`` back as the null it
    # was looking for.
    differences = sorted(
        key
        for key, value in declared.items()
        if key not in _ENGINE_RESOLVED_KEYS
        and (key not in observed or observed[key] != value)
    )
    checks = [
        ExecutionCheck(
            id="resolved_config_matches_compiled",
            status="passed" if not differences else "failed",
            detail=(
                "every value Techtree declared came back unchanged."
                if not differences
                else "the engine resolved a different value at "
                f"{', '.join(differences)}."
            ),
        ),
        _push_check(observed),
        _serve_check(observed),
        _subject_seat_check(observed),
    ]
    return checks


def _invocation_check(process: EngineProcessResult) -> ExecutionCheck:
    """Whether the engine's own ``eval`` accepted the configuration."""
    if process.exit_code == 0:
        return ExecutionCheck(
            id="engine_eval_accepted_config",
            status="passed",
            detail="the engine's eval entrypoint resolved the configuration.",
        )
    return ExecutionCheck(
        id="engine_eval_accepted_config",
        status="failed",
        detail=(
            f"the engine's eval entrypoint exited {process.exit_code}: "
            f"{_last_meaningful_line(process)}"
        ),
    )


def _serve_check(observed: Mapping[str, Any]) -> ExecutionCheck:
    """Whether the run the engine resolved is this process's own work.

    Hosting through the elastic env-server worker pool is the default since
    v0.3.1 (``docs/verifiers-pin-0.3.1.md``, deviation D5), and it is a default
    Techtree cannot take: the supervision a real run depends on watches one
    child and tears its containers down through one process group (decisions
    document 0029). ``--no-serve`` is what turns it off, and this is the engine
    confirming that it did rather than Techtree assuming the flag still means
    what it meant.
    """
    in_process = observed.get("serve", _MISSING) is None
    return ExecutionCheck(
        id="rollouts_run_in_process",
        status="passed" if in_process else "failed",
        detail=(
            "the resolved configuration records no worker pool, so the "
            "rollouts are the evaluation child's own work."
            if in_process
            else "the resolved configuration would host the rollouts through "
            "an env-server worker pool rather than in the evaluation child."
        ),
    )


def _push_check(observed: Mapping[str, Any]) -> ExecutionCheck:
    """Whether the platform upload is off in the configuration the engine read."""
    disabled = observed.get("push") is False
    return ExecutionCheck(
        id="platform_push_disabled",
        status="passed" if disabled else "failed",
        detail=(
            "the resolved configuration records push = false, so no episode "
            "leaves this machine."
            if disabled
            else "the resolved configuration would upload this run's episodes "
            "to the Prime platform."
        ),
    )


def _subject_seat_check(observed: Mapping[str, Any]) -> ExecutionCheck:
    """Whether the environment the engine resolved really names the subject seat."""
    seat_keys = [key for key in observed if key.startswith("env.subject.")]
    agent_keys = [key for key in observed if key.startswith("env.agent.")]
    if seat_keys and not agent_keys:
        return ExecutionCheck(
            id="named_subject_seat_resolved",
            status="passed",
            detail=(
                "the resolved environment declares a subject seat, so every "
                "trace will record agent.name == 'subject'."
            ),
        )
    return ExecutionCheck(
        id="named_subject_seat_resolved",
        status="failed",
        detail=(
            "the resolved environment does not declare a subject seat; the "
            "reference package must export the named-subject environment."
        ),
    )


def _output_directory_check(compiled: EvalToml) -> ExecutionCheck:
    """Whether the real run would write inside the run's own directory."""
    output_dir = Path(compiled.output_dir)
    inside = output_dir.is_absolute() and VERIFIERS_DIRECTORY in output_dir.parts
    return ExecutionCheck(
        id="output_directory_is_run_owned",
        status="passed" if inside else "failed",
        detail=(
            f"the real run would write to {compiled.output_dir}, inside the "
            "run's own evaluation tree."
            if inside
            else f"the real run would write to {compiled.output_dir}, which is "
            "not inside the run's own evaluation tree."
        ),
    )


def _image_pinning_check(compiled: EvalToml) -> ExecutionCheck:
    """Whether the subject runtime names content rather than a moving tag."""
    runtime = compiled.env.subject.runtime
    if runtime.image_is_digest_pinned:
        return ExecutionCheck(
            id="runtime_image_digest_pinned",
            status="passed",
            detail="the subject runtime image is pinned by content digest.",
        )
    return ExecutionCheck(
        id="runtime_image_digest_pinned",
        status="warning",
        detail=(
            f"the subject runtime image {runtime.image!r} is not pinned by "
            "content digest, so what runs could change without the Campaign "
            "changing."
        ),
    )


def _credential_check(model: ModelSpec) -> ExecutionCheck:
    """Whether the evaluation endpoint can authenticate, diagnosed on its own."""
    status = credential_status(model)
    return ExecutionCheck(
        id="evaluation_credential_available",
        status="passed" if status.available else "failed",
        detail=status.detail,
    )


def _read_resolved_config(path: Path) -> dict[str, Any]:
    """Read the configuration the engine wrote back."""
    try:
        document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return document
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(
            "the engine's resolved configuration could not be read",
            code=VARIANT_DRY_RUN_FAILED,
            details={"path": str(path)},
        ) from error


def _flatten(document: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested tables into dotted keys so two documents can be compared."""
    flat: dict[str, Any] = {}
    for key, value in document.items():
        dotted = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, prefix=f"{dotted}."))
        else:
            flat[dotted] = value
    return flat


def _last_meaningful_line(process: EngineProcessResult) -> str:
    """Return the most useful line of a failed invocation's output.

    The engine renders configuration errors as a box-drawn panel, so the raw
    tail is mostly border. This keeps the last line that carries characters
    other than the frame.
    """
    frame = set("│╭╮╰╯─ ")
    for stream in (process.stderr, process.stdout):
        lines = [
            line.strip("│ ").strip()
            for line in reversed(stream.splitlines())
            if line.strip() and set(line) - frame
        ]
        if lines:
            return lines[0]
    return "<no output>"


# ---------------------------------------------------------------------------
# After the run: is this execution scientifically usable
# ---------------------------------------------------------------------------


def verify_variant_execution(
    *,
    result: VariantExecutionResult,
    experiment: ExperimentManifest,
    taskset_lock: TasksetLock,
    primary_reward: str,
    engine: EngineDescriptor | None = None,
) -> list[ExecutionCheck]:
    """Return ordered checks over one completed variant.

    Raises only when the inputs cannot be checked at all — a manifest with no
    subject agent leaves nothing to compare an execution against. Everything
    else is reported as a verdict, because "which rule did this break" is the
    question a caller actually has.
    """
    subject = experiment.configuration.agents.get(SUBJECT_AGENT)
    if subject is None:
        raise ValidationError(
            f"the experiment manifest defines no {SUBJECT_AGENT!r} agent, so "
            "there is nothing to verify this execution against",
            code=VARIANT_EXECUTION_UNCHECKABLE,
            details={"manifest_id": experiment.id, "variant": result.variant.value},
        )

    checks = [_completion_check(result)]
    checks.extend(_membership_checks(result, taskset_lock))
    checks.extend(_trace_checks(result, subject, primary_reward))
    checks.append(_manifest_check(result, experiment))
    if engine is not None:
        checks.append(_pin_check(result, engine))
    return checks


def _completion_check(result: VariantExecutionResult) -> ExecutionCheck:
    """Whether the child finished rather than being stopped."""
    outcome = result.child_outcome
    if outcome.cancelled or outcome.exit_code == CANCELLATION_EXIT_CODE:
        return ExecutionCheck(
            id="child_completed",
            status="failed",
            detail=(
                "the evaluation was cancelled, so it produced no answer rather "
                "than a wrong one."
            ),
        )
    if outcome.exit_code != 0:
        return ExecutionCheck(
            id="child_completed",
            status="failed",
            detail=f"the evaluation child exited {outcome.exit_code}.",
        )
    return ExecutionCheck(
        id="child_completed",
        status="passed",
        detail="the evaluation child ran to completion and was not cancelled.",
    )


def _membership_checks(
    result: VariantExecutionResult, taskset_lock: TasksetLock
) -> list[ExecutionCheck]:
    """Whether exactly the committed tasks were scored, in the committed order."""
    observed = [episode.task_hash for episode in result.episodes]
    committed = list(taskset_lock.ordered_task_hashes)

    count = ExecutionCheck(
        id="episode_count",
        status="passed" if len(observed) == len(committed) else "failed",
        detail=(
            f"{len(observed)} episodes for {len(committed)} committed tasks."
            if len(observed) == len(committed)
            else f"{len(observed)} episodes were recorded for {len(committed)} "
            "committed tasks."
        ),
    )
    ordered = ExecutionCheck(
        id="ordered_task_membership",
        status="passed" if observed == committed else "failed",
        detail=(
            "the normalized episodes cover exactly the committed tasks, in the "
            "committed order."
            if observed == committed
            else "the normalized episodes do not match the committed membership; "
            "pairing joins on task hash, never on position."
        ),
    )
    positions = [episode.task_position for episode in result.episodes]
    numbered = ExecutionCheck(
        id="task_positions_are_membership_positions",
        status="passed" if positions == list(range(len(observed))) else "failed",
        detail=(
            "every episode carries its membership position."
            if positions == list(range(len(observed)))
            else f"episode positions are not 0..{len(observed) - 1} exactly once."
        ),
    )

    episode_ids = [episode.episode_id for episode in result.episodes]
    unique = ExecutionCheck(
        id="episode_ids_unique",
        status="passed" if len(set(episode_ids)) == len(episode_ids) else "failed",
        detail=(
            "every episode has its own identifier."
            if len(set(episode_ids)) == len(episode_ids)
            else "two episodes share an identifier."
        ),
    )
    completed = [episode for episode in result.episodes if not episode.ok]
    finished = ExecutionCheck(
        id="all_episodes_completed",
        status="passed" if not completed else "failed",
        detail=(
            "every episode completed."
            if not completed
            else f"{len(completed)} episode(s) did not complete."
        ),
    )
    return [count, ordered, numbered, unique, finished]


def _trace_checks(
    result: VariantExecutionResult, subject: AgentSpec, primary_reward: str
) -> list[ExecutionCheck]:
    """Whether every trace is the subject the manifest declared, scored."""
    traces = [trace for episode in result.episodes for trace in episode.traces]
    per_episode = {len(episode.traces) for episode in result.episodes}

    checks = [
        ExecutionCheck(
            id="one_subject_trace_per_episode",
            status="passed" if per_episode <= {1} else "failed",
            detail=(
                "each episode carries exactly one subject trace."
                if per_episode <= {1}
                else f"episodes carry {sorted(per_episode)} traces."
            ),
        )
    ]
    trace_ids = [trace.trace_id for trace in traces]
    checks.append(
        ExecutionCheck(
            id="trace_ids_unique",
            status="passed" if len(set(trace_ids)) == len(trace_ids) else "failed",
            detail=(
                "every trace has its own identifier."
                if len(set(trace_ids)) == len(trace_ids)
                else "two traces share an identifier."
            ),
        )
    )

    declared_skills = sorted(artifact.digest for artifact in subject.harness.skills)
    expectations: list[tuple[str, str, Any, Any]] = [
        ("model_id_matches", "model", subject.model.model_id, None),
        ("harness_id_matches", "harness", subject.harness.id, None),
        ("harness_version_matches", "harness version", subject.harness.version, None),
        ("runtime_image_matches", "runtime image", subject.runtime.image, None),
    ]
    observed: dict[str, set[Any]] = {
        "model_id_matches": {trace.model_id for trace in traces},
        "harness_id_matches": {trace.harness_id for trace in traces},
        "harness_version_matches": {trace.harness_version for trace in traces},
        "runtime_image_matches": {trace.runtime.image for trace in traces},
    }
    for identifier, label, expected, _ in expectations:
        seen = observed[identifier]
        checks.append(
            ExecutionCheck(
                id=identifier,
                status="passed" if seen == {expected} else "failed",
                detail=(
                    f"every trace ran the declared {label}."
                    if seen == {expected}
                    else f"the declared {label} is {expected!r}; traces recorded "
                    f"{sorted(str(value) for value in seen)}."
                ),
            )
        )

    bundled = {trace.use_bundled_skill for trace in traces}
    checks.append(
        ExecutionCheck(
            id="bundled_skills_disabled",
            status="passed" if bundled <= {False} else "failed",
            detail=(
                "no trace enabled the harness's bundled skill catalogue."
                if bundled <= {False}
                else "a trace ran with the bundled skill catalogue enabled."
            ),
        )
    )
    skills = {tuple(sorted(trace.skill_root_digests)) for trace in traces}
    checks.append(
        ExecutionCheck(
            id="skill_digests_match_variant",
            status="passed" if skills <= {tuple(declared_skills)} else "failed",
            detail=(
                f"every trace carried the {len(declared_skills)} skill(s) this "
                "variant declares."
                if skills <= {tuple(declared_skills)}
                else "a trace carried skills the variant does not declare."
            ),
        )
    )
    runtimes = {trace.runtime.kind for trace in traces}
    checks.append(
        ExecutionCheck(
            id="runtime_is_docker",
            status="passed" if runtimes <= {"docker"} else "failed",
            detail=(
                "every trace ran in a Docker runtime."
                if runtimes <= {"docker"}
                else f"traces ran on {sorted(runtimes)}."
            ),
        )
    )
    roles = {trace.agent_role for trace in traces}
    checks.append(
        ExecutionCheck(
            id="every_trace_is_the_subject",
            status="passed" if roles <= {SUBJECT_AGENT} else "failed",
            detail=(
                f"every trace records the {SUBJECT_AGENT!r} role."
                if roles <= {SUBJECT_AGENT}
                else f"traces recorded the roles {sorted(roles)}."
            ),
        )
    )
    incomplete = [trace for trace in traces if not trace.ok]
    checks.append(
        ExecutionCheck(
            id="all_traces_completed",
            status="passed" if not incomplete else "failed",
            detail=(
                "every trace completed."
                if not incomplete
                else f"{len(incomplete)} trace(s) did not complete."
            ),
        )
    )
    checks.append(_primary_reward_check(traces, primary_reward))
    checks.append(_tool_inventory_check(traces))
    return checks


def _primary_reward_check(
    traces: list[NormalizedTrace], primary_reward: str
) -> ExecutionCheck:
    """Whether the reward the comparison turns on was scored everywhere."""
    unscored = [trace for trace in traces if trace.reward(primary_reward) is None]
    if unscored:
        return ExecutionCheck(
            id="primary_reward_present",
            status="failed",
            detail=(
                f"{len(unscored)} trace(s) carry no {primary_reward!r} reward, "
                "which is the reward the comparison is decided on."
            ),
        )
    return ExecutionCheck(
        id="primary_reward_present",
        status="passed",
        detail=f"every trace scored {primary_reward!r}.",
    )


def _tool_inventory_check(traces: list[NormalizedTrace]) -> ExecutionCheck:
    """Whether each trace's recorded tool inventory is internally coherent."""
    for trace in traces:
        names = [tool.name for tool in trace.tools]
        if len(set(names)) != len(names):
            return ExecutionCheck(
                id="tool_inventory_valid",
                status="failed",
                detail=f"trace {trace.trace_id} advertises a tool name twice.",
            )
    return ExecutionCheck(
        id="tool_inventory_valid",
        status="passed",
        detail="every trace's tool inventory names each tool once.",
    )


def _manifest_check(
    result: VariantExecutionResult, experiment: ExperimentManifest
) -> ExecutionCheck:
    """Whether this result belongs to the manifest it is being checked against."""
    from techtree.canonical import digest_object

    expected = digest_object(experiment)
    matches = result.experiment_manifest_digest == expected
    return ExecutionCheck(
        id="result_matches_experiment",
        status="passed" if matches else "failed",
        detail=(
            "the result was produced from this experiment manifest."
            if matches
            else "the result names a different experiment manifest."
        ),
    )


def _pin_check(
    result: VariantExecutionResult, engine: EngineDescriptor
) -> ExecutionCheck:
    """Whether the build that produced this result is the build we pinned.

    Nothing is inferred here. Every upstream trace records the Verifiers
    version and commit that wrote it (``docs/verifiers-eval.md``) and the
    normalizer carries both across, so this compares evidence against the
    engine descriptor rather than trusting a caller's claim about which engine
    ran.
    """
    observed = {
        (trace.verifiers_version, trace.verifiers_revision)
        for episode in result.episodes
        for trace in episode.traces
    }
    expected = (engine.verifiers_version, engine.verifiers_revision)
    if observed == {expected}:
        return ExecutionCheck(
            id="verifiers_pin_matches_engine",
            status="passed",
            detail=(
                f"every trace was produced by Verifiers {expected[0]} at "
                f"{expected[1]}, which is what the engine descriptor pins."
            ),
        )
    return ExecutionCheck(
        id="verifiers_pin_matches_engine",
        status="failed",
        detail=(
            f"the engine descriptor pins Verifiers {expected[0]} at "
            f"{expected[1]}, but the traces record "
            f"{sorted(f'{version} at {revision}' for version, revision in observed)}."
        ),
    )
