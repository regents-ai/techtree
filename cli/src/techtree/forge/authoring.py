"""What planning and construction share: the Skill as sent, and one Hermes call.

``docs/plan/v0.3.0-skill-environments.md`` (U3, KTD4). Both authoring phases
send the same thing, the Source Skill's admitted files read back from
Techtree's kept copy and checked against their record, and make their calls
the same way: Hermes one-shot in the person's ``techtree`` profile, held and
emptied of all but the sign-in exactly as an experiment does it
(:mod:`techtree.forge.profile`), in an empty workspace, with its text-only
toolset, memory off, and its rules, memory and Skills not injected. The
answer is what Hermes prints; everything else it writes goes to a log.
Techtree copies no credential and reads none.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Final, Literal

from techtree.canonical import canonical_json_bytes, sha256_digest_bytes
from techtree.errors import PrerequisiteError, ValidationError
from techtree.forge.experiment import hermes_version
from techtree.forge.models import (
    ForgeAgentSpec,
    ForgeBuildFailure,
    ForgeModelSpec,
    ForgeSourceStatus,
    ForgeUsage,
)
from techtree.forge.profile import reset_profile
from techtree.forge.run import AgentOutcome, read_usage, supervise_hermes
from techtree.fs import atomic_write_bytes
from techtree.models.skill import SkillFile

__all__ = [
    "PROMPT_LIMIT",
    "TEXT_ONLY_TOOLSET",
    "AnsweredWith",
    "Launcher",
    "ReviewedOn",
    "agent_spec",
    "alive",
    "call_failure",
    "hermes_config",
    "hermes_executable",
    "kept_files",
    "launch_one_shot",
    "model_spec",
    "one_shot_argv",
    "run_one_shot",
    "skill_text",
]

#: The largest prompt handed to Hermes. It takes the prompt as one
#: command-line argument, and Linux caps one argument at 128 KiB.
PROMPT_LIMIT: Final = 120 * 1024
#: Hermes' toolset with no tool in it.
TEXT_ONLY_TOOLSET: Final = "bot_room"
_STATE_DB: Final = "state.db"

type ReviewedOn = Literal["cli", "host-agent"]
type AnsweredWith = Literal["prompt", "yes-flag"]
type Launcher = Callable[
    [list[str], dict[str, str], Path, Path, Path, float], AgentOutcome
]


def launch_one_shot(
    argv: list[str],
    env: dict[str, str],
    cwd: Path,
    answer: Path,
    log: Path,
    timeout: float,
) -> AgentOutcome:
    """Run Hermes once: its answer to ``answer``, everything else to ``log``."""
    with answer.open("wb") as stdout, log.open("wb") as stderr:
        return supervise_hermes(
            argv, env, cwd, stdout=stdout, stderr=stderr, timeout=timeout
        )


def hermes_executable() -> Path:
    found = shutil.which("hermes")
    if found is None:
        raise PrerequisiteError(
            "no hermes on the path; install Hermes Agent and sign in to a "
            "provider before planning or building tasks",
            code="hermes_not_found",
        )
    return Path(found)


def agent_spec(executable: Path) -> ForgeAgentSpec:
    return ForgeAgentSpec(
        harness="hermes", executable=str(executable), version=hermes_version(executable)
    )


def model_spec(provider: str, model_id: str, reasoning: str | None) -> ForgeModelSpec:
    return ForgeModelSpec(
        provider=provider,
        model_id=model_id,
        reasoning=reasoning,
        credential_source="hermes-auth-store",
    )


def kept_files(
    source: ForgeSourceStatus, *, called: str
) -> list[tuple[SkillFile, bytes]]:
    """Read the admitted files back from the kept copy, as recorded.

    ``called`` names who would have been sent them, for the refusal.
    """
    record = source.record
    if source.snapshot_path is None:
        raise ValidationError(
            f"Techtree cannot use Source Skill {source.source_id} as it is: "
            + "; ".join(refusal.message for refusal in record.refusals)
            + f". {called} was not called. A copy without these is a "
            "different Skill; look at that copy with forge inspect-skill "
            f"--derived-from {source.source_id}",
            code="forge_skill_unsupported",
            details={
                "source_id": source.source_id,
                "refusals": [
                    refusal.model_dump(mode="json") for refusal in record.refusals
                ],
            },
        )
    snapshot = Path(source.snapshot_path)
    kept: list[tuple[SkillFile, bytes]] = []
    for file in record.admitted_files:
        try:
            data = (snapshot / file.path).read_bytes()
        except OSError:
            data = b""
        if len(data) != file.size or sha256_digest_bytes(data) != file.digest:
            raise ValidationError(
                f"Techtree's kept copy of {file.path} no longer matches what "
                f"Source Skill {source.source_id} recorded, so it cannot be "
                f"sent as that Skill. {called} was not called; look at the "
                "Skill again with forge inspect-skill",
                code="forge_source_changed",
                details={"source_id": source.source_id, "path": file.path},
            )
        kept.append((file, data))
    return kept


def skill_text(kept: list[tuple[SkillFile, bytes]]) -> bytes:
    """Return every kept file, word for word, each between two marker lines."""
    parts: list[bytes] = []
    for file, data in kept:
        parts.append(f"\n===== {file.path} ({file.size} bytes) =====\n".encode())
        parts.append(data if data.endswith(b"\n") else data + b"\n")
        parts.append(f"===== end of {file.path} =====\n".encode())
    return b"".join(parts)


def hermes_config(wall_seconds: int) -> bytes:
    """Return the ``config.yaml`` Techtree writes for one call, as bytes."""
    return canonical_json_bytes(
        {
            "memory": {"memory_enabled": False, "user_profile_enabled": False},
            "agent": {"run_budget_seconds": wall_seconds},
            "auxiliary": {"title_generation": {"enabled": False}},
            "skills": {"external_dirs": []},
        }
    )


def one_shot_argv(
    agent: ForgeAgentSpec,
    model: ForgeModelSpec,
    *,
    toolset: str,
    workspace: Path,
    usage_file: Path,
    prompt: bytes,
) -> list[str]:
    """Return the command line of one call; the prompt is its last argument."""
    return [
        agent.executable,
        "--ignore-rules",
        "--in",
        str(workspace),
        "-m",
        model.model_id,
        "--provider",
        model.provider,
        *(("--reasoning", model.reasoning) if model.reasoning else ()),
        "-t",
        toolset,
        "--usage-file",
        str(usage_file),
        "-z",
        prompt.decode("utf-8"),
    ]


def run_one_shot(
    launch: Launcher,
    argv: list[str],
    *,
    profile: Path,
    config: bytes,
    workspace: Path,
    answer: Path,
    log: Path,
    wall_seconds: int,
    keep_in: Path,
) -> AgentOutcome:
    """Launch one call in the emptied profile and keep its transcript.

    The profile is emptied to its sign-in before and after, whatever happens
    in between; a Ctrl-C is raised again once that is done.
    """
    reset_profile(profile)
    atomic_write_bytes(profile / "config.yaml", config)
    try:
        return launch(
            argv,
            {**os.environ, "HERMES_HOME": str(profile)},
            workspace,
            answer,
            log,
            float(wall_seconds),
        )
    finally:
        transcript = profile / _STATE_DB
        if transcript.is_file() and not transcript.is_symlink():
            shutil.copyfile(transcript, keep_in / _STATE_DB)
        reset_profile(profile)


def call_failure(
    outcome: AgentOutcome, usage_file: Path, *, code: str, error_type: str
) -> ForgeBuildFailure | None:
    """Return why a finished call left no answer, or None when it answered."""
    usage: ForgeUsage | None = read_usage(usage_file)
    if (
        outcome.exit_code == 0
        and usage is not None
        and not usage.failed
        and usage.completed
    ):
        return None
    reason = usage.failure if usage is not None and usage.failure else None
    return ForgeBuildFailure(
        code=code,
        message=(
            f"Hermes ended without an answer (exit {outcome.exit_code}"
            + (f": {reason}" if reason else "")
            + ")"
        )[:512],
        error_type=error_type,
    )


def alive(process_id: int) -> bool:
    """Whether a process with this id is running; a reused id reads as alive."""
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
