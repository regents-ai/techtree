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
from techtree.models.base import NonEmptyString, ProtocolModel
from techtree.models.cli import (
    CliWarning,
    DataEgress,
    NextAction,
    Operation,
    RetryClass,
    SideEffect,
    invocation,
)
from techtree.models.engine import EngineStatus
from techtree.paths import ensure_path_layout

__all__ = ["LOCAL_SIGNING_KEY_NOTICE", "SetupPayload", "setup_command"]

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


class SetupPayload(ProtocolModel):
    """What one setup settled: the engine, and this machine's identity.

    The key identifier is a fact rather than a sentence. A caller that is a
    program has to be able to read which key this machine will sign with, and
    a machine answer that carried the engine but only mentioned the key in
    prose would leave it unreadable to exactly the caller that most needs it.
    """

    engine: EngineStatus
    key_id: NonEmptyString


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

    def action() -> CommandResult[SetupPayload]:
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
            data=SetupPayload(engine=status, key_id=identity.key_id),
            warnings=[_interrupted_notice(install) for install in interrupted],
            next_actions=[_browse_climbs()],
        )

    invoke_command(context, Operation.ACTION_EXECUTE, action, render_data=_render)


def _interrupted_notice(install: InterruptedInstall) -> CliWarning:
    """Say that an earlier install did not finish, and what became of it."""
    when = "" if install.started_at is None else f", started {install.started_at}"
    return CliWarning(
        id="engine_install_interrupted",
        text=(
            f"An earlier install of evaluation engine {install.digest} did not "
            f"finish{when}. What it left behind was removed and the engine was "
            "installed again from scratch."
        ),
        resolvable_by=None,
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
    """Say what setup settled, then show the engine and the key it settled."""
    if not isinstance(data, SetupPayload):
        return
    console.print(
        f"This machine is ready. Evaluation engine {data.engine.digest} is "
        "installed, verified, and active."
    )
    console.print()
    render_engine_status(data.engine, console)
    console.print()
    console.print(LOCAL_SIGNING_KEY_NOTICE.format(key_id=data.key_id))


def _run_doctor() -> NextAction:
    return NextAction(
        operation=Operation.PLAN_INSPECT,
        prepared_arguments=invocation("doctor"),
        expected_state_digest=None,
        side_effect=SideEffect.NONE,
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.NONE,
        reason="Doctor lists every prerequisite and how to satisfy it.",
    )


def _browse_climbs() -> NextAction:
    return NextAction(
        operation=Operation.PLAN_INSPECT,
        prepared_arguments=invocation("climb", "list"),
        expected_state_digest=None,
        side_effect=SideEffect.NONE,
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.NONE,
        reason="This host is ready; these are the Climbs it can run.",
    )
