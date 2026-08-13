"""``techtree run status``, ``logs``, ``cancel``, and ``result``.
Spec §12.6 and PR8 §8.12-§8.15.

These four commands are the whole of what a caller can do with a run it has
already started, and they are written for a caller that may be a program.

*Status never lies about liveness.* It reports the projected phase, whether
the worker process still exists, and how old the heartbeat is, and it changes
nothing. A dead worker on a nonterminal run shows up as exactly that — not as
a failure the CLI invented on the reader's behalf.

*Logs are untrusted output.* A worker writes whatever it writes, including
whatever a library it called wrote. Every line is passed through the secret
scrubber before it is shown, in bounded and followed reading alike, and the
response never contains the log's path: handing an agent a filename is handing
it an invitation to read something else.

*Cancelling is a mutation and is treated as one.* A person is asked; a program
must pass ``--confirm``. Possession of a run identifier is not intent to stop
the run.

*A fake result announces itself first.* Human output for ``result`` leads with
the development-only banner before a single number appears, and the machine
envelope carries the same caveat as a warning, because the caller most likely
to mistake an invented number for a measurement is the one reading JSON.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Iterator
from enum import StrEnum
from typing import Annotated, Final, Literal

import typer
from rich.console import Console
from rich.table import Table

from techtree.cli.context import CliContext, cli_context
from techtree.cli.invoke import CommandResult, invoke_command
from techtree.cli.output import human_console
from techtree.drafts.confirmation import ConfirmationService
from techtree.drafts.store import DraftStore
from techtree.errors import TechtreeError, UsageError, VerificationError
from techtree.identity.models import VerificationResult
from techtree.models.base import Digest, NonEmptyString, ProtocolModel, UtcDateTime
from techtree.models.cli import CliError, CliMessage, MessageLevel, NextAction
from techtree.models.experiment import ExperimentVariant
from techtree.models.run import RunPhase, RunProgress, VariantProgress
from techtree.models.uplift_report import UpliftReport
from techtree.presentation.build import build_uplift_presentation
from techtree.presentation.compact import render_uplift_markdown
from techtree.presentation.models import UpliftPresentationPayload
from techtree.presentation.rich import TaskDisplay, render_uplift_console
from techtree.receipts.bundle import (
    BUNDLE_DIRECTORY,
    PROOF_BUNDLE_INVALID,
    REPORT_FILENAME,
    proof_bundle_dir,
)
from techtree.receipts.verify import LocalProofVerifier
from techtree.runs.artifacts import RunArtifactStore
from techtree.runs.launcher import (
    WorkerLauncher,
    default_worker_executable,
    scrubbed_worker_environment,
)
from techtree.runs.machine import is_terminal
from techtree.runs.service import (
    DEFAULT_LOG_TAIL,
    MAXIMUM_LOG_TAIL,
    MINIMUM_LOG_TAIL,
    RunService,
)
from techtree.runs.store import RunStore
from techtree.verifiers.models import VariantName

__all__ = [
    "CANCEL_COMMAND",
    "CANCEL_CONFIRMATION_REQUIRED",
    "DEVELOPMENT_ONLY_BANNER",
    "DEVELOPMENT_ONLY_RESULT_NOTICE",
    "LOGS_COMMAND",
    "PROVISIONAL_SCORE",
    "RESULT_COMMAND",
    "RUN_FOLLOW_NOT_SUPPORTED_FOR_VARIANT",
    "RUN_FOLLOW_NOT_SUPPORTED_IN_JSON",
    "RUN_WATCH_NOT_SUPPORTED_IN_JSON",
    "SCORE_PROVISIONAL_NOTICE",
    "STATUS_COMMAND",
    "ResultFormat",
    "RunCancelPayload",
    "RunLogsPayload",
    "RunResultPayload",
    "RunStatusPayload",
    "build_run_service",
    "cancel_run_command",
    "development_only_result_notice",
    "logs_run_command",
    "result_run_command",
    "status_run_command",
    "watch_line",
]

STATUS_COMMAND: Final = "run status"
LOGS_COMMAND: Final = "run logs"
CANCEL_COMMAND: Final = "run cancel"
RESULT_COMMAND: Final = "run result"

#: Stable error codes this module reports. Spec PR8 §8.16 names the first;
#: the other two are the machine-mode rules the same section asks for.
RUN_FOLLOW_NOT_SUPPORTED_IN_JSON: Final = "run_follow_not_supported_in_json"
RUN_FOLLOW_NOT_SUPPORTED_FOR_VARIANT: Final = "run_follow_not_supported_for_variant"
RUN_WATCH_NOT_SUPPORTED_IN_JSON: Final = "run_watch_not_supported_in_json"
CANCEL_CONFIRMATION_REQUIRED: Final = "run_cancel_confirmation_required"

#: What every reader of a fake result is told before they read anything else.
DEVELOPMENT_ONLY_BANNER: Final = (
    "DEVELOPMENT-ONLY FAKE RESULT\n"
    "\n"
    "No agent was evaluated.\n"
    "No model was called.\n"
    "This report is not publication eligible."
)

_DEVELOPMENT_ONLY_WARNING: Final = (
    "This run was executed by the development fake executor. No agent was "
    "evaluated, no model was called, and the numbers below are invented. The "
    "report is not publication eligible."
)

#: Spec section 29, verbatim. A finished report is the one place a reader
#: decides what they may do with what they are holding, so it says both halves
#: at once: which part of the run was real, and whose rights still govern the
#: artifacts it produced. The DataPolicy digest is named rather than described,
#: because a digest is the only unambiguous way to point at one.
DEVELOPMENT_ONLY_RESULT_NOTICE: Final = (
    "This is a development-only report.\n"
    "\n"
    "The taskset was validated through Prime Intellect Verifiers.\n"
    "The baseline and candidate results were generated by the fake executor.\n"
    "No agent was evaluated. The report is not publication eligible.\n"
    "\n"
    "The candidate and generated artifacts remain governed by DataPolicy:\n"
    "{data_policy_digest}"
)


def development_only_result_notice(data_policy_digest: str) -> str:
    """Return the spec section 29 warning a development result must carry."""
    return DEVELOPMENT_ONLY_RESULT_NOTICE.format(data_policy_digest=data_policy_digest)


#: What a variant's score column says while the comparison is still running.
#: Spec section 6.20 forbids showing a delta before both sides have finished
#: every task, and a blank cell would read as "nothing scored" rather than
#: "not yet answerable".
PROVISIONAL_SCORE: Final = "provisional only"

#: Spec section 6.20, the sentence under a progress table.
SCORE_PROVISIONAL_NOTICE: Final = (
    "The score remains provisional until every task completes and Techtree "
    "verifies that the observed configurations match."
)

#: How often human watch mode looks again.
_WATCH_INTERVAL_SECONDS: Final = 1.0

#: How long a follower waits before checking a quiet log again.
_FOLLOW_INTERVAL_SECONDS: Final = 0.25


class RunStatusPayload(ProtocolModel):
    """Everything a caller needs to decide what to do about a run next."""

    run_id: NonEmptyString
    phase: RunPhase
    sequence: int
    updated_at: UtcDateTime
    progress: RunProgress | None
    #: One entry per variant once a concurrent comparison is under way, keyed by
    #: variant name. Spec section 6.20 exposes it here so a machine caller reads
    #: both sides' episode counts without parsing anything meant for a person.
    variant_progress: dict[str, VariantProgress]
    worker_pid: int | None
    worker_alive: bool
    heartbeat_at: UtcDateTime | None
    heartbeat_age_seconds: float | None
    heartbeat_stale: bool
    cancel_requested_at: UtcDateTime | None
    terminal: bool
    result_available: bool
    result_digest: Digest | None
    error: CliError | None
    development_only: bool


class RunLogsPayload(ProtocolModel):
    """A bounded, scrubbed window onto one run's worker log."""

    run_id: NonEmptyString
    lines: list[str]
    truncated: bool


