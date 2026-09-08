"""Running the checks and deciding what to do about them. Spec section 13.2.

The service owns three decisions the CLI must not make for itself: the order
checks run in, which failures actually block, and which repairs are worth
offering. Keeping them here is what lets the Doctor command be nine lines of
plumbing with no opinion in it.

What a check found and what to do about it are two halves of one answer, and
the service produces both. A failing check becomes a blocker or a warning whose
text carries the repair — including the ones only a person can carry out, a
permissions change, an interpreter, a container runtime, a sign-in — and the
next actions are the Techtree operations that follow. A next action names a
Techtree operation and nothing else, so an instruction to run something that is
not Techtree is stated in words rather than handed over as a command somebody's
agent might run unread.

Repairs are chosen by priority and capped at three. When nothing needs repair
the caller is not left without a next step: the useful thing to do on a healthy
host is to look at what there is to climb.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal

from techtree.doctor.checks import (
    check_active_engine,
    check_docker_cli,
    check_docker_daemon,
    check_hermes_cli,
    check_hermes_plugin,
    check_host_platform,
    check_python_version,
    check_techtree_home,
    check_uv_cli,
    detect_host_platform,
)
from techtree.doctor.execution_checks import execution_checks
from techtree.engines.registry import EngineRegistry
from techtree.models.base import NonEmptyString, ProtocolModel
from techtree.models.campaign import CampaignSpecV2
from techtree.models.cli import (
    MAX_NEXT_ACTIONS,
    CheckStatus,
    CliBlocker,
    CliWarning,
    DataEgress,
    DoctorCheck,
    NextAction,
    Operation,
    RetryClass,
    SideEffect,
    invocation,
)
from techtree.paths import TechtreePaths
from techtree.settings import Settings
from techtree.version import version_info

__all__ = ["BLOCKED_OPERATIONS", "DoctorReport", "DoctorService"]

#: What a blocking environment failure forbids. A machine that cannot run a
#: Climb cannot prepare a comparison to run and cannot perform a side-effecting
#: step, and saying which operations are stopped is the whole difference
#: between a blocker and a note.
BLOCKED_OPERATIONS: Final[tuple[Operation, ...]] = (
    Operation.PLAN_PREPARE,
    Operation.ACTION_EXECUTE,
)

#: Where uv's own installation instructions live. It goes in a reason, never in
#: an argument vector: Techtree does not offer to pipe an installer into a
#: shell on someone's behalf.
UV_INSTALL_DOCUMENTATION: Final = (
    "https://docs.astral.sh/uv/getting-started/installation/"
)


class DoctorReport(ProtocolModel):
    """Everything one Doctor run found.

    The two platform strings are separate on purpose. ``host_platform`` is
    where Techtree runs; ``docker_platform`` is where an evaluated subject
    would run, and is absent whenever the daemon could not say.
    """

    techtree_home: NonEmptyString
    host_platform: NonEmptyString | None
    docker_platform: NonEmptyString | None
    versions: dict[str, NonEmptyString]
    checks: list[DoctorCheck]


class DoctorService:
    """Runs environment checks and turns them into repairs."""

    def __init__(self, paths: TechtreePaths, settings: Settings) -> None:
        self._paths = paths
        self._settings = settings

    def run(
        self,
        *,
        for_evaluation: bool = False,
        campaign: CampaignSpecV2 | None = None,
    ) -> list[DoctorCheck]:
        """Run checks in deterministic order.

        ``for_evaluation`` adds the execution checks of spec section 6.18 and
        makes them blocking. An ordinary Doctor is a question about the machine
        and answers it with warnings; the evaluation Doctor is the gate in front
        of a run that provisions containers and spends money on model calls, so
        the same facts stop it rather than merely being noted.

        A ``campaign`` narrows the question from "could anything run here" to
        "could this run here", which is the only form in which the subject's
        credential and image can be checked at all.
        """
        host_platform = detect_host_platform()
        checks = [
            check_python_version(),
            check_host_platform(host_platform),
            check_techtree_home(self._paths),
            check_uv_cli(),
            check_docker_cli(),
            check_docker_daemon(),
            check_hermes_cli(),
            check_hermes_plugin(),
            check_active_engine(self._paths, self._settings),
        ]
        if not for_evaluation:
            return checks
        registry = EngineRegistry(self._paths, self._settings)
        checks.extend(execution_checks(engine_registry=registry, campaign=campaign))
        return checks

    def report(self, checks: list[DoctorCheck]) -> DoctorReport:
        """Project the checks into the command's response payload."""
        return DoctorReport(
            techtree_home=str(self._paths.root),
            host_platform=_metadata_string(checks, "host_platform", "host_platform"),
            docker_platform=_metadata_string(
                checks, "docker_daemon", "docker_platform"
            ),
            versions=version_info(),
            checks=list(checks),
        )

    def blocking_failures(self, checks: list[DoctorCheck]) -> list[DoctorCheck]:
        """Return blocking failures."""
        return [check for check in checks if check.blocking]

    def warning_checks(self, checks: list[DoctorCheck]) -> list[DoctorCheck]:
        """Return the checks that reported something short of blocking."""
        return [
            check
            for check in checks
            if check.status is CheckStatus.WARN
            or (check.status is CheckStatus.FAIL and not check.blocking)
        ]

    def blockers(self, checks: list[DoctorCheck]) -> list[CliBlocker]:
        """Return one blocker per blocking failure, carrying its repair.

        Each names the operations it forbids rather than leaving a reader to
        work out what a failed check costs them, and each carries what to do
        about it — including the part only a person can do.
        """
        return [
            CliBlocker(
                id=check.id,
                text=_finding(check),
                blocks=list(BLOCKED_OPERATIONS),
                resolvable_by=_resolvable_by(check.id),
            )
            for check in self.blocking_failures(checks)
        ]

    def warnings(self, checks: list[DoctorCheck]) -> list[CliWarning]:
        """Return what did not stop this host and must still be seen."""
        return [
            CliWarning(
                id=check.id,
                text=_finding(check),
                resolvable_by=_resolvable_by(check.id),
            )
            for check in self.warning_checks(checks)
        ]

    def next_actions(self, checks: list[DoctorCheck]) -> list[NextAction]:
        """Create no more than three repair actions.

        Two checks can share one repair — a missing Docker CLI and an
        unreachable daemon are both fixed by installing and starting it — so a
        step that is already offered is not offered twice. What makes two steps
        the same step is what the envelope says it is: one operation with one
        set of prepared arguments. Comparing the wording instead would let two
        identical calls through the moment somebody reworded one of them.
        """
        by_id = {check.id: check for check in checks}
        actions: list[NextAction] = []
        offered: set[tuple[Operation, str]] = set()

        for check_id, repair in _REPAIRS:
            check = by_id.get(check_id)
            if check is None or check.status in (CheckStatus.PASS, CheckStatus.SKIP):
                continue
            action = repair.action
            if action is None:
                continue
            step = (
                action.operation,
                json.dumps(action.prepared_arguments, sort_keys=True),
            )
            if step in offered:
                continue
            actions.append(action)
            offered.add(step)
            if len(actions) == MAX_NEXT_ACTIONS:
                return actions

        if actions:
            return actions
        # Nothing offered a repair. That means either the host is fine, or the
        # only things wrong with it are things Techtree cannot fix — a Campaign
        # that is not meant to be executed yet, for instance. Saying "this host
        # is ready" in the second case would be a lie told cheerfully.
        return [_browse_climbs(ready=not any(check.blocking for check in checks))]


