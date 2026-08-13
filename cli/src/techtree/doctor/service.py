"""Running the checks and deciding what to do about them. Spec section 13.2.

The service owns three decisions the CLI must not make for itself: the order
checks run in, which failures actually block, and which repairs are worth
offering. Keeping them here is what lets the Doctor command be nine lines of
plumbing with no opinion in it.

Repairs are chosen by priority and capped at three. Some problems have a
concrete argument vector that fixes them — a permissions change, an engine
install. Others cannot be fixed by anything Techtree is allowed to run, and for
those the action's argv is the re-check and the reason says what a person has
to do first. That is deliberate: a next action is a promise that running the
vector is safe and sensible, so it never carries a placeholder to be filled in
or an installer piped out of the network.

When nothing needs repair the caller is not left without a next step. The
useful thing to do on a healthy host is to look at what there is to climb.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Final

from techtree.doctor.checks import (
    check_active_engine,
    check_docker_cli,
    check_docker_daemon,
    check_hermes_cli,
    check_host_platform,
    check_python_version,
    check_techtree_home,
    check_uv_cli,
    detect_host_platform,
)
from techtree.models.base import NonEmptyString, ProtocolModel
from techtree.models.cli import MAX_NEXT_ACTIONS, CheckStatus, DoctorCheck, NextAction
from techtree.paths import TechtreePaths
from techtree.settings import Settings
from techtree.version import version_info

__all__ = ["DoctorReport", "DoctorService"]

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

    def run(self) -> list[DoctorCheck]:
        """Run checks in deterministic order."""
        host_platform = detect_host_platform()
        return [
            check_python_version(),
            check_host_platform(host_platform),
            check_techtree_home(self._paths),
            check_uv_cli(),
            check_docker_cli(),
            check_docker_daemon(),
            check_hermes_cli(),
            check_active_engine(self._paths, self._settings),
        ]

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

    def warnings(self, checks: list[DoctorCheck]) -> list[DoctorCheck]:
        """Return warnings."""
        return [
            check
            for check in checks
            if check.status is CheckStatus.WARN
            or (check.status is CheckStatus.FAIL and not check.blocking)
        ]

    def next_actions(self, checks: list[DoctorCheck]) -> list[NextAction]:
        """Create no more than three repair actions."""
        by_id = {check.id: check for check in checks}
        actions: list[NextAction] = []
        offered: set[str] = set()

        for check_id, build in _REPAIRS:
            check = by_id.get(check_id)
            if check is None or check.status in (CheckStatus.PASS, CheckStatus.SKIP):
                continue
            action = build(self._paths)
            # Two checks can share one repair — a missing Docker CLI and an
            # unreachable daemon are both fixed by installing and starting it.
            if action is None or action.id in offered:
                continue
            actions.append(action)
            offered.add(action.id)
            if len(actions) == MAX_NEXT_ACTIONS:
                return actions

        if actions:
            return actions
        return [_browse_climbs()]


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


def _fix_home_permissions(paths: TechtreePaths) -> NextAction:
    return NextAction(
        id="fix_techtree_home_permissions",
        label="Make the Techtree home directory private and writable",
        reason="Techtree stores drafts, runs, and engines there for one user only.",
        cli=["chmod", "700", str(paths.root)],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=True,
    )


def _install_supported_python(_: TechtreePaths) -> NextAction:
    return NextAction(
        id="install_supported_python",
        label="Install a supported Python and re-run Doctor",
        reason="Techtree requires Python 3.12 or 3.13.",
        cli=["uv", "python", "install", "3.12"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=True,
    )


def _install_engine(_: TechtreePaths) -> NextAction:
    return NextAction(
        id="install_engine",
        label="Install the managed evaluation engine",
        reason="Preparing or starting a Climb needs an installed, active engine.",
        cli=["techtree", "engine", "install"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def _recheck_after_installing_uv(_: TechtreePaths) -> NextAction:
    return NextAction(
        id="recheck_after_installing_uv",
        label="Install uv, then re-run Doctor",
        reason=(
            "The managed evaluation engine is installed with uv. Installation "
            f"instructions: {UV_INSTALL_DOCUMENTATION}"
        ),
        cli=["techtree", "doctor"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def _recheck_after_starting_docker(_: TechtreePaths) -> NextAction:
    return NextAction(
        id="recheck_after_starting_docker",
        label="Start Docker, then re-run Doctor",
        reason="An evaluated subject runs in a container on this host.",
        cli=["techtree", "doctor"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def _unsupported_host(_: TechtreePaths) -> None:
    """No repair exists for the wrong machine, so no action is offered."""
    return None


def _browse_climbs() -> NextAction:
    return NextAction(
        id="list_climbs",
        label="Browse the available Climbs",
        reason="This host is ready.",
        cli=["techtree", "climb", "list"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


#: Check identifier to repair builder, most important first. A builder returns
#: None when the problem is real and nothing runnable would fix it.
type _Repair = Callable[[TechtreePaths], NextAction | None]

_REPAIRS: Final[tuple[tuple[str, _Repair], ...]] = (
    ("techtree_home", _fix_home_permissions),
    ("python_version", _install_supported_python),
    ("host_platform", _unsupported_host),
    ("uv", _recheck_after_installing_uv),
    ("active_engine", _install_engine),
    ("docker_cli", _recheck_after_starting_docker),
    ("docker_daemon", _recheck_after_starting_docker),
)