class RunCancelPayload(ProtocolModel):
    """What asking a run to stop achieved."""

    run_id: NonEmptyString
    outcome: Literal["requested", "already_requested", "already_terminal"]
    phase: RunPhase
    cancel_requested_at: UtcDateTime | None
    worker_alive: bool


class ResultFormat(StrEnum):
    """How a person asked for a finished result to be drawn."""

    RICH = "rich"
    COMPACT = "compact"
    PATH = "path"


class RunResultPayload(ProtocolModel):
    """A finished run's report, and the neutral payload every channel draws.

    Both, always. The report is the evidence and the presentation is the view;
    a machine caller that received only one of them would either have to render
    the evidence itself — inventing the wording this product is careful about —
    or trust a view it cannot check against anything.
    """

    report: UpliftReport
    presentation: UpliftPresentationPayload
    format: ResultFormat
    show_tasks: TaskDisplay


def build_run_service(context: CliContext) -> RunService:
    """Construct the service every run command acts through."""
    run_store = RunStore(context.paths)
    return RunService(
        paths=context.paths,
        draft_store=DraftStore(context.paths, ConfirmationService()),
        run_store=run_store,
        artifact_store=RunArtifactStore(context.paths),
        launcher=WorkerLauncher(
            worker_executable=default_worker_executable(),
            run_store=run_store,
            environment_builder=scrubbed_worker_environment(context.paths),
        ),
    )


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def status_run_command(
    ctx: typer.Context,
    run_id: Annotated[
        str,
        typer.Argument(metavar="RUN_ID", help="The run to report on."),
    ],
    watch: Annotated[
        bool,
        typer.Option(
            "--watch",
            help="Keep reporting until the run ends. Human output only.",
        ),
    ] = False,
) -> None:
    """Show how a run is progressing."""
    context = cli_context(ctx)

    def action() -> CommandResult[RunStatusPayload]:
        if watch and context.json_output:
            raise UsageError(
                "--watch prints repeatedly and machine mode returns one "
                "envelope; poll `techtree run status --json` instead",
                code=RUN_WATCH_NOT_SUPPORTED_IN_JSON,
                details={"run_id": run_id},
            )

        service = build_run_service(context)
        payload = (
            _watch_until_terminal(service, run_id, context)
            if watch
            else _status_payload(service, run_id)
        )
        return CommandResult(
            data=payload,
            warnings=_development_warnings(payload.development_only),
            next_actions=_status_next_actions(payload),
        )

    invoke_command(context, STATUS_COMMAND, action, render_data=_render_status)