def _metadata_string(
    checks: Iterable[DoctorCheck], check_id: str, key: str
) -> str | None:
    """Read one string out of a check's metadata, if the check reported it."""
    for check in checks:
        if check.id != check_id:
            continue
        value = check.metadata.get(key)
        return value if isinstance(value, str) else None
    return None


@dataclass(frozen=True)
class _Repair:
    """What to do about one failing check.

    ``instruction`` is what a person does, in words, and it is the only place
    a step Techtree cannot take for somebody appears. ``action`` is the
    Techtree operation that follows it, and is absent when nothing Techtree can
    run would move this forward.
    """

    instruction: str | None
    action: NextAction | None


def _recheck(*, for_evaluation: bool = False) -> NextAction:
    """Return the check that says whether a repair worked."""
    options: dict[str, str | Literal[True]] = {}
    if for_evaluation:
        options["--for-evaluation"] = True
    return NextAction(
        operation=Operation.PLAN_INSPECT,
        prepared_arguments=invocation("doctor", options=options),
        expected_state_digest=None,
        side_effect=SideEffect.NONE,
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.NONE,
        reason=(
            "Doctor reports what is installed, what is missing, and what would "
            "block a run, so it says whether a repair worked."
            if not for_evaluation
            else (
                "The evaluation checks report whether this machine could run a "
                "Climb for real, so they say whether a repair worked."
            )
        ),
    )


