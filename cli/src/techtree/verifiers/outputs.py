"""The files one variant's evaluation must have left behind. Spec section 6.13.

A real ``eval`` run writes exactly three files, and Techtree keeps all three:
the resolved configuration, the raw upstream episodes, and the upstream log.
The normalizer that the engine runs over them does not replace any of them
(spec section 6.12) — Techtree retains raw upstream evidence *and* its
normalized projection, because a projection nobody can check against its source
is a claim rather than evidence.

A dry-run directory is deliberately not accepted here. Dry run writes only
``config.toml`` (``docs/verifiers-eval.md``, finding E2), so applying the run's
requirements to it would report a truncated run where there was never a run at
all.

``build_variant_result`` is absent. Spec section 6.13 builds it by running the
engine tool ``normalize_eval_output.py``, and that tool lives inside the
digested engine bundle, which this ticket is not permitted to change. Writing
the function now would mean writing a function whose only reachable behaviour
is to raise ``engine_tool_unknown``. The STOP-AND-NOTE on the ticket carries
the details.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import sha256_digest_bytes
from techtree.errors import ValidationError
from techtree.models.base import ArtifactRef
from techtree.verifiers.models import NormalizedEpisode

__all__ = [
    "CONFIG_FILENAME",
    "EVAL_LOG_FILENAME",
    "NORMALIZED_EPISODES_MEDIA_TYPE",
    "TRACES_FILENAME",
    "VARIANT_OUTPUT_INCOMPLETE",
    "artifact_for",
    "read_normalized_episodes",
    "require_output_files",
    "required_output_paths",
]

#: Stable error code. Spec section 6.13.
VARIANT_OUTPUT_INCOMPLETE: Final = "variant_output_incomplete"

CONFIG_FILENAME: Final = "config.toml"
TRACES_FILENAME: Final = "traces.jsonl"
EVAL_LOG_FILENAME: Final = "eval.log"

NORMALIZED_EPISODES_MEDIA_TYPE: Final = "application/x-ndjson"


def required_output_paths(output_dir: Path) -> dict[str, Path]:
    """Return the three files a completed evaluation writes."""
    return {
        "config": output_dir / CONFIG_FILENAME,
        "traces": output_dir / TRACES_FILENAME,
        "eval_log": output_dir / EVAL_LOG_FILENAME,
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