def _status_payload(service: RunService, run_id: str) -> RunStatusPayload:
    status = service.status(run_id)
    health = service.process_health(run_id)
    state = status.state
    return RunStatusPayload(
        run_id=state.run_id,
        phase=state.phase,
        sequence=state.sequence,
        updated_at=state.updated_at,
        progress=state.progress,
        variant_progress=dict(state.variant_progress),
        worker_pid=state.worker_pid,
        worker_alive=status.worker_alive,
        heartbeat_at=state.heartbeat_at,
        heartbeat_age_seconds=health.heartbeat_age_seconds,
        heartbeat_stale=status.heartbeat_stale,
        cancel_requested_at=state.cancel_requested_at,
        terminal=is_terminal(state.phase),
        result_available=status.result_available,
        result_digest=state.result_digest,
        error=state.error,
        development_only=service.request(run_id).executor_kind == "fake",
    )


def _watch_until_terminal(
    service: RunService, run_id: str, context: CliContext
) -> RunStatusPayload:
    """Report every second until the run ends or the reader stops watching.

    A ``Ctrl-C`` here stops the watching, never the run. Anything else would
    make looking at a run a way to lose one.
    """
    console = human_console(no_color=context.no_color)
    payload = _status_payload(service, run_id)
    try:
        while not payload.terminal:
            console.print(watch_line(payload))
            time.sleep(_WATCH_INTERVAL_SECONDS)
            payload = _status_payload(service, run_id)
    except KeyboardInterrupt:
        console.print("Stopped watching. The run is still going.")
    return payload


