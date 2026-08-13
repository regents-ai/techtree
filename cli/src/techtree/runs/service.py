"""Run control, and the transaction that makes starting safe. Spec PR8 §8.8.

Starting a run spends something that cannot be un-spent: a one-time
confirmation, and with it a participant's acceptance of a rights policy. It
also crosses four separate pieces of state — the draft's start claim, the run
directory, the staged inputs, and a detached process — with a crash possible
between any two of them. The whole of :meth:`RunService.start` exists to make
that sequence survivable.

The rule it is built on is that the *draft* decides which run identifier a
draft becomes. :meth:`~techtree.drafts.store.DraftStore.claim_start` writes
``start.json`` under the draft's lock and returns whatever it already holds, so
the identifier is allocated exactly once no matter how many starts are
attempted or where they crash. Everything after that point is repair: the run
directory is created if it is missing, the inputs are staged if they are not
staged, the worker is launched only if no worker has ever announced itself.
Spec §9.2 through §9.5 are each a line in that algorithm, and each is tested.

Two things are deliberately not automatic.

*A failed launch does not produce a second run.* The run is marked failed, the
draft's claim is marked ``launch_failed``, and the confirmation stays consumed.
Retrying returns the same failed run rather than quietly allocating another,
because the participant asked to start one run and the honest answer is that
that run failed. A future explicit retry operation may say otherwise.

*Reading a run's status never changes it.* A worker that died leaves a
nonterminal run with a stale heartbeat, and that is exactly what
:meth:`RunService.status` reports. Inventing a failure transition on a read
would mean the run's history recorded something nobody observed; spec §8.8
reserves that for an explicit reconciliation path.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from techtree.canonical import digest_object, to_json_value
from techtree.constants import DEFAULT_STALE_HEARTBEAT_SECONDS
from techtree.drafts.store import (
    DraftSnapshot,
    DraftStartRecord,
    DraftStartStatus,
    DraftStore,
)
from techtree.errors import (
    ConflictError,
    NotFoundError,
    PolicyError,
    RunError,
    TechtreeError,
    UsageError,
    ValidationError,
    VerificationError,
    error_to_cli_error,
    sanitize_text,
)
from techtree.ids import new_id
from techtree.models.evaluation_backend import SUPPORTED_EVALUATION_BACKEND_KINDS
from techtree.models.run import (
    PolicyAcknowledgement,
    RunPhase,
    RunRequest,
    RunState,
    RunStatus,
)
from techtree.models.uplift_report import UpliftReport
from techtree.paths import TechtreePaths
from techtree.runs.artifacts import RunArtifactStore
from techtree.runs.events import DETAIL_ERROR, RUN_FAILED
from techtree.runs.launcher import WorkerLauncher
from techtree.runs.machine import is_terminal
from techtree.runs.store import RunStore
from techtree.verifiers.models import RunPaths, VariantName
from techtree.verifiers.outputs import EVAL_LOG_FILENAME

__all__ = [
    "ACKNOWLEDGEMENT_METHODS",
    "CONFIRMATION_TOKEN_REQUIRED",
    "DEFAULT_LOG_TAIL",
    "DRAFT_ALREADY_STARTED",
    "MAXIMUM_LOG_TAIL",
    "MINIMUM_LOG_TAIL",
    "POLICY_ACCEPTANCE_DIGEST_MISMATCH",
    "POLICY_ACCEPTANCE_METHOD_INVALID",
    "POLICY_ACCEPTANCE_REQUIRED",
    "RUN_LOGS_UNAVAILABLE",
    "RUN_RESULT_DIGEST_MISMATCH",
    "RUN_RESULT_NOT_READY",
    "CancellationOutcome",
    "ProcessHealth",
    "RunCancellation",
    "RunLogs",
    "RunService",
]

#: Stable error codes. Spec PR8 §8.16.
CONFIRMATION_TOKEN_REQUIRED: Final = "confirmation_token_required"
DRAFT_ALREADY_STARTED: Final = "draft_already_started"
POLICY_ACCEPTANCE_REQUIRED: Final = "policy_acceptance_required"
POLICY_ACCEPTANCE_DIGEST_MISMATCH: Final = "policy_acceptance_digest_mismatch"
POLICY_ACCEPTANCE_METHOD_INVALID: Final = "policy_acceptance_method_invalid"
RUN_RESULT_NOT_READY: Final = "run_result_not_ready"
RUN_RESULT_DIGEST_MISMATCH: Final = "run_result_digest_mismatch"
RUN_LOGS_UNAVAILABLE: Final = "run_logs_unavailable"

#: How a person or a machine may state that a rights policy was accepted in
#: this build. ``host_agent_confirmation`` is reserved for the future plugin
#: and there is no channel that could produce it, so accepting it would be
#: accepting an acknowledgement nobody made.
ACKNOWLEDGEMENT_METHODS: Final[frozenset[str]] = frozenset(
    {"interactive_cli", "explicit_cli_digest"}
)

#: Log tail bounds. Spec PR8 §8.13.
DEFAULT_LOG_TAIL: Final = 200
MINIMUM_LOG_TAIL: Final = 1
MAXIMUM_LOG_TAIL: Final = 5000

type CancellationOutcome = Literal["requested", "already_requested", "already_terminal"]


def utc_now() -> datetime:
    """Return the current instant in UTC."""
    return datetime.now(UTC)


@dataclass(frozen=True)
class ProcessHealth:
    """What the host can say about a run's worker that its log cannot."""

    worker_pid: int | None
    worker_alive: bool
    heartbeat_at: datetime | None
    heartbeat_age_seconds: float | None
    heartbeat_stale: bool


