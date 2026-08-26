"""The files one variant's evaluation must have left behind. Spec section 6.13.

A real ``eval`` run leaves three files Techtree keeps: the resolved
configuration, the raw upstream episodes, and the upstream log. The normalizer
that the engine runs over them does not replace any of them (spec section 6.12)
— Techtree retains raw upstream evidence *and* its normalized projection,
because a projection nobody can check against its source is a claim rather than
evidence.

*Two of the three live in subdirectories now.* The released engine writes
``configs/resolved/eval.json`` and ``logs/attempt_<n>/eval.log`` rather than the
flat ``config.toml`` and ``eval.log`` of the development build
(``docs/verifiers-pin-0.3.1.md``, deviations D1 and D5), and the resolved
configuration is JSON because only JSON round-trips the explicit nulls the
engine writes. The attempt number is ``1`` and can be nothing else: an attempt
directory is minted per *launch*, and Techtree launches a run directory exactly
once — it never resumes and never re-enters one (deviation D3).

*The engine also writes ``logs/latest``, and Techtree ignores it.* It is a
symbolic link to the current attempt directory, repointed by every later
launch. A digest taken over a link is not a digest of the file it names, and a
path that another launch can silently redirect is not a citation, so the
evidence this module hashes is the attempt directory itself. Nothing here
follows, records or hashes the link.

*The engine writes no copy of the launch configuration for a Techtree run.* It
copies the launch file verbatim to ``configs/eval.toml`` only when that file is
TOML, and Techtree's is ``input.json`` (deviation D5). Nothing is lost: the
compiled input is already the run's own file and already digested where it was
written.

A dry-run directory is deliberately not accepted here. Dry run writes only the
resolved configuration (``docs/verifiers-eval.md``, finding E2), so applying
the run's requirements to it would report a truncated run where there was never
a run at all.

``build_variant_result`` does not interpret anything itself. It hands the raw
directory to the engine tool ``normalize_eval_output.py``, which runs under the
engine's own interpreter with the pinned Verifiers wire models available to it
(decisions document 0003 A3). Reading a Trace with the version of Verifiers
that wrote it is the difference between interpreting the record and guessing at
it, and it is why the interpretation is pinned exactly as tightly as the
library.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import sha256_digest_bytes
from techtree.engines.registry import EngineRegistry
from techtree.engines.runner import EngineRunner
from techtree.errors import EngineError, ValidationError
from techtree.models.base import ArtifactRef, Digest
from techtree.verifiers.models import (
    NORMALIZED_EPISODES_FILENAME,
    ChildProcessOutcome,
    NormalizedEpisode,
    SubjectImageResolution,
    VariantExecutionPlan,
    VariantExecutionResult,
)

__all__ = [
    "DEFAULT_NORMALIZE_TIMEOUT_SECONDS",
    "EVAL_LOG_MEDIA_TYPE",
    "EVAL_LOG_PATH",
    "NORMALIZED_EPISODES_FILENAME",
    "NORMALIZED_EPISODES_MEDIA_TYPE",
    "NORMALIZE_EVAL_OUTPUT_TOOL",
    "RESOLVED_CONFIG_MEDIA_TYPE",
    "RESOLVED_CONFIG_PATH",
    "TRACES_FILENAME",
    "TRACES_MEDIA_TYPE",
    "VARIANT_OUTPUT_INCOMPLETE",
    "artifact_for",
    "build_variant_result",
    "normalize_eval_output",
    "read_normalized_episodes",
    "require_output_files",
    "required_output_paths",
]

#: Stable error code. Spec section 6.13.
VARIANT_OUTPUT_INCOMPLETE: Final = "variant_output_incomplete"

#: The configuration the engine resolved and wrote back, relative to the run's
#: own directory. Nested and JSON since v0.3.1 (deviation D1), and the same
#: relative path whether the run was real or a dry run, which is what lets the
#: validation confirm the path the real run's reader will use.
RESOLVED_CONFIG_PATH: Final = "configs/resolved/eval.json"

TRACES_FILENAME: Final = "traces.jsonl"

#: This launch's log. One attempt directory is minted per launch and Techtree
#: launches once, so the run's log is always attempt one's (deviation D5). The
#: ``logs/latest`` link beside it is deliberately not what is read: see the
#: module docstring.
EVAL_LOG_PATH: Final = "logs/attempt_1/eval.log"

#: The engine helper that turns raw episodes into the protocol projection. It
#: lives inside the digested bundle (decisions document 0003 A3).
NORMALIZE_EVAL_OUTPUT_TOOL: Final = "normalize_eval_output.py"

RESOLVED_CONFIG_MEDIA_TYPE: Final = "application/json"
TRACES_MEDIA_TYPE: Final = "application/x-ndjson"
EVAL_LOG_MEDIA_TYPE: Final = "text/plain"
NORMALIZED_EPISODES_MEDIA_TYPE: Final = "application/x-ndjson"

DEFAULT_NORMALIZE_TIMEOUT_SECONDS: Final = 300.0


def required_output_paths(output_dir: Path) -> dict[str, Path]:
    """Return the three files a completed evaluation writes.

    ``output_dir`` is the run's own directory — the one ``--run.name`` pins,
    one level below the directory the compiled configuration groups runs under.
    """
    return {
        "config": output_dir / RESOLVED_CONFIG_PATH,
        "traces": output_dir / TRACES_FILENAME,
        "eval_log": output_dir / EVAL_LOG_PATH,
    }


def require_output_files(output_dir: Path) -> dict[str, Path]:
    """Return the three files, or refuse.

    An empty ``traces.jsonl`` counts as missing. Upstream truncates the file to
    empty before the first rollout, so its emptiness after the child exits
    means no episode ever completed, which is a failed run rather than a run
    with no results.
    """
    paths = required_output_paths(output_dir)
    missing = sorted(name for name, path in paths.items() if not path.is_file())
    if missing:
        raise ValidationError(
            "the evaluation output is incomplete; "
            f"missing {', '.join(missing)} under {output_dir.name}",
            code=VARIANT_OUTPUT_INCOMPLETE,
            details={"output_dir": str(output_dir), "missing": list(missing)},
        )
    if paths["traces"].stat().st_size == 0:
        raise ValidationError(
            "the evaluation recorded no episodes; traces.jsonl is empty",
            code=VARIANT_OUTPUT_INCOMPLETE,
            details={"output_dir": str(output_dir), "missing": ["episodes"]},
        )
    return paths


def artifact_for(path: Path, media_type: str) -> ArtifactRef:
    """Hash a file's exact bytes and build its artifact reference."""
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ValidationError(
            f"the evaluation artifact {path.name} could not be read",
            code=VARIANT_OUTPUT_INCOMPLETE,
            details={"path": str(path)},
        ) from error
    if not data:
        raise ValidationError(
            f"the evaluation artifact {path.name} is empty",
            code=VARIANT_OUTPUT_INCOMPLETE,
            details={"path": str(path)},
        )
    return ArtifactRef(
        digest=sha256_digest_bytes(data),
        media_type=media_type,
        size=len(data),
        relative_path=None,
    )