def watch_line(payload: RunStatusPayload) -> str:
    """Return one line describing where the run is right now.

    While both variants are in flight the line carries both, because a single
    number would have to be either one side's or a sum, and a watcher reading
    "18/72" cannot tell a comparison that is running evenly from one whose
    candidate has not started. No score appears: spec section 6.20 forbids a
    delta before both sides have finished, and a watch line is the easiest
    place for a partial one to be mistaken for the answer.
    """
    if payload.variant_progress:
        return "  ".join(
            [payload.phase.value, *_variant_watch_cells(payload.variant_progress)]
        )
    progress = payload.progress
    if progress is None:
        return payload.phase.value
    return f"{payload.phase.value}  {progress.current}/{progress.total}"


def _variant_watch_cells(progress: dict[str, VariantProgress]) -> list[str]:
    """Return one cell per side of the comparison, in comparison order."""
    cells: list[str] = []
    for variant in (VariantName.BASELINE, VariantName.CANDIDATE):
        side = progress.get(variant.value)
        counts = "not started" if side is None else f"{side.completed}/{side.total}"
        cells.append(f"{variant.value} {counts}")
    return cells


def _status_next_actions(payload: RunStatusPayload) -> list[NextAction]:
    if payload.result_available:
        return [_read_result(payload.run_id)]
    if payload.terminal:
        return [_read_logs(payload.run_id)]
    return [_check_status(payload.run_id), _read_logs(payload.run_id)]


# ---------------------------------------------------------------------------
# logs
# ---------------------------------------------------------------------------


def logs_run_command(
    ctx: typer.Context,
    run_id: Annotated[
        str,
        typer.Argument(metavar="RUN_ID", help="The run to read the log of."),
    ],
    tail: Annotated[
        int,
        typer.Option(
            "--tail",
            metavar="LINES",
            help=(
                f"How many trailing lines to show, from {MINIMUM_LOG_TAIL} to "
                f"{MAXIMUM_LOG_TAIL}."
            ),
        ),
    ] = DEFAULT_LOG_TAIL,
    follow: Annotated[
        bool,
        typer.Option(
            "--follow",
            help="Keep printing new lines as they arrive. Human output only.",
        ),
    ] = False,
    variant: Annotated[
        VariantName | None,
        typer.Option(
            "--variant",
            help="Read one side of the comparison's evaluation log.",
        ),
    ] = None,
) -> None:
    """Show the log output of a run."""
    context = cli_context(ctx)

    def action() -> CommandResult[RunLogsPayload]:
        # The narrower incompatibility is reported first. Following one side of
        # a comparison is not supported in any output mode, so saying "not in
        # machine mode" would send a caller off to try it in human mode.
        if follow and variant is not None:
            raise UsageError(
                "--follow reads the worker's own log; a variant's evaluation "
                "log is read a window at a time with --tail",
                code=RUN_FOLLOW_NOT_SUPPORTED_FOR_VARIANT,
                details={"run_id": run_id, "variant": variant.value},
            )
        if follow and context.json_output:
            raise UsageError(
                "--follow never ends and machine mode returns one envelope; "
                "poll `techtree run logs --json` instead",
                code=RUN_FOLLOW_NOT_SUPPORTED_IN_JSON,
                details={"run_id": run_id},
            )

        service = build_run_service(context)
        if variant is not None:
            logs = service.variant_logs(run_id, variant, tail=tail)
            return CommandResult(
                data=RunLogsPayload(
                    run_id=logs.run_id,
                    lines=list(logs.lines),
                    truncated=logs.truncated,
                ),
                next_actions=[_check_status(run_id)],
            )

        logs = service.logs(run_id, tail=tail)
        if follow:
            _follow_log(service, run_id, context, shown=logs.lines)
            logs = service.logs(run_id, tail=tail)

        return CommandResult(
            data=RunLogsPayload(
                run_id=logs.run_id,
                lines=list(logs.lines),
                truncated=logs.truncated,
            ),
            next_actions=[_check_status(run_id)],
        )

    invoke_command(context, LOGS_COMMAND, action, render_data=_render_logs)


