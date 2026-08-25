"""Operator command surfaces. Specification section 7.12.

Two surfaces, deliberately different.

``/techtree …`` works in any session, including one where answers have to stay
short. A host hands a slash command the same way from a terminal and from a
chat window, with nothing that says which — so these always answer as if the
narrower window were reading: compact text, no control characters, bounded,
with the cut stated when there is one.

Every successful answer ends with one immediate next step (decision 0024
section 7), so a reader is never left holding a result with nothing to do.

``hermes techtree …`` is terminal-only, and is where Techtree's own rendered
output belongs. ``watch`` in particular runs Techtree's live view against the
user's own terminal; no model-visible tool ever holds an open watch, because a
tool call that never returns is a conversation that never continues.

The grammar is fixed. A subcommand is looked up in a table, its arguments are
checked, and anything else is refused with the list of what does exist. There
is no passthrough: nothing a user or a model types becomes part of a command.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, NamedTuple

from .channels import bounded_gateway_text, ensure_gateway_safe
from .errors import PluginError, scrub_text
from .models import ChannelKind
from .state import active_run_ids, latest_session
from .tools import TOOL_HANDLERS

SLASH_COMMAND = "techtree"

#: The one grammar, and what each part of it means to a person.
SLASH_USAGE: Mapping[str, str] = {
    "setup": "check whether Techtree is installed and this machine is ready",
    "climbs": "list the Climbs this build offers",
    "demo": "prepare Techtree Hello World, stopping before it spends",
    "status": "how a run is going — /techtree status [run-id]",
    "cancel": "stop a run — /techtree cancel <run-id>",
    "result": "the finished result — /techtree result [run-id]",
    "verify": "check a local proof — /techtree verify [run-id or path]",
    "improve": "what a finished run says about itself — /techtree improve [run-id]",
}


class SlashCommandHandler:
    """The call shape of an in-session ``/techtree`` handler."""

    def __call__(self, raw_args: str) -> str:
        """Return the text to show for this invocation."""
        raise NotImplementedError


class CliCommand(NamedTuple):
    """One ``hermes techtree …`` terminal subcommand."""

    help: str
    setup: Callable[[Any], None]
    handler: Callable[[Any], int]


def parse_slash_args(raw_args: str) -> tuple[str, list[str]]:
    """Split ``/techtree status run_…`` into a subcommand and its arguments."""
    parts = (raw_args or "").split()
    if not parts:
        return "", []
    return parts[0].lower(), parts[1:]


def handle_slash_command(raw_args: str, services: Any) -> str:
    """Run one fixed subcommand and return text any window can hold."""
    subcommand, arguments = parse_slash_args(raw_args)
    if not subcommand:
        return _usage("Techtree commands:")
    if subcommand not in SLASH_USAGE:
        return _usage(f"There is no /techtree {subcommand}. There is:")

    try:
        text = _SLASH_ACTIONS[subcommand](services, arguments)
    except PluginError as error:
        text = f"That did not work: {scrub_text(str(error))}"
    except Exception as error:  # a defect must not break the session
        text = f"That did not work: {scrub_text(str(error))}"
    return bounded_gateway_text(text)


def register_cli_subcommands(ctx: Any, services: Any) -> None:
    """Register the ``hermes techtree …`` terminal-only commands."""
    for name, command in sorted(build_cli_commands(services).items()):
        ctx.register_cli_command(
            name=name,
            help=command.help,
            setup_fn=command.setup,
            handler_fn=command.handler,
        )


# The slash grammar ------------------------------------------------------------


def _slash_setup(services: Any, arguments: Sequence[str]) -> str:
    answer = _tool(services, "techtree_bootstrap_check", {"include_doctor": True})
    lines = [_release_line(answer)]

    cli = answer.get("cli", {})
    lines.append(
        f"Techtree CLI: {cli.get('version') or 'not installed'}"
        if cli.get("installed")
        else "Techtree CLI: not installed"
    )
    if answer.get("refusal"):
        lines.append(str(answer["refusal"]["message"]))
    doctor = answer.get("doctor")
    if isinstance(doctor, dict) and doctor.get("ran"):
        blocking = doctor.get("blocking_failures") or []
        lines.append(
            "Doctor: ready"
            if not blocking
            else "Doctor: "
            + "; ".join(str(failure.get("detail")) for failure in blocking)
        )
    lines.append(_next_action_line(answer))
    return "\n".join(line for line in lines if line)


def _slash_climbs(services: Any, arguments: Sequence[str]) -> str:
    answer = _tool(services, "techtree_climbs_list", {})
    if not answer.get("ok"):
        return _error_line(answer)
    if answer.get("truncated"):
        return (
            "The list is too long to show here. "
            "Next: run `techtree climb list` in a terminal to see all of it."
        )
    climbs = answer.get("data") or []
    if not isinstance(climbs, list) or not climbs:
        return (
            "This build ships no Climbs. "
            "Next: ask me whether Techtree is installed and ready."
        )
    lines = ["Climbs in this build:"]
    for climb in climbs:
        reference = climb.get("reference") if isinstance(climb, dict) else None
        title = climb.get("title") if isinstance(climb, dict) else None
        lines.append(f"- {reference}{f' — {title}' if title else ''}")
    lines.append("Next: ask me to show one of these Climbs in detail.")
    return "\n".join(lines)


#: What the DataPolicy's publication terms mean in this build, shown where
#: those terms are handed to a person.
#:
#: A Climb's data rights describe a result that has been published: entering
#: requires releasing the candidate Skill, and the uplift report is public. On
#: their own they read as a plan to publish somebody's Skill and their numbers,
#: and two readers stopped and refused to start a run over exactly that.
#: Nothing in this build can publish anything. So the terms are shown unchanged
#: and this is shown with them.
#:
#: The last clause is not decoration. Decision 0013 section 1.4: a sentence
#: about what stays here is read as a claim that nothing goes anywhere, and
#: model calls do.
PUBLICATION_TERMS_LINE = (
    "These are the terms this Climb sets for a published result. Nothing is "
    "published from this build: your Skill, the episodes and the report stay "
    "on this machine, and model calls still go to the model provider you "
    "configured."
)


def _declared_maximum_line(answer: Mapping[str, Any]) -> str:
    """Say the most this Campaign declares it may cost, and what that is not.

    The terminal review has printed this figure since decision 0029 and this
    surface did not, so a reader who approved a run here was told a check
    happens without being told what it checks against. The number is the
    Campaign's and arrives with the prepared draft; a Campaign that declares no
    maximum says so, because a figure invented for it would be false.
    """
    maximum = answer.get("campaign_maximum_usd")
    if not isinstance(maximum, int | float) or isinstance(maximum, bool):
        return (
            "This Campaign declares no maximum, so there is no figure to hold "
            "it to. Techtree works out no figure for the bill first and keeps "
            "no running total as it goes, so what it comes to is settled by "
            "the model provider you configured."
        )
    return (
        f"The most this Campaign declares it may cost is ${maximum:.2f}. "
        "Techtree checks before it starts that the limits the Campaign "
        "enforces on each episode cannot add up past that, and refuses the "
        "run if they could. That figure is a ceiling it declares and never "
        "a prediction: Techtree works out no figure for the bill first and "
        "keeps no running total as it goes, so what it comes to is settled by "
        "the model provider you configured."
    )


def _slash_demo(services: Any, arguments: Sequence[str]) -> str:
    answer = _tool(services, "techtree_demo_prepare", {})
    if not answer.get("ok"):
        return (
            f"Techtree Hello World cannot start yet: "
            f"{answer.get('message') or _error_line(answer)}"
        )
    return "\n".join(
        [
            "Prepared Techtree Hello World, a toy Skill-uplift Climb. "
            "Nothing has run yet.",
            f"Draft: {answer.get('draft_id')}",
            f"Episodes to run: {answer.get('estimated_episodes')}",
            f"Data policy: {answer.get('data_policy_digest')}",
            PUBLICATION_TERMS_LINE,
            "Starting it spends real money on model calls, and needs your "
            "explicit approval.",
            _declared_maximum_line(answer),
            "Next: review the Skill-only change, then approve the start.",
        ]
    )


def _slash_status(services: Any, arguments: Sequence[str]) -> str:
    run_id = _run_argument(services, arguments)
    if run_id is None:
        return "No run to report on. Start one, or give me a run identifier."
    answer = _tool(services, "techtree_run_status", {"run_id": run_id})
    if not answer.get("ok"):
        return _error_line(answer)
    summary = answer.get("summary", {})
    return (
        f"Run {run_id}: {summary.get('phase')}"
        + (" — finished" if summary.get("finished") else " — still going")
        + (", result ready" if summary.get("result_available") else "")
        + "\n"
        + (
            "Next: ask me for its result."
            if summary.get("result_available")
            else "Next: ask me for its status at any time."
        )
    )


def _slash_cancel(services: Any, arguments: Sequence[str]) -> str:
    if not arguments:
        return "Name the run to stop: /techtree cancel <run-id>"
    answer = _tool(services, "techtree_run_cancel", {"run_id": arguments[0]})
    if not answer.get("ok"):
        return _error_line(answer)
    return (
        f"Asked Techtree to stop {arguments[0]}.\n"
        "Next: ask me for its status to confirm it stopped."
    )


def _slash_result(services: Any, arguments: Sequence[str]) -> str:
    run_id = _run_argument(services, arguments)
    if run_id is None:
        return "No finished run yet. Give me a run identifier once one exists."
    answer = _tool(services, "techtree_run_result", {"run_id": run_id})
    if not answer.get("ok"):
        return _error_line(answer)
    presentation = (answer.get("data") or {}).get("presentation") or {}
    lines = [f"Run {run_id}"]
    if presentation:
        lines += [
            f"Baseline {presentation.get('baseline_score')} versus candidate "
            f"{presentation.get('candidate_score')}",
            f"Won {presentation.get('wins')}, lost {presentation.get('losses')}, "
            f"tied {presentation.get('ties')}",
            f"Decision: {presentation.get('decision')}",
            f"Proof grade: {presentation.get('proof_grade')}",
        ]
    lines.append(
        "Run locally by Techtree, and not independently reproduced by anyone else."
    )
    lines.append("Next: ask me to check this run's proof offline.")
    return "\n".join(lines)


def _slash_verify(services: Any, arguments: Sequence[str]) -> str:
    target = arguments[0] if arguments else _run_argument(services, arguments)
    if target is None:
        return "Name a run or a proof path: /techtree verify <run-id or path>"
    key = "run_id" if target.startswith("run_") else "proof_path"
    answer = _tool(services, "techtree_proof_verify", {key: target})
    if not answer.get("ok"):
        return _error_line(answer)
    data = answer.get("data") or {}
    return (
        f"Proof for {target}: "
        + ("verified" if data.get("verified") else "did not verify")
        + f" ({len(data.get('checks') or [])} checks, all offline)"
        + "\n"
        + (
            "Next: ask me for the measured difference in this run's result."
            if data.get("verified")
            else f"Next: run `techtree proof verify {target}` in a terminal to "
            "see every check."
        )
    )


def _slash_improve(services: Any, arguments: Sequence[str]) -> str:
    run_id = _run_argument(services, arguments)
    if run_id is None:
        return "Name the finished run: /techtree improve <run-id>"
    answer = _tool(services, "techtree_uplift_context", {"run_id": run_id})
    if not answer.get("ok"):
        return _error_line(answer)
    return "\n".join(
        [
            f"Techtree exported the improvement context for {run_id}.",
            "It holds only what may be shown: public task inputs, pass or fail, "
            "and rewards — never the subject's answers or the expected ones.",
            "Proposing a revised Skill is not part of this build.",
            "Next: ask me to check this run's proof offline.",
        ]
    )


_SLASH_ACTIONS: Mapping[str, Callable[[Any, Sequence[str]], str]] = {
    "setup": _slash_setup,
    "climbs": _slash_climbs,
    "demo": _slash_demo,
    "status": _slash_status,
    "cancel": _slash_cancel,
    "result": _slash_result,
    "verify": _slash_verify,
    "improve": _slash_improve,
}


# The terminal grammar -----------------------------------------------------------


def _add_run_id(parser: Any) -> None:
    parser.add_argument("run_id", help="the run to act on")


def _add_target(parser: Any) -> None:
    parser.add_argument("target", help="a run identifier or a local proof path")


def _no_arguments(parser: Any) -> None:
    return None


def _terminal(services: Any, arguments: Sequence[str]) -> int:
    """Run Techtree's own human output against this terminal."""
    return int(services.bridge.invoke_human(list(arguments)))