def read_normalized_episodes(path: Path) -> list[NormalizedEpisode]:
    """Parse every record of a normalized JSONL file.

    A missing final newline is a refusal rather than a shrug. The normalizer
    writes whole records; a file that stops mid-line is a file that was
    truncated, and parsing the part that survived would silently drop an
    episode from a comparison that claims to cover every task.
    """
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ValidationError(
            "the normalized episode file could not be read",
            code=VARIANT_OUTPUT_INCOMPLETE,
            details={"path": str(path)},
        ) from error

    if not raw:
        raise ValidationError(
            "the normalized episode file is empty",
            code=VARIANT_OUTPUT_INCOMPLETE,
            details={"path": str(path)},
        )
    if not raw.endswith(b"\n"):
        raise ValidationError(
            "the normalized episode file does not end with a newline, so its "
            "last record is incomplete",
            code=VARIANT_OUTPUT_INCOMPLETE,
            details={"path": str(path)},
        )

    episodes: list[NormalizedEpisode] = []
    for number, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            raise ValidationError(
                f"the normalized episode file has a blank record at line {number}",
                code=VARIANT_OUTPUT_INCOMPLETE,
                details={"path": str(path), "line": number},
            )
        episodes.append(_parse_episode(line, path=path, number=number))
    return episodes


def _parse_episode(line: str, *, path: Path, number: int) -> NormalizedEpisode:
    """Parse one normalized record, or refuse with its line number."""
    try:
        return NormalizedEpisode.model_validate_json(line)
    except PydanticValidationError as error:
        detail = error.errors()[0]["msg"]
        raise ValidationError(
            f"the normalized episode at line {number} is malformed: {detail}",
            code=VARIANT_OUTPUT_INCOMPLETE,
            details={"path": str(path), "line": number},
        ) from error
    except json.JSONDecodeError as error:
        raise ValidationError(
            f"the normalized episode at line {number} is not JSON",
            code=VARIANT_OUTPUT_INCOMPLETE,
            details={"path": str(path), "line": number},
        ) from error