def _follow_log(
    service: RunService,
    run_id: str,
    context: CliContext,
    *,
    shown: list[str],
) -> None:
    """Print new lines as they arrive, scrubbing each one.

    ``Ctrl-C`` leaves the run alone: following a log is reading, and reading
    has never been a way to cancel anything.
    """
    console = human_console(no_color=context.no_color)
    for line in shown:
        console.print(line)

    try:
        for line in _new_log_lines(service, run_id):
            console.print(line)
    except KeyboardInterrupt:
        console.print("Stopped following. The run is unaffected.")


def _new_log_lines(service: RunService, run_id: str) -> Iterator[str]:
    """Yield each new log line, scrubbed, until the run ends."""
    path = service.worker_log_path(run_id)
    position = path.stat().st_size if path.exists() else 0

    while True:
        if path.exists():
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(position)
                fresh = handle.read()
                position = handle.tell()
            for line in fresh.splitlines():
                yield service.scrub(line)
        if is_terminal(service.status(run_id).state.phase):
            return
        time.sleep(_FOLLOW_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------


def cancel_run_command(
    ctx: typer.Context,
    run_id: Annotated[
        str,
        typer.Argument(metavar="RUN_ID", help="The run to stop."),
    ],
    confirm: Annotated[
        bool,
        typer.Option(
            "--confirm",
            help="Confirm the cancellation without being asked.",
        ),
    ] = False,
) -> None:
    """Stop a run that is still in progress."""
    context = cli_context(ctx)

    def action() -> CommandResult[RunCancelPayload]:
        service = build_run_service(context)
        _require_cancel_confirmation(context, run_id, confirm=confirm)

        cancellation = service.cancel(run_id)
        state = cancellation.status.state
        payload = RunCancelPayload(
            run_id=state.run_id,
            outcome=cancellation.outcome,
            phase=state.phase,
            cancel_requested_at=state.cancel_requested_at,
            worker_alive=cancellation.status.worker_alive,
        )
        return CommandResult(
            data=payload,
            messages=[
                CliMessage(
                    level=MessageLevel.INFO,
                    code=f"run_cancel_{cancellation.outcome}",
                    text=_cancel_message(payload),
                )
            ],
            warnings=_cancel_warnings(payload),
            next_actions=[_check_status(run_id)],
        )

    invoke_command(context, CANCEL_COMMAND, action, render_data=_render_cancel)


def _require_cancel_confirmation(
    context: CliContext, run_id: str, *, confirm: bool
) -> None:
    """Require an explicit yes, from a person or from an option."""
    if confirm:
        return
    if context.no_input:
        raise UsageError(
            "cancelling a run stops work that cannot be resumed, so it needs "
            "--confirm when nothing can be asked",
            code=CANCEL_CONFIRMATION_REQUIRED,
            details={"run_id": run_id},
        )
    if not typer.confirm(f"Stop run {run_id}?", default=False):
        raise UsageError(
            f"run {run_id} was left running",
            code=CANCEL_CONFIRMATION_REQUIRED,
            details={"run_id": run_id},
        )


def _cancel_message(payload: RunCancelPayload) -> str:
    if payload.outcome == "already_terminal":
        return (
            f"Run {payload.run_id} had already ended in {payload.phase.value}; "
            "nothing was changed."
        )
    if payload.outcome == "already_requested":
        return f"Run {payload.run_id} had already been asked to stop."
    return f"Run {payload.run_id} has been asked to stop."


def _cancel_warnings(payload: RunCancelPayload) -> list[CliMessage]:
    if payload.outcome == "already_terminal":
        return [
            CliMessage(
                level=MessageLevel.WARNING,
                code="run_already_terminal",
                text=(
                    "A run that has ended cannot be cancelled, and its result "
                    "was left exactly as it was."
                ),
            )
        ]
    if payload.worker_alive:
        return [
            CliMessage(
                level=MessageLevel.WARNING,
                code="run_stopping",
                text=(
                    "The worker was signalled and stops at its next safe point, "
                    "so the run may take a moment to report as cancelled."
                ),
            )
        ]
    return []


# ---------------------------------------------------------------------------
# result
# ---------------------------------------------------------------------------


def result_run_command(
    ctx: typer.Context,
    run_id: Annotated[
        str,
        typer.Argument(metavar="RUN_ID", help="The finished run to report on."),
    ],
    result_format: Annotated[
        ResultFormat | None,
        typer.Option(
            "--format",
            help=(
                "How to show the result. Defaults to rich in a terminal and "
                "compact when the output is piped."
            ),
        ),
    ] = None,
    show_tasks: Annotated[
        TaskDisplay,
        typer.Option("--show-tasks", help="Which per-task rows to print."),
    ] = TaskDisplay.CHANGED,
    verify: Annotated[
        bool,
        typer.Option(
            "--verify/--no-verify",
            help="Check the run's local proof before showing the result.",
        ),
    ] = True,
) -> None:
    """Show the finished report for a run."""
    context = cli_context(ctx)

    def action() -> CommandResult[RunResultPayload]:
        service = build_run_service(context)
        try:
            report = service.result(run_id)
        except TechtreeError as error:
            # "Not finished yet" is the ordinary answer here, and the caller
            # should be told where to look rather than told to guess.
            if not error.next_actions:
                error.next_actions = [_check_status(run_id)]
            raise

        verification = _verify_proof(context, run_id, report) if verify else None
        payload = RunResultPayload(
            report=report,
            presentation=_presentation(context, run_id, report, verification),
            format=result_format or _default_format(context),
            show_tasks=show_tasks,
        )
        return CommandResult(
            data=payload,
            warnings=_result_warnings(report),
            next_actions=[*payload.presentation.next_actions, _read_logs(run_id)],
            # A result whose own proof does not check out is shown and
            # reported as a failure: the caller still gets the report, and
            # the exit code says not to believe it.
            error=_unverified_error(run_id, verification),
        )

    invoke_command(context, RESULT_COMMAND, action, render_data=_render_result)


def _presentation(
    context: CliContext,
    run_id: str,
    report: UpliftReport,
    verification: VerificationResult | None,
) -> UpliftPresentationPayload:
    """Build the channel-neutral payload every rendering of this result uses.

    The Skills and the comparison's title come from the run's own staged
    inputs, which the artifact store verifies against the run's immutable
    request, so what is shown is what was executed rather than whatever a
    draft or a catalog holds now.

    ``baseline_skill`` is the Skill the baseline variant carried, which is
    ``None`` for a Skill insertion and the Skill being revised for a Skill
    replacement. It is read off the run rather than assumed, so the two
    comparisons cannot be labelled as each other.
    """
    artifacts = RunArtifactStore(context.paths)
    inputs = artifacts.load_inputs(run_id, RunStore(context.paths).get_request(run_id))
    baseline_skill = inputs.baseline_skill
    return build_uplift_presentation(
        report=report,
        baseline_receipts=artifacts.episode_receipts(
            run_id, ExperimentVariant.BASELINE
        ),
        candidate_receipts=artifacts.episode_receipts(
            run_id, ExperimentVariant.CANDIDATE
        ),
        campaign_title=inputs.source.title,
        baseline_skill=None if baseline_skill is None else baseline_skill.artifact,
        candidate_skill=inputs.candidate_skill.artifact,
        verification=verification,
    )


def _verify_proof(
    context: CliContext, run_id: str, report: UpliftReport
) -> VerificationResult | None:
    """Check the run's local proof, when it has one to check.

    A development-only report has no proof bundle and never claimed one, so
    there is nothing to verify and nothing is claimed about it. A graded report
    always has one, and a missing bundle for a graded report is a failed
    verification rather than a silent "not checked".
    """
    if report.proof_grade == "development_only":
        return None
    return LocalProofVerifier().verify_bundle(
        proof_bundle_dir(context.paths.run_dir(run_id))
    )


def _unverified_error(
    run_id: str, verification: VerificationResult | None
) -> VerificationError | None:
    """Return the failure a result carries when its proof did not verify."""
    if verification is None or verification.verified:
        return None
    return VerificationError(
        f"run {run_id} produced a report whose local proof does not verify",
        code=PROOF_BUNDLE_INVALID,
        details={
            "run_id": run_id,
            "failed_checks": [message.id for message in verification.failures],
        },
    )


def _default_format(context: CliContext) -> ResultFormat:
    """Return the rendering a reader gets when they did not choose one.

    Spec section 7.21: rich for a person at a terminal, compact when the output
    is going somewhere else — a pipe, a file, or a gateway that will forward
    it. Machine mode renders neither.
    """
    return ResultFormat.RICH if sys.stdout.isatty() else ResultFormat.COMPACT


# ---------------------------------------------------------------------------
# Messages and next actions
# ---------------------------------------------------------------------------


def _development_warnings(development_only: bool) -> list[CliMessage]:
    if not development_only:
        return []
    return [
        CliMessage(
            level=MessageLevel.WARNING,
            code="development_only_result",
            text=_DEVELOPMENT_ONLY_WARNING,
        )
    ]


def _result_warnings(report: UpliftReport) -> list[CliMessage]:
    """Return the caveat a finished report carries. Spec section 29.

    A report knows which DataPolicy its run executed under, so the warning on
    a result can name it. Progress reporting cannot — a run in flight has no
    report yet — which is why ``run status`` carries the shorter caveat.
    """
    if report.proof_grade != "development_only":
        return []
    return [
        CliMessage(
            level=MessageLevel.WARNING,
            code="development_only_result",
            text=development_only_result_notice(report.data_policy_digest),
        )
    ]


def _check_status(run_id: str) -> NextAction:
    return NextAction(
        id="run_status",
        label="Check how the run is going",
        reason="A run continues whether or not anything is watching it.",
        cli=["techtree", "run", "status", run_id],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def _read_logs(run_id: str) -> NextAction:
    return NextAction(
        id="run_logs",
        label="Read what the worker recorded",
        reason="The log says what the run was doing when it got there.",
        cli=["techtree", "run", "logs", run_id],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def _read_result(run_id: str) -> NextAction:
    return NextAction(
        id="run_result",
        label="Read the finished report",
        reason="The run has produced its result.",
        cli=["techtree", "run", "result", run_id],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


# ---------------------------------------------------------------------------
# Human rendering
# ---------------------------------------------------------------------------


def _render_status(data: object, console: Console) -> None:
    if not isinstance(data, RunStatusPayload):
        return

    rows = [
        ("Run", data.run_id),
        ("Phase", data.phase.value),
        ("Progress", _progress_text(data.progress)),
        ("Worker", _worker_text(data)),
        ("Heartbeat", _heartbeat_text(data)),
        ("Result", "ready" if data.result_available else "not yet"),
    ]
    if data.cancel_requested_at is not None:
        rows.append(("Cancellation", "requested"))
    if data.error is not None:
        rows.append(("Error", data.error.message))
    _print_pairs(console, rows)

    if data.variant_progress:
        console.print()
        _print_variant_progress(console, data.variant_progress)


def _print_variant_progress(
    console: Console, progress: dict[str, VariantProgress]
) -> None:
    """Show both sides of a comparison side by side. Spec section 6.20.

    No score appears here, and no delta. Until both variants have finished
    every task, any number would be a partial mean of a partial run, and a
    reader who saw one would reasonably take it for the answer.
    """
    baseline = progress.get(VariantName.BASELINE.value)
    candidate = progress.get(VariantName.CANDIDATE.value)

    table = Table(box=None, pad_edge=False, padding=(0, 2))
    table.add_column("", no_wrap=True)
    table.add_column("Baseline", no_wrap=True)
    table.add_column("Skill candidate", no_wrap=True)
    table.add_row("Episodes", _episode_text(baseline), _episode_text(candidate))
    table.add_row("State", _variant_state(baseline), _variant_state(candidate))
    table.add_row("Current score", PROVISIONAL_SCORE, PROVISIONAL_SCORE)
    console.print(table)
    console.print()
    console.print(SCORE_PROVISIONAL_NOTICE)


def _episode_text(variant: VariantProgress | None) -> str:
    if variant is None:
        return "not started"
    return f"{variant.completed} / {variant.total}"


def _variant_state(variant: VariantProgress | None) -> str:
    return "pending" if variant is None else variant.state


def _progress_text(progress: RunProgress | None) -> str:
    if progress is None:
        return "not started"
    return f"{progress.current} of {progress.total} {progress.label}"


def _worker_text(data: RunStatusPayload) -> str:
    if data.worker_pid is None:
        return "not started"
    return f"{'running' if data.worker_alive else 'gone'} (pid {data.worker_pid})"


def _heartbeat_text(data: RunStatusPayload) -> str:
    if data.heartbeat_age_seconds is None:
        return "none yet"
    age = f"{data.heartbeat_age_seconds:.0f}s ago"
    return f"{age} (stale)" if data.heartbeat_stale else age


def _render_logs(data: object, console: Console) -> None:
    if not isinstance(data, RunLogsPayload):
        return
    if not data.lines:
        console.print("The worker has not written anything yet.")
        return
    if data.truncated:
        console.print(f"Showing the last {len(data.lines)} lines.")
    for line in data.lines:
        console.print(line)


def _render_cancel(data: object, console: Console) -> None:
    if not isinstance(data, RunCancelPayload):
        return
    _print_pairs(
        console,
        [
            ("Run", data.run_id),
            ("Phase", data.phase.value),
            ("Worker", "running" if data.worker_alive else "stopped"),
        ],
    )


def _render_result(data: object, console: Console) -> None:
    """Draw a finished result in the shape the reader asked for.

    The development-only banner comes before everything in every format. A
    reader who stops at the first line of an invented result has still been
    told that it is invented.
    """
    if not isinstance(data, RunResultPayload):
        return

    if data.report.proof_grade == "development_only":
        console.print(DEVELOPMENT_ONLY_BANNER)
        console.print()

    if data.format is ResultFormat.PATH:
        _render_result_paths(data, console)
        return
    if data.format is ResultFormat.COMPACT:
        console.print(render_uplift_markdown(data.presentation))
        return
    render_uplift_console(data.presentation, console, show_tasks=data.show_tasks)


def _render_result_paths(data: RunResultPayload, console: Console) -> None:
    """Print where this run's result and proof live, and nothing else.

    ``--format path`` exists for a caller that is going to open the files
    itself, so it prints paths relative to the run directory rather than the
    absolute ones: the run identifier is what a caller already has.
    """
    _print_pairs(
        console,
        [
            ("Run", data.report.run_id),
            ("Report", "report/uplift.json"),
            ("Proof bundle", f"{BUNDLE_DIRECTORY}/"),
            ("Signed report", f"{BUNDLE_DIRECTORY}/{REPORT_FILENAME}"),
        ],
    )


def _print_pairs(console: Console, pairs: list[tuple[str, str]]) -> None:
    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 2))
    table.add_column("label", no_wrap=True)
    table.add_column("value", overflow="fold")
    for label, value in pairs:
        table.add_row(label, value)
    console.print(table)
