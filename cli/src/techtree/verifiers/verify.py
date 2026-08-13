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

Section 6.14's post-execution checks are not here. They read normalized
episodes, which the engine tool ``normalize_eval_output.py`` produces, and that
tool lives inside the digested engine bundle this ticket may not change. The
STOP-AND-NOTE on the ticket carries the details.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from techtree.engines.runner import EngineProcessResult, EngineRunner
from techtree.errors import ValidationError
from techtree.fs import ensure_private_directory
from techtree.models.campaign import ModelSpec
from techtree.verifiers.config import EvalToml
from techtree.verifiers.credentials import credential_status
from techtree.verifiers.models import (
    VERIFIERS_DIRECTORY,
    ExecutionCheck,
    VariantName,
)
from techtree.verifiers.outputs import CONFIG_FILENAME

__all__ = [
    "CONFIG_ARGUMENT_MARKER",
    "DEFAULT_DRY_RUN_TIMEOUT_SECONDS",
    "DRY_RUN_FLAG",
    "EVAL_EXECUTABLE",
    "OUTPUT_DIR_FLAG",
    "PUSH_DISABLED_FLAG",
    "VARIANT_DRY_RUN_FAILED",
    "DryRunOutcome",
    "dry_run_argv",
    "dry_run_variant_config",
    "verify_compiled_config",
]

#: Stable error code. Spec section 6.14.
VARIANT_DRY_RUN_FAILED: Final = "variant_dry_run_failed"

#: The pinned engine's evaluation console script. A bare, generic name
#: (``docs/verifiers-pin.md``, finding C3), so it is always addressed through
#: :class:`~techtree.engines.runner.EngineRunner`, which resolves it to an
#: absolute path inside the engine's own virtual environment.
EVAL_EXECUTABLE: Final = "eval"

#: ``eval`` takes a configuration file as ``@`` followed by the path, as two
#: separate argv entries.
CONFIG_ARGUMENT_MARKER: Final = "@"
DRY_RUN_FLAG: Final = "--dry-run"
OUTPUT_DIR_FLAG: Final = "--output-dir"
#: Belt and braces alongside ``push = false`` in the compiled document. The
#: upstream default is to upload (``docs/verifiers-eval.md``, finding E1), and
#: a flag on the command line overrides whatever the file says.
PUSH_DISABLED_FLAG: Final = "--no-push"

DEFAULT_DRY_RUN_TIMEOUT_SECONDS: Final = 300.0

#: The one key the engine fills in that Techtree deliberately left out, so a
#: difference there is not a disagreement. The routing header the engine may
#: also add needs no entry: Techtree declares no headers at all, so an added
#: one has nothing on the declared side to disagree with.
_ENGINE_RESOLVED_KEYS: Final[frozenset[str]] = frozenset({"client.base_url"})


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


def dry_run_argv(*, input_config_path: Path, dry_run_dir: Path) -> list[str]:
    """Return the arguments the engine's ``eval`` script is given.

    No credential appears here, and none can: the configuration names an
    environment variable and the engine reads it from the child's environment.
    """
    return [
        CONFIG_ARGUMENT_MARKER,
        str(input_config_path),
        DRY_RUN_FLAG,
        PUSH_DISABLED_FLAG,
        OUTPUT_DIR_FLAG,
        str(dry_run_dir),
    ]


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

    process = engine_runner.run(
        EVAL_EXECUTABLE,
        dry_run_argv(input_config_path=input_config_path, dry_run_dir=dry_run_dir),
        timeout=timeout,
    )

    checks: list[ExecutionCheck] = [_invocation_check(process)]
    resolved_path = dry_run_dir / CONFIG_FILENAME
    resolved: dict[str, Any] | None = None

    if process.exit_code == 0 and resolved_path.is_file():
        resolved = _read_resolved_config(resolved_path)
        checks.append(
            ExecutionCheck(
                id="resolved_config_written",
                status="passed",
                detail=f"the engine wrote {CONFIG_FILENAME} to the dry-run directory.",
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
    """Compare what the engine resolved against what Techtree declared."""
    declared = _flatten(compiled.model_dump(mode="json", exclude_none=True))
    observed = _flatten(resolved)

    differences = sorted(
        key
        for key, value in declared.items()
        if key not in _ENGINE_RESOLVED_KEYS and observed.get(key) != value
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
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
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