def _install_engine() -> NextAction:
    return NextAction(
        operation=Operation.ACTION_EXECUTE,
        prepared_arguments=invocation("engine", "install"),
        expected_state_digest=None,
        side_effect=SideEffect.LOCAL_STATE,
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.PACKAGE_INDEX,
        reason="Preparing or starting a Climb needs an installed, active engine.",
    )


def _browse_climbs(*, ready: bool) -> NextAction:
    return NextAction(
        operation=Operation.PLAN_INSPECT,
        prepared_arguments=invocation("climb", "list"),
        expected_state_digest=None,
        side_effect=SideEffect.NONE,
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.NONE,
        reason=(
            "This host is ready."
            if ready
            else (
                "Nothing left to fix automatically; each failed check says what "
                "it needs."
            )
        ),
    )


def _finding(check: DoctorCheck) -> str:
    """Return what one check found, and what to do about it."""
    repair = _REPAIRS_BY_CHECK.get(check.id)
    instruction = None if repair is None else repair.instruction
    if instruction is None:
        return check.detail
    return f"{check.detail} {instruction}"


def _resolvable_by(check_id: str) -> Operation | None:
    """Return the operation that would clear this check, if one would."""
    repair = _REPAIRS_BY_CHECK.get(check_id)
    if repair is None or repair.action is None:
        return None
    return repair.action.operation


def _repairs() -> tuple[tuple[str, _Repair], ...]:
    """Return the repair table, most important first.

    The order is the order actions are offered in. A repair with no action is a
    problem that is real and that nothing Techtree runs would fix; a repair
    with no instruction is one Techtree can carry out itself.
    """
    recheck = _Repair(instruction=None, action=_recheck())
    engine = _Repair(instruction=None, action=_install_engine())
    return (
        (
            "techtree_home",
            _Repair(
                instruction=(
                    "Make that directory private and writable — chmod 700 — "
                    "and try again. Techtree stores drafts, runs, and engines "
                    "there for one user only."
                ),
                action=_recheck(),
            ),
        ),
        (
            "python_version",
            _Repair(
                instruction=(
                    "Install a supported Python — Techtree requires 3.12 or "
                    "3.13 — for example with uv python install 3.12."
                ),
                action=_recheck(),
            ),
        ),
        ("host_platform", _Repair(instruction=None, action=None)),
        (
            "uv",
            _Repair(
                instruction=(
                    "Install uv: the managed evaluation engine is installed "
                    f"with it. Installation instructions: "
                    f"{UV_INSTALL_DOCUMENTATION}"
                ),
                action=_recheck(),
            ),
        ),
        ("active_engine", engine),
        (
            "docker_cli",
            _Repair(
                instruction=(
                    "Install and start Docker: an evaluated subject runs in a "
                    "container on this host."
                ),
                action=_recheck(),
            ),
        ),
        (
            "docker_daemon",
            _Repair(
                instruction=(
                    "Start Docker: an evaluated subject runs in a container on "
                    "this host."
                ),
                action=_recheck(),
            ),
        ),
        # Spec section 6.18. These only appear under --for-evaluation, and they
        # sit last because a host that fails an ordinary check fails these too,
        # and the ordinary repair is the one worth offering first.
        ("execution_docker_platform", recheck),
        ("execution_engine_eval", engine),
        (
            "execution_model_credential",
            _Repair(
                instruction=(
                    "Sign in to Prime with prime login. The evaluated subject's "
                    "model calls are paid for by a credential a run reads for "
                    "itself, which is why signing in works and exporting the "
                    "credential in a terminal does not. It is separate from "
                    "whatever your own agent is signed in with."
                ),
                action=_recheck(for_evaluation=True),
            ),
        ),
        (
            "execution_subject_image",
            _Repair(
                instruction=(
                    "Pull the subject's container image. The evaluated subject "
                    "runs in the image the Campaign pins, and downloading it is "
                    "a deliberate setup step Techtree reports rather than takes "
                    "during a check."
                ),
                action=_recheck(for_evaluation=True),
            ),
        ),
        ("execution_live_campaign", _Repair(instruction=None, action=None)),
    )


#: The repair table, built once. Nothing in it reads the machine, so it is a
#: constant rather than something each Doctor run assembles again.
_REPAIRS: Final[tuple[tuple[str, _Repair], ...]] = _repairs()

_REPAIRS_BY_CHECK: Final[dict[str, _Repair]] = dict(_REPAIRS)