# ---------------------------------------------------------------------------
# The engine's own interpretation
# ---------------------------------------------------------------------------


def normalize_eval_output(
    *,
    engine_registry: EngineRegistry,
    engine_digest: Digest,
    engine_runner: EngineRunner,
    output_dir: Path,
    taskset_lock_path: Path,
    experiment_manifest_path: Path,
    destination: Path,
    timeout: float = DEFAULT_NORMALIZE_TIMEOUT_SECONDS,
) -> Path:
    """Run the engine's normalizer over one variant's raw output.

    Nothing about the upstream record is interpreted on this side of the
    boundary. The helper runs under the engine's interpreter, refuses anything
    it cannot join onto the Campaign's committed membership, and writes the
    projection ordered by that membership rather than by completion order.
    """
    script = engine_registry.tool_path(engine_digest, NORMALIZE_EVAL_OUTPUT_TOOL)
    result = engine_runner.run_python_script(
        script,
        [
            "--output-dir",
            str(output_dir),
            "--membership",
            str(taskset_lock_path),
            "--experiment-manifest",
            str(experiment_manifest_path),
            "--output",
            str(destination),
        ],
        timeout=timeout,
    )
    if result.exit_code != 0:
        raise EngineError(
            "the engine could not normalize the evaluation output: "
            f"{_last_line(result.stderr) or _last_line(result.stdout)}",
            code="eval_normalization_failed",
            details={
                "engine_digest": engine_digest,
                "output_dir": str(output_dir),
                "exit_code": result.exit_code,
            },
        )
    return destination


def build_variant_result(
    *,
    plan: VariantExecutionPlan,
    outcome: ChildProcessOutcome,
    image_resolution: SubjectImageResolution,
    engine_registry: EngineRegistry,
    engine_digest: Digest,
    engine_runner: EngineRunner,
    taskset_lock_path: Path,
    timeout: float = DEFAULT_NORMALIZE_TIMEOUT_SECONDS,
) -> VariantExecutionResult:
    """Assemble one variant's complete result from what the child left behind.

    Raw evidence and its projection are both retained and both hashed. The
    projection is what later stages read; the raw files are what makes the
    projection checkable, and a receipt that cited only the tidy document would
    be asking to be trusted rather than verified.
    """
    if outcome.variant is not plan.variant:
        raise ValidationError(
            f"a {plan.variant.value} plan cannot be completed by a "
            f"{outcome.variant.value} child process",
            code=VARIANT_OUTPUT_INCOMPLETE,
            details={"plan": plan.variant.value, "outcome": outcome.variant.value},
        )

    output_dir = Path(plan.verifiers_output_dir)
    paths = require_output_files(output_dir)
    destination = output_dir / NORMALIZED_EPISODES_FILENAME

    normalize_eval_output(
        engine_registry=engine_registry,
        engine_digest=engine_digest,
        engine_runner=engine_runner,
        output_dir=output_dir,
        taskset_lock_path=taskset_lock_path,
        experiment_manifest_path=Path(plan.experiment_manifest_path),
        destination=destination,
        timeout=timeout,
    )
    episodes = read_normalized_episodes(destination)

    if len(episodes) != plan.task_count:
        raise ValidationError(
            f"the {plan.variant.value} variant normalized {len(episodes)} "
            f"episodes for {plan.task_count} committed tasks",
            code=VARIANT_OUTPUT_INCOMPLETE,
            details={
                "variant": plan.variant.value,
                "normalized": len(episodes),
                "expected": plan.task_count,
            },
        )

    return VariantExecutionResult(
        variant=plan.variant,
        experiment_manifest_digest=plan.experiment_manifest_digest,
        resolved_verifiers_config=artifact_for(
            paths["config"], RESOLVED_CONFIG_MEDIA_TYPE
        ),
        raw_traces=artifact_for(paths["traces"], TRACES_MEDIA_TYPE),
        eval_log=artifact_for(paths["eval_log"], EVAL_LOG_MEDIA_TYPE),
        normalized_episodes=artifact_for(destination, NORMALIZED_EPISODES_MEDIA_TYPE),
        child_outcome=outcome,
        image_resolution=image_resolution,
        episodes=episodes,
    )


def _last_line(stream: str) -> str:
    """Return the last line that says something."""
    for line in reversed(stream.splitlines()):
        if line.strip():
            return line.strip()
    return ""
