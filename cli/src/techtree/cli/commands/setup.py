"""``techtree setup``. Spec section 12.9.

One command that takes a machine from "Techtree is installed" to "Techtree can
run a Climb here": create the local layout, refuse early if a prerequisite is
missing, install the engine this build ships, make it the active one, verify
it, settle the local signing key, and say what to do next.

The signing key is created here rather than on first use, and it is announced
rather than assumed: a person running setup is asking this machine to be made
ready, which is the moment to tell them a key exists, what it is for, and
where each half of it goes.

It does not install the Hermes plugin. ``--hermes`` is reserved so that the
name means one thing when it does exist, and until then it says so.

Prerequisites are checked before anything is downloaded. Finding out that the
host is unsupported after a several-hundred-megabyte install would be a worse
version of the same answer.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from techtree.cli.commands.engine import render_engine_status
from techtree.cli.context import CliContext, cli_context
from techtree.cli.invoke import CommandResult, invoke_command, not_implemented_error
from techtree.doctor.service import DoctorService
from techtree.engines.installer import (
    EngineInstaller,
    InterruptedInstall,
    find_uv,
)
from techtree.engines.registry import EngineRegistry
from techtree.errors import PrerequisiteError
from techtree.identity.service import IdentityService
from techtree.identity.store import IdentityStore
from techtree.models.cli import CliMessage, MessageLevel, NextAction
from techtree.models.engine import EngineStatus
from techtree.paths import ensure_path_layout

__all__ = ["LOCAL_SIGNING_KEY_NOTICE", "setup_command"]

COMMAND = "setup"

#: Spec section 7.5. Printed whenever setup settles this machine's identity,
#: whether it made one or found one, because the sentence a person needs is
#: what the key is for and where each half of it goes.
#:
#: The two halves used to be summarised as "the key is not uploaded", which was
#: true and, since decisions 0038 built ``techtree publish``, is now the kind
#: of sentence a reader could take further than it goes. A published proof
#: carries the public half inside the envelopes it signs — that is what makes
#: the signature checkable by somebody who does not trust us — so the notice
#: says which half travels rather than implying neither does.
LOCAL_SIGNING_KEY_NOTICE = (
    "Techtree keeps a local signing key, used only to detect changes to your "
    "local receipts. The private half never leaves the key directory. The "
    "public half travels inside the proofs it signs, which is what lets "
    "anybody check one.\n"
    "Key: {key_id}"
)


def setup_command(
    ctx: typer.Context,
    hermes: Annotated[
        bool,
        typer.Option(
            "--hermes",
            help="Reserved for installing the Hermes plugin. Not available yet.",
        ),
    ] = False,
) -> None:
    """Prepare this machine to run a Climb."""
    context = cli_context(ctx)

    def action() -> CommandResult[EngineStatus]:
        if hermes:
            raise not_implemented_error("setup --hermes")

        ensure_path_layout(context.paths)
        _check_prerequisites(context)

        registry = EngineRegistry(context.paths, context.settings)
        installer = EngineInstaller(context.paths, registry, find_uv())

        # Decisions 0004, ratified as 0007 R7: an install that was killed is
        # found here, said out loud, and discarded by the install that
        # follows. Reported before the install so the sentence a person reads
        # is about the machine they left behind, not about this run.
        interrupted = installer.interrupted_installs()
        installed = installer.install()
        registry.set_active(installed.digest)
        status = installer.verify(installed.digest)
        identity = IdentityService(IdentityStore(context.paths)).ensure()

        return CommandResult(
            data=status,
            messages=[
                CliMessage(
                    level=MessageLevel.INFO,
                    code="local_signing_key",
                    text=LOCAL_SIGNING_KEY_NOTICE.format(key_id=identity.key_id),
                ),
                CliMessage(
                    level=MessageLevel.INFO,
                    code="setup_complete",
                    text=(
                        f"This machine is ready. Evaluation engine "
                        f"{status.digest} is installed, verified, and active."
                    ),
                ),
            ],
            warnings=[_interrupted_notice(install) for install in interrupted],
            next_actions=[_browse_climbs()],
        )

    invoke_command(context, COMMAND, action, render_data=_render)


def _interrupted_notice(install: InterruptedInstall) -> CliMessage:
    """Say that an earlier install did not finish, and what became of it."""
    when = "" if install.started_at is None else f", started {install.started_at}"
    return CliMessage(
        level=MessageLevel.WARNING,
        code="engine_install_interrupted",
        text=(
            f"An earlier install of evaluation engine {install.digest} did not "
            f"finish{when}. What it left behind was removed and the engine was "
            "installed again from scratch."
        ),
    )


def _check_prerequisites(context: CliContext) -> None:
    """Stop before installing anything if this host cannot run a Climb."""
    doctor = DoctorService(context.paths, context.settings)
    blocking = doctor.blocking_failures(doctor.run())
    if not blocking:
        return

    identifiers = [check.id for check in blocking]
    raise PrerequisiteError(
        "this host is not ready to run a Climb: " + ", ".join(identifiers),
        code="environment_not_ready",
        details={"failed_checks": list(identifiers)},
        next_actions=[_run_doctor()],
    )


def _render(data: object, console: Console) -> None:
    if isinstance(data, EngineStatus):
        render_engine_status(data, console)


def _run_doctor() -> NextAction:
    return NextAction(
        id="run_doctor",
        label="See what this machine is missing",
        reason="Doctor lists every prerequisite and how to satisfy it.",
        cli=["techtree", "doctor"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


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
