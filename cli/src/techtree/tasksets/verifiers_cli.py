"""Driving the pinned Verifiers validator. Spec section 21.4.

This module is the whole of Techtree's contact with the upstream ``validate``
command, and every line of it is shaped by what the PI0 preflight actually
observed (``docs/verifiers-pin.md``) rather than by what the specification
assumed.

*The exit code is not the verdict* (finding C2). ``validate`` exits ``0`` when
every task in a taskset fails, because its status reports runner health. So
:meth:`VerifiersValidationRunner.run` returns the process result as data and
refuses to interpret it; validity is read from ``summary.json`` and nowhere
else.

*The summary is nested* (finding C1). The five outcome counts the protocol
models at the top level live under ``outcomes`` upstream, and the document
carries ``owed``, ``terminal``, and ``checks`` besides. The file is therefore
*projected* into :class:`~techtree.models.validation.UpstreamValidationSummary`
field by field and never validated as one.

*Per-check counts are optional* (finding C1 again). ``checks`` appears only when
both checks ran. Techtree always runs both, so its absence is an anomaly worth
reporting rather than a shape to tolerate — but it is read through an accessor
that can say "the validator reported none" instead of raising a parse error a
caller cannot act on.

*Row order is completion order* (finding C0). ``results.jsonl`` is appended as
each isolated check finishes, so its bytes differ between two identical runs.
Nothing here reads it: turning those rows into deterministic evidence is the
engine helper ``normalize_validation.py``'s job, invoked through
:meth:`VerifiersValidationRunner.normalize`, which joins on ``task_position``
and ``task_key`` and sorts by position.

*Scripts are addressed absolutely* (finding C3). The pinned build installs a
console script called plain ``validate``; :class:`EngineRunner` resolves it
inside the engine's own environment and never through ``PATH``.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import sha256_digest_bytes
from techtree.engines.registry import EngineRegistry
from techtree.engines.runner import EngineProcessResult, EngineRunner
from techtree.errors import EngineError, ValidationError
from techtree.models.base import ArtifactRef, Digest
from techtree.models.validation import (
    UpstreamValidationSummary,
    ValidationEvidence,
)

__all__ = [
    "NORMALIZE_VALIDATION_TOOL",
    "VALIDATE_EXECUTABLE",
    "VALIDATION_FILENAMES",
    "VALIDATION_TIMEOUT_SECONDS",
    "UpstreamCheckCounts",
    "VerifiersValidationRunner",
    "validate_argv",
]

#: The console script the pinned Verifiers build installs. Generic enough to
#: collide with anything on ``PATH``, which is why it is only ever run through
#: the engine's absolute path (``docs/verifiers-pin.md``, finding C3).
VALIDATE_EXECUTABLE: Final = "validate"

#: The engine helper that turns raw validator output into deterministic
#: evidence. It lives inside the digested bundle (decisions document 0003 A3).
NORMALIZE_VALIDATION_TOOL: Final = "normalize_validation.py"

#: Exactly the files one validation run writes, in the order a receipt lists
#: them (``docs/verifiers-pin.md``, claim 7). Nothing else appears, and a
#: missing one is a broken run rather than a smaller one.
VALIDATION_FILENAMES: Final[tuple[str, ...]] = (
    "config.toml",
    "results.jsonl",
    "summary.json",
    "validate.log",
)

#: Model-free validation of the reference taskset finishes in seconds. The
#: limit exists to end a hung validator, not to police performance.
VALIDATION_TIMEOUT_SECONDS: Final = 1800.0

#: How the validator spells the mode in which both checks run.
_BOTH_CHECKS: Final = "all"

#: The two per-task checks a ``mode = "all"`` run performs.
GOLD_CHECK: Final = "gold"
SETUP_CHECK: Final = "setup"

#: The five outcome counts, at whatever depth they appear.
_OUTCOME_KEYS: Final[tuple[str, ...]] = (
    "valid",
    "invalid",
    "error",
    "timeout",
    "missing",
)

_SUMMARY_FILE: Final = "summary.json"
_JSON_MEDIA_TYPE: Final = "application/json"
_MEDIA_TYPES: Final[Mapping[str, str]] = {
    "config.toml": "application/toml",
    "results.jsonl": "application/x-ndjson",
    "summary.json": _JSON_MEDIA_TYPE,
    "validate.log": "text/plain",
}

_EVIDENCE_FILENAME: Final = "evidence.json"
_TEMPORARY_PREFIX: Final = "techtree-normalize-"


class UpstreamCheckCounts:
    """The five outcome counts for one of the validator's two checks.

    A plain value object rather than a protocol model: these counts are read
    to build a :class:`~techtree.models.validation.ValidationCheck` and are
    never written anywhere, so giving them a schema version would claim a
    stability nothing depends on.
    """

    __slots__ = ("error", "invalid", "missing", "timeout", "valid")

    def __init__(
        self,
        *,
        valid: int,
        invalid: int,
        error: int,
        timeout: int,
        missing: int,
    ) -> None:
        self.valid = valid
        self.invalid = invalid
        self.error = error
        self.timeout = timeout
        self.missing = missing

    @property
    def total(self) -> int:
        """Return how many verdicts this check accounted for."""
        return self.valid + self.invalid + self.error + self.timeout + self.missing

    @property
    def passed(self) -> bool:
        """Return whether every task this check saw was valid."""
        return self.total > 0 and self.valid == self.total

    def summary(self) -> str:
        """Describe the counts in the order a reader cares about them."""
        return (
            f"{self.valid} valid, {self.invalid} invalid, {self.error} errored, "
            f"{self.timeout} timed out, {self.missing} missing"
        )


def validate_argv(*, taskset_id: str, num_tasks: int, output_dir: Path) -> list[str]:
    """Return the pinned validate arguments, without the executable.

    Spelled once, here, because this exact form is what the PI0 preflight
    proved and what a :class:`~techtree.models.validation.ValidationMethod`
    claims. ``--runtime.type subprocess`` is mandatory — upstream defaults to
    docker — and ``--rich false`` replaces a live dashboard with one log line
    per task, which is what a captured subprocess wants.
    """
    return [
        taskset_id,
        "--num-tasks",
        str(num_tasks),
        "--runtime.type",
        "subprocess",
        "--output-dir",
        str(output_dir),
        "--rich",
        "false",
    ]


class VerifiersValidationRunner:
    """Runs and reads one model-free validation inside the managed engine.

    Constructed from a registry and an engine digest rather than from a bare
    :class:`~techtree.engines.runner.EngineRunner`, matching
    :class:`~techtree.tasksets.resolver.TasksetResolver`: normalizing the
    output needs a bundled helper, and only the registry can say where a
    bundled helper lives (decisions document 0003 A3).
    """

    def __init__(
        self,
        registry: EngineRegistry,
        engine_digest: Digest,
        *,
        timeout_seconds: float = VALIDATION_TIMEOUT_SECONDS,
    ) -> None:
        self._registry = registry
        self._engine_digest = engine_digest
        self._runner = EngineRunner(registry, engine_digest)
        self._timeout_seconds = timeout_seconds

    # -- running -----------------------------------------------------------

    def run(
        self,
        *,
        taskset_id: str,
        num_tasks: int,
        output_dir: Path,
    ) -> EngineProcessResult:
        """Invoke the pinned validate command and return what the process did.

        The result is data. A zero exit code means the validator ran, not that
        the taskset is valid (``docs/verifiers-pin.md``, finding C2), so the
        only failure this raises is one where no summary could exist at all.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        result = self._runner.run(
            VALIDATE_EXECUTABLE,
            validate_argv(
                taskset_id=taskset_id,
                num_tasks=num_tasks,
                output_dir=output_dir,
            ),
            timeout=self._timeout_seconds,
        )

        if not (output_dir / _SUMMARY_FILE).is_file():
            raise EngineError(
                f"the validator produced no summary for taskset {taskset_id}: "
                f"{_last_line(result.stderr)}",
                code="taskset_validation_failed",
                details={
                    "taskset_id": taskset_id,
                    "engine_digest": self._engine_digest,
                    "exit_code": result.exit_code,
                },
            )
        return result

    def normalize(
        self,
        output_dir: Path,
        *,
        taskset_lock_digest: Digest,
    ) -> ValidationEvidence:
        """Return the deterministic evidence the engine derived from a run.

        The transformation happens inside the engine because only the engine
        can name the Verifiers commit that actually produced the output. The
        helper writes readable JSON to a scratch file; the caller decides where
        the canonical bytes finally live.
        """
        script = self._registry.tool_path(
            self._engine_digest, NORMALIZE_VALIDATION_TOOL
        )

        with tempfile.TemporaryDirectory(prefix=_TEMPORARY_PREFIX) as directory:
            destination = Path(directory) / _EVIDENCE_FILENAME
            result = self._runner.run_python_script(
                script,
                [
                    "--results-dir",
                    str(output_dir),
                    "--taskset-lock-digest",
                    taskset_lock_digest,
                    "--output",
                    str(destination),
                ],
                timeout=self._timeout_seconds,
            )
            if result.exit_code != 0:
                raise EngineError(
                    "the engine could not normalize this validation run: "
                    f"{_last_line(result.stderr or result.stdout)}",
                    code="validation_evidence_unavailable",
                    details={
                        "engine_digest": self._engine_digest,
                        "exit_code": result.exit_code,
                    },
                )
            raw = destination.read_bytes()

        try:
            return ValidationEvidence.model_validate_json(raw)
        except PydanticValidationError as error:
            raise ValidationError(
                "the engine's normalized validation evidence is not a valid "
                f"evidence document: {error.errors()[0]['msg']}",
                code="validation_evidence_invalid",
                details={"engine_digest": self._engine_digest},
            ) from error

    # -- reading -----------------------------------------------------------

    def parse_summary(self, output_dir: Path) -> UpstreamValidationSummary:
        """Project ``summary.json`` into the protocol's flat summary.

        Field by field, because every one of the five outcome counts sits at
        the wrong depth upstream and two of the document's keys have no
        protocol meaning at all (``docs/verifiers-pin.md``, finding C1).
        """
        document = self._summary_document(output_dir)
        outcomes = _require_object(document, "outcomes", output_dir)

        try:
            return UpstreamValidationSummary(
                mode=_require_str(document, "mode", output_dir),  # type: ignore[arg-type]
                total=_require_count(document, "total", output_dir),
                recorded=_require_count(document, "recorded", output_dir),
                valid=_require_count(outcomes, "valid", output_dir),
                invalid=_require_count(outcomes, "invalid", output_dir),
                error=_require_count(outcomes, "error", output_dir),
                timeout=_require_count(outcomes, "timeout", output_dir),
                missing=_require_count(outcomes, "missing", output_dir),
                valid_rate=_optional_rate(document, output_dir),
            )
        except PydanticValidationError as error:
            raise ValidationError(
                "the validator's summary does not describe a coherent run: "
                f"{error.errors()[0]['msg']}",
                code="validation_summary_invalid",
                details={"path": str(output_dir / _SUMMARY_FILE)},
            ) from error

    def parse_check_counts(self, output_dir: Path) -> dict[str, UpstreamCheckCounts]:
        """Return the per-check breakdown, empty when the validator reported none.

        Upstream writes ``checks`` only for a run in which both checks ran.
        Techtree always asks for both, so an empty result is something the
        caller reports as a failed check rather than something this hides.
        """
        document = self._summary_document(output_dir)
        checks = document.get("checks")
        if checks is None:
            return {}
        if not isinstance(checks, dict):
            raise ValidationError(
                "the validator's summary records a checks breakdown that is "
                "not an object",
                code="validation_summary_invalid",
                details={"path": str(output_dir / _SUMMARY_FILE)},
            )

        counts: dict[str, UpstreamCheckCounts] = {}
        for name, reported in checks.items():
            if not isinstance(reported, dict):
                raise ValidationError(
                    f"the validator's summary records the {name} check as "
                    "something other than a set of counts",
                    code="validation_summary_invalid",
                    details={"path": str(output_dir / _SUMMARY_FILE)},
                )
            counts[str(name)] = UpstreamCheckCounts(
                **{
                    key: _require_count(reported, key, output_dir)
                    for key in _OUTCOME_KEYS
                }
            )
        return counts

    def validation_artifacts(self, output_dir: Path) -> list[ArtifactRef]:
        """Digest the four files one validation run leaves behind.

        These are raw execution outputs, not evidence: ``results.jsonl`` is
        written in completion order and the log carries wall-clock times, so
        two identical runs digest differently by construction (finding C0).
        They belong to the local
        :class:`~techtree.models.validation.ValidationExecutionRecord` and are
        never referenced by a receipt or shipped in a catalog.
        """
        artifacts: list[ArtifactRef] = []
        for name in VALIDATION_FILENAMES:
            path = output_dir / name
            try:
                data = path.read_bytes()
            except OSError as error:
                raise ValidationError(
                    f"the validation run left no {name} behind",
                    code="validation_artifact_missing",
                    details={"path": str(path)},
                ) from error
            artifacts.append(
                ArtifactRef(
                    digest=sha256_digest_bytes(data),
                    media_type=_MEDIA_TYPES[name],
                    size=len(data),
                    relative_path=name,
                )
            )
        return artifacts

    # -- one read of one small file ----------------------------------------

    def _summary_document(self, output_dir: Path) -> dict[str, Any]:
        path = output_dir / _SUMMARY_FILE
        try:
            raw = path.read_bytes()
        except OSError as error:
            raise ValidationError(
                f"the validation run wrote no summary at {path}",
                code="validation_summary_missing",
                details={"path": str(path)},
            ) from error

        try:
            document = json.loads(raw)
        except ValueError as error:
            raise ValidationError(
                f"the validator's summary is not JSON: {path}",
                code="validation_summary_invalid",
                details={"path": str(path)},
            ) from error

        if not isinstance(document, dict):
            raise ValidationError(
                f"the validator's summary is not a JSON object: {path}",
                code="validation_summary_invalid",
                details={"path": str(path)},
            )
        if document.get("mode") != _BOTH_CHECKS:
            raise ValidationError(
                f"this validation ran in mode {document.get('mode')!r}; Techtree "
                f"pins mode {_BOTH_CHECKS!r}, which runs both checks",
                code="validation_summary_invalid",
                details={"path": str(path), "mode": str(document.get("mode"))},
            )
        return document