def _cli_doctor(services: Any) -> Callable[[Any], int]:
    def run(namespace: Any) -> int:
        return _terminal(services, ["doctor"])

    return run


def _cli_status(services: Any) -> Callable[[Any], int]:
    def run(namespace: Any) -> int:
        return _terminal(services, ["run", "status", namespace.run_id])

    return run


def _cli_watch(services: Any) -> Callable[[Any], int]:
    def run(namespace: Any) -> int:
        return _terminal(services, ["run", "status", namespace.run_id, "--watch"])

    return run


def _cli_result(services: Any) -> Callable[[Any], int]:
    def run(namespace: Any) -> int:
        return _terminal(services, ["run", "result", namespace.run_id])

    return run


def _cli_verify(services: Any) -> Callable[[Any], int]:
    def run(namespace: Any) -> int:
        return _terminal(services, ["proof", "verify", namespace.target])

    return run


def _cli_demo(services: Any) -> Callable[[Any], int]:
    def run(namespace: Any) -> int:
        print(ensure_gateway_safe(_slash_demo(services, [])))
        return 0

    return run


def build_cli_commands(services: Any) -> Mapping[str, CliCommand]:
    """Return the terminal subcommands, bound to this session's services."""
    return {
        "doctor": CliCommand(
            help="check that this machine is ready to run a Climb",
            setup=_no_arguments,
            handler=_cli_doctor(services),
        ),
        "demo": CliCommand(
            help="prepare Techtree Hello World, the toy Skill-uplift Climb",
            setup=_no_arguments,
            handler=_cli_demo(services),
        ),
        "status": CliCommand(
            help="show how a run is progressing",
            setup=_add_run_id,
            handler=_cli_status(services),
        ),
        "watch": CliCommand(
            help="follow a run until it ends (terminal only)",
            setup=_add_run_id,
            handler=_cli_watch(services),
        ),
        "result": CliCommand(
            help="show the finished report for a run",
            setup=_add_run_id,
            handler=_cli_result(services),
        ),
        "verify": CliCommand(
            help="check a local proof offline",
            setup=_add_target,
            handler=_cli_verify(services),
        ),
    }