@dataclass(frozen=True)
class RunCancellation:
    """The result of asking a run to stop, and which of the three it was."""

    status: RunStatus
    outcome: CancellationOutcome


@dataclass(frozen=True)
class RunLogs:
    """A bounded, scrubbed window onto one run's worker log."""

    run_id: str
    lines: list[str]
    truncated: bool


class RunService:
    """Transactional, idempotent run control for the CLI."""

    def __init__(
        self,
        *,
        paths: TechtreePaths,
        draft_store: DraftStore,
        run_store: RunStore,
        artifact_store: RunArtifactStore,
        launcher: WorkerLauncher,
        clock: Callable[[], datetime] = utc_now,
        stale_heartbeat_seconds: float = DEFAULT_STALE_HEARTBEAT_SECONDS,
    ) -> None:
        self._paths = paths
        self._drafts = draft_store
        self._runs = run_store
        self._artifacts = artifact_store
        self._launcher = launcher
        self._clock = clock
        self._stale_after = stale_heartbeat_seconds

    # -- starting -----------------------------------------------------------

    def start(
        self,
        *,
        draft_id: str,
        confirmation_token: str,
        policy_acknowledgement: PolicyAcknowledgement,
    ) -> RunStatus:
        """Claim the draft, create the run, stage inputs, and launch."""
        if not confirmation_token.strip():
            raise UsageError(
                "starting a prepared draft needs the confirmation token that "
                "`techtree climb prepare` returned",
                code=CONFIRMATION_TOKEN_REQUIRED,
                details={"draft_id": draft_id},
            )

        snapshot = self._drafts.load_snapshot(draft_id)
        self._require_startable(snapshot, policy_acknowledgement)

        existing = self._drafts.start_record(draft_id)
        proposed = existing.run_id if existing is not None else new_id("run")
        record = self._drafts.claim_start(
            draft_id=draft_id,
            token=confirmation_token,
            run_id=proposed,
        )

        request = self._request_for(
            record=record,
            snapshot=snapshot,
            policy_acknowledgement=policy_acknowledgement,
        )
        self._ensure_run_exists(record, request)
        self._artifacts.stage_inputs(
            run_id=record.run_id, request=request, snapshot=snapshot
        )
        return self._ensure_launched(record)

    def _require_startable(
        self,
        snapshot: DraftSnapshot,
        acknowledgement: PolicyAcknowledgement,
    ) -> None:
        """Check everything that must hold before any state is mutated."""
        draft = snapshot.draft
        if draft.policy_acceptance.required and acknowledgement.data_policy_digest != (
            draft.data_policy_digest
        ):
            raise PolicyError(
                "the accepted DataPolicy is not the one this draft runs under",
                code=POLICY_ACCEPTANCE_DIGEST_MISMATCH,
                details={
                    "draft_id": draft.id,
                    "expected_digest": draft.data_policy_digest,
                    "accepted_digest": acknowledgement.data_policy_digest,
                },
            )
        if acknowledgement.method not in ACKNOWLEDGEMENT_METHODS:
            raise PolicyError(
                f"{acknowledgement.method} is not a way this build can record "
                "acceptance of a data policy",
                code=POLICY_ACCEPTANCE_METHOD_INVALID,
                details={"draft_id": draft.id, "method": acknowledgement.method},
            )
        if not snapshot.comparison.controlled:
            raise VerificationError(
                "this draft's candidate differs from its baseline somewhere "
                "the Campaign does not permit, so it cannot be run",
                code="manifest_comparison_invalid",
                details={"draft_id": draft.id},
            )

        kind = snapshot.resolved_climb.campaign.evaluation_backend.kind
        if kind not in SUPPORTED_EVALUATION_BACKEND_KINDS:
            raise VerificationError(
                f"this Campaign is evaluated by {kind.value}, which this build "
                "does not run",
                code="evaluation_backend_unsupported",
                details={"draft_id": draft.id, "evaluation_backend": kind.value},
            )

    def _request_for(
        self,
        *,
        record: DraftStartRecord,
        snapshot: DraftSnapshot,
        policy_acknowledgement: PolicyAcknowledgement,
    ) -> RunRequest:
        """Return the run's immutable request, existing or newly built.

        A run that already exists keeps the request it was created with. The
        acknowledgement recorded there is the one that was made at the time,
        and a retried start must not overwrite it with a fresher timestamp.
        """
        draft = snapshot.draft
        try:
            existing = self._runs.get_request(record.run_id)
        except NotFoundError:
            existing = None

        if existing is not None:
            if existing.draft_id != draft.id:
                raise ConflictError(
                    f"draft {draft.id} is claimed by run {record.run_id}, which "
                    "was created from a different draft",
                    code=DRAFT_ALREADY_STARTED,
                    details={"draft_id": draft.id, "run_id": record.run_id},
                )
            return existing

        return RunRequest(
            run_id=record.run_id,
            draft_id=draft.id,
            draft_digest=digest_object(draft),
            campaign_spec_digest=draft.campaign_spec_digest,
            program_ref=draft.program_ref,
            public_context=draft.public_context,
            data_policy_digest=draft.data_policy_digest,
            outcome_contract_digest=draft.outcome_contract_digest,
            evaluation_backend=snapshot.resolved_climb.campaign.evaluation_backend,
            taskset_lock_digest=(
                snapshot.resolved_climb.publisher_validation.taskset_lock_digest
            ),
            baseline_manifest_digest=draft.baseline_manifest_digest,
            candidate_manifest_digest=draft.candidate_manifest_digest,
            policy_acknowledgement=policy_acknowledgement,
            executor_kind="fake",
            created_at=self._clock(),
        )

    def _ensure_run_exists(self, record: DraftStartRecord, request: RunRequest) -> None:
        """Create the run directory unless a previous attempt already did."""
        try:
            self._runs.get_request(record.run_id)
        except NotFoundError:
            self._runs.create(request)

    def _ensure_launched(self, record: DraftStartRecord) -> RunStatus:
        """Launch the worker if, and only if, none has ever been launched."""
        run_id = record.run_id
        state = self._runs.state(run_id)

        if record.status is DraftStartStatus.LAUNCH_FAILED:
            raise RunError(
                f"run {run_id} could not be started, and a draft is spent on "
                "exactly one run",
                code="worker_launch_failed",
                details={
                    "run_id": run_id,
                    "draft_id": record.draft_id,
                    "launch_error_code": record.launch_error_code,
                },
            )

        # A worker announces its own process id as its first act, so evidence
        # of a worker is evidence that the launch happened even if the
        # launching process died before it could record anything.
        if state.worker_pid is not None or is_terminal(state.phase):
            return self.status(run_id)

        try:
            pid = self._launcher.launch(run_id)
        except TechtreeError as error:
            self._record_launch_failure(record, error)
            raise

        # The pid file and the ``worker.started`` event are the launcher's to
        # write only until the worker writes them itself; whichever gets there
        # first, the other finds the run already carries a worker and leaves
        # it alone. Spec §9.5: a worker records its own process id as its
        # first act, so the run is complete either way.
        if self._runs.state(run_id).worker_pid is None:
            with suppress(ConflictError, RunError, ValidationError):
                self._runs.write_pid(run_id, pid)

        self._drafts.mark_launched(
            draft_id=record.draft_id,
            run_id=run_id,
            launched_at=self._clock(),
        )
        return self.status(run_id)

    def _record_launch_failure(
        self, record: DraftStartRecord, error: TechtreeError
    ) -> None:
        """Leave a failed launch addressable rather than invisible."""
        state = self._runs.state(record.run_id)
        if not is_terminal(state.phase):
            self._runs.append(
                record.run_id,
                phase=RunPhase.FAILED,
                kind=RUN_FAILED,
                details={DETAIL_ERROR: to_json_value(error_to_cli_error(error))},
            )
        self._drafts.mark_launch_failed(
            draft_id=record.draft_id,
            run_id=record.run_id,
            error_code=error.code,
        )

    # -- reading ------------------------------------------------------------

    def status(self, run_id: str) -> RunStatus:
        """Return the projected state plus process and heartbeat health."""
        state = self._runs.state(run_id)
        health = self._health(run_id, state)
        return RunStatus(
            state=state,
            worker_alive=health.worker_alive,
            heartbeat_stale=health.heartbeat_stale,
            result_available=self._runs.result_path(run_id).exists(),
        )

    def request(self, run_id: str) -> RunRequest:
        """Return the immutable request this run executes."""
        return self._runs.get_request(run_id)

    def process_health(self, run_id: str) -> ProcessHealth:
        """Return what the host knows about this run's worker process."""
        return self._health(run_id, self._runs.state(run_id))

    def _health(self, run_id: str, state: RunState) -> ProcessHealth:
        alive = self._launcher.is_alive(run_id)
        heartbeat = state.heartbeat_at
        age = None if heartbeat is None else (self._clock() - heartbeat).total_seconds()

        if is_terminal(state.phase):
            # A run that has ended is not expected to have a heartbeat, and
            # calling the absence of one "stale" would report every finished
            # run as unhealthy.
            stale = False
        elif state.worker_pid is None:
            stale = False
        else:
            stale = age is None or age > self._stale_after

        return ProcessHealth(
            worker_pid=state.worker_pid,
            worker_alive=alive,
            heartbeat_at=heartbeat,
            heartbeat_age_seconds=age,
            heartbeat_stale=stale,
        )

    def result(self, run_id: str) -> UpliftReport:
        """Return the report, once the run has finished and it verifies."""
        state = self._runs.state(run_id)
        if state.phase is not RunPhase.COMPLETED:
            raise RunError(
                f"run {run_id} is {state.phase.value} and has no result yet",
                code=RUN_RESULT_NOT_READY,
                retryable=not is_terminal(state.phase),
                details={"run_id": run_id, "phase": state.phase.value},
            )

        report = self._runs.get_result(run_id)
        recomputed = digest_object(report)
        if state.result_digest is None or recomputed != state.result_digest:
            raise VerificationError(
                f"the report stored for run {run_id} is not the report its "
                "journal recorded",
                code=RUN_RESULT_DIGEST_MISMATCH,
                details={
                    "run_id": run_id,
                    "expected": state.result_digest,
                    "computed": recomputed,
                },
            )
        return report

    def logs(self, run_id: str, *, tail: int = DEFAULT_LOG_TAIL) -> RunLogs:
        """Return the last ``tail`` lines of the worker log, scrubbed."""
        return self._read_log(
            run_id,
            path=self._runs.worker_log_path(run_id),
            tail=tail,
            missing=f"run {run_id} has written no log yet",
        )

    def variant_logs(
        self, run_id: str, variant: VariantName, *, tail: int = DEFAULT_LOG_TAIL
    ) -> RunLogs:
        """Return one variant's evaluation log, scrubbed. Spec section 6.20.

        The engine's own ``eval.log`` is the answer, never the child's captured
        stdout. With rich output disabled the pinned CLI dumps every trace to
        stdout as indented JSON when the run ends
        (``docs/verifiers-eval.md``), and those are the subject's transcripts.
        They are retained for diagnosis on disk and are not something a log
        command hands back to whoever asked.
        """
        paths = RunPaths.for_run(self._paths, run_id)
        return self._read_log(
            run_id,
            path=paths.variant_output_dir(variant) / EVAL_LOG_FILENAME,
            tail=tail,
            missing=(
                f"the {variant.value} variant of run {run_id} has not started "
                "evaluating yet"
            ),
        )

    def _read_log(self, run_id: str, *, path: Path, tail: int, missing: str) -> RunLogs:
        """Read the tail of one log file, scrubbing every line."""
        if tail < MINIMUM_LOG_TAIL or tail > MAXIMUM_LOG_TAIL:
            raise UsageError(
                f"--tail is between {MINIMUM_LOG_TAIL} and {MAXIMUM_LOG_TAIL} "
                f"lines; {tail} is outside that",
                details={
                    "run_id": run_id,
                    "tail": tail,
                    "minimum": MINIMUM_LOG_TAIL,
                    "maximum": MAXIMUM_LOG_TAIL,
                },
            )

        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError as error:
            raise NotFoundError(
                missing,
                code=RUN_LOGS_UNAVAILABLE,
                retryable=True,
                details={"run_id": run_id},
            ) from error

        lines = raw.splitlines()
        return RunLogs(
            run_id=run_id,
            lines=[sanitize_text(line) for line in lines[-tail:]],
            truncated=len(lines) > tail,
        )

    def scrub(self, line: str) -> str:
        """Return one log line as it may be shown.

        Exposed so that ``--follow`` sanitizes each line as it arrives through
        exactly the same path a bounded read does.
        """
        return sanitize_text(line)

    def worker_log_path(self, run_id: str) -> Path:
        """Return the log file a follower reads.

        The path is for the CLI's own use. It is never put in a response:
        spec §8.13 is explicit that a run's answer must not hand another agent
        an arbitrary file to read.
        """
        return self._runs.worker_log_path(run_id)

    # -- cancelling ---------------------------------------------------------

    def cancel(self, run_id: str, *, requested_by: str = "cli") -> RunCancellation:
        """Ask a run to stop, idempotently, and signal its worker."""
        state = self._runs.state(run_id)
        if is_terminal(state.phase):
            return RunCancellation(
                status=self.status(run_id), outcome="already_terminal"
            )

        already = state.phase is RunPhase.CANCEL_REQUESTED
        self._runs.request_cancel(run_id, requested_by=requested_by)
        self._launcher.request_termination(run_id)
        return RunCancellation(
            status=self.status(run_id),
            outcome="already_requested" if already else "requested",
        )