def _require_object(
    document: Mapping[str, Any], key: str, output_dir: Path
) -> dict[str, Any]:
    value = document.get(key)
    if not isinstance(value, dict):
        raise ValidationError(
            f"the validator's summary has no {key} object",
            code="validation_summary_invalid",
            details={"path": str(output_dir / _SUMMARY_FILE), "field": key},
        )
    return value


def _require_str(document: Mapping[str, Any], key: str, output_dir: Path) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise ValidationError(
            f"the validator's summary field {key} is not a name: {value!r}",
            code="validation_summary_invalid",
            details={"path": str(output_dir / _SUMMARY_FILE), "field": key},
        )
    return value


def _require_count(document: Mapping[str, Any], key: str, output_dir: Path) -> int:
    value = document.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(
            f"the validator's summary field {key} is not a count: {value!r}",
            code="validation_summary_invalid",
            details={"path": str(output_dir / _SUMMARY_FILE), "field": key},
        )
    return value


def _optional_rate(document: Mapping[str, Any], output_dir: Path) -> float | None:
    value = document.get("valid_rate")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValidationError(
            f"the validator's summary field valid_rate is not a rate: {value!r}",
            code="validation_summary_invalid",
            details={"path": str(output_dir / _SUMMARY_FILE), "field": "valid_rate"},
        )
    return float(value)


def _last_line(text: str) -> str:
    """Return the last meaningful line of a child process's diagnostics."""
    lines: Sequence[str] = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else "the engine reported no diagnostics"