#: What `hermes techtree …` offers. The commands themselves are built per
#: session, because each one runs against that session's services.
CLI_COMMAND_NAMES: tuple[str, ...] = (
    "doctor",
    "demo",
    "status",
    "watch",
    "result",
    "verify",
)

#: Registered as `/techtree`: one command, one fixed grammar, any channel.
SLASH_COMMANDS: Mapping[str, str] = {
    SLASH_COMMAND: "Operate Techtree: setup, climbs, demo, status, result, verify"
}

#: The argument hint a gateway shows beside the command.
SLASH_ARGS_HINT = "<subcommand> [run-id]"


def slash_handler(services: Any) -> Callable[[str], str]:
    """Return the `/techtree` handler bound to this session's services."""

    def handle(raw_args: str) -> str:
        return handle_slash_command(raw_args, services)

    return handle


# Shared ---------------------------------------------------------------------------


def _tool(services: Any, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Call one tool and return everything it answered.

    The full answer is asked for on purpose. These commands read a handful of
    fields out of it and write their own sentences, and the sentences are what
    gets bounded — a summary built from an answer that was already cut would
    quietly describe half a result as if it were the whole one.
    """
    answer = TOOL_HANDLERS[name](
        services, {**args, "channel": ChannelKind.TERMINAL.value}
    )
    parsed = json.loads(answer)
    return parsed if isinstance(parsed, dict) else {}


def _run_argument(services: Any, arguments: Sequence[str]) -> str | None:
    if arguments:
        return arguments[0]
    session = latest_session(services)
    if session is not None:
        return session.second_run_id or session.first_run_id
    running = active_run_ids(services)
    return running[0] if running else None


def _error_line(answer: Mapping[str, Any]) -> str:
    error = answer.get("error")
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    return str(answer.get("message") or "Techtree could not answer that.")


def _release_line(answer: Mapping[str, Any]) -> str:
    release = answer.get("release") or {}
    return (
        f"Plugin {answer.get('plugin_version')}, release {release.get('release_id')}."
    )


def _next_action_line(answer: Mapping[str, Any]) -> str:
    action = answer.get("next_action")
    if not isinstance(action, dict):
        return ""
    return f"Next: {action.get('label')}"


def _usage(headline: str) -> str:
    lines = [headline]
    lines += [f"/techtree {name} — {purpose}" for name, purpose in SLASH_USAGE.items()]
    return "\n".join(lines)


__all__ = [
    "CLI_COMMAND_NAMES",
    "SLASH_COMMANDS",
    "CliCommand",
    "build_cli_commands",
    "handle_slash_command",
    "parse_slash_args",
    "register_cli_subcommands",
    "slash_handler",
]
