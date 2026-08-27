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

That surface is one command deep on purpose. The host turns every name a
plugin registers into ``hermes <name>``, so this plugin registers the single
name ``techtree`` and hangs its verbs off that. A verb registered on its own
would be a bare ``hermes doctor`` or ``hermes watch`` — the first four of ours
shadowed by Hermes's own commands of those names, the rest a top-level word
taken from everyone else who might want it.

The grammar is fixed. A subcommand is looked up in a table, its arguments are
checked, and anything else is refused with the list of what does exist. There
is no passthrough: nothing a user or a model types becomes part of a command.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, NamedTuple, TypeGuard

from .channels import ensure_gateway_safe
from .errors import PluginError
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
    """One verb beneath ``hermes techtree``."""

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
        text = f"That did not work: {error}"
    except Exception as error:  # a defect must not break the session
        text = f"That did not work: {error}"
    # Sanitised, not shortened. Stripping what a display would obey is a
    # safety control; cutting the answer at a guessed length was not, and is
    # gone.
    return ensure_gateway_safe(text)


def register_cli_subcommands(ctx: Any, services: Any) -> None:
    """Register the one ``techtree`` terminal command and its verbs.

    The host turns each registered name into ``hermes <name>``, so exactly one
    name is registered — our own — and every verb lives beneath it. Registering
    the verbs themselves would put ``doctor``, ``demo``, ``status`` and
    ``verify`` up against Hermes's own commands of those names, and would claim
    ``watch`` and ``result`` as top-level words that are not ours to take.
    """
    command = build_cli_command(services)
    ctx.register_cli_command(
        name=CLI_COMMAND,
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
    answer = _tool(services, "techtree_climb_list", {})
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


#: What a cost figure's provenance means to a reader, in the words Techtree's
#: own renderings use. The plugin cannot import Techtree — it reads a finished
#: payload out of another process — so the phrase is looked up here and never
#: reworded, and a figure is never shown with a basis this build cannot name.
_COST_BASIS: Mapping[str, str] = {
    "provider_reported": "reported by the provider",
    "computed_from_pinned_price": "computed from the pinned price",
    "estimated": "estimated, not billed",
}

#: What is said of a figure whose provenance this build has no phrase for. A
#: number with no stated basis is the one thing decision 0007 R6 forbids, so
#: the absence is stated rather than the figure being shown bare.
_COST_BASIS_UNNAMED = "and this build has no name for where that figure came from"


def _number(value: Any, spec: str) -> str | None:
    """Return one figure from the payload as text, or nothing when it has none.

    Formatting is all that happens here. Every figure the relay shows was
    computed by Techtree and is copied out of its payload; this build works
    out no number of its own and rounds none into a better one.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return format(value, spec)


def _measured_difference_line(presentation: Mapping[str, Any]) -> str:
    """Return the measured difference, counted first wherever it can be.

    A mean is what the report holds and a count is what a person reads a
    result in, and for an all-or-nothing reward the two are the same fact.
    Techtree's own renderings lead with the count for exactly that reason, and
    this is the line most likely to be quoted to somebody, so it leads with the
    same one and keeps the mean in the same breath. A reward with no such count
    has none invented for it.
    """
    baseline = _number(presentation.get("baseline_score"), ".3f")
    candidate = _number(presentation.get("candidate_score"), ".3f")
    delta = _number(presentation.get("absolute_delta"), "+.3f")
    if baseline is None or candidate is None:
        means = "unavailable"
    else:
        means = f"{baseline} → {candidate}"
        if delta is not None:
            means = f"{means} ({delta})"
    counted = _task_counts(presentation)
    if counted is None:
        return f"Mean score {means}"
    scored_baseline, scored_candidate, total = counted
    return (
        f"Tasks {scored_baseline} of {total} → {scored_candidate} of {total}, "
        f"mean {means}"
    )


def _task_counts(presentation: Mapping[str, Any]) -> tuple[int, int, int] | None:
    """Return both sides' fully scored task counts and the size of the set."""
    baseline = presentation.get("baseline_tasks_scored_full")
    candidate = presentation.get("candidate_tasks_scored_full")
    rows = presentation.get("task_rows")
    if not _is_count(baseline) or not _is_count(candidate):
        return None
    if not isinstance(rows, Sequence) or isinstance(rows, str):
        return None
    return baseline, candidate, len(rows)


def _is_count(value: Any) -> TypeGuard[int]:
    """Whether the payload carried a whole count here rather than nothing."""
    return isinstance(value, int) and not isinstance(value, bool)


def _cost_line(presentation: Mapping[str, Any]) -> str:
    """Return what the run cost and, in the same breath, what kind of figure it is.

    Decision 0007 R6: a figure that was worked out and a figure that was billed
    are different claims, and the word telling them apart travels with the
    number rather than somewhere below it.
    """
    reported = _number(presentation.get("cost_usd"), ".2f")
    if reported is not None:
        basis = _COST_BASIS.get(
            str(presentation.get("cost_provenance")), _COST_BASIS_UNNAMED
        )
        return f"${reported}, {basis}"
    derived = presentation.get("derived_cost")
    if isinstance(derived, Mapping):
        figure = _number(derived.get("usd"), ".2f")
        if figure is not None:
            return f"about ${figure}, worked out here, not billed"
    return "unavailable"


def _cost_basis_lines(presentation: Mapping[str, Any]) -> list[str]:
    """Return what a reader needs in order to judge the figure above it."""
    if presentation.get("cost_usd") is not None:
        return []
    derived = presentation.get("derived_cost")
    if not isinstance(derived, Mapping):
        reason = presentation.get("cost_unavailable_reason")
        return [reason] if isinstance(reason, str) and reason else []
    lines = []
    tokens_in = _number(derived.get("input_tokens"), ",")
    tokens_out = _number(derived.get("output_tokens"), ",")
    if tokens_in is not None and tokens_out is not None:
        lines.append(
            f"Computed from {tokens_in} input and {tokens_out} output tokens "
            "at the prices this release recorded. Your provider's bill is what "
            "you actually pay."
        )
    cached = _number(derived.get("cached_input_tokens"), ",")
    if cached is not None and not derived.get("prices_name_a_cached_rate"):
        lines.append(
            f"{cached} of those input tokens came back from the provider's "
            "cache. The recorded prices name no separate rate for those, so "
            "every token is priced at the full rate and the figure above is "
            "on the high side."
        )
    return lines


def _work_line(presentation: Mapping[str, Any]) -> str:
    """Return what each side spent doing the same tasks, in one line.

    How many times each side had to go back to the model is the half of this
    that a different machine would reproduce, so it is said first and the
    clock is said with it rather than on its own.
    """
    baseline = _number(presentation.get("baseline_model_turns"), ",")
    candidate = _number(presentation.get("candidate_model_turns"), ",")
    baseline_seconds = _number(presentation.get("baseline_seconds"), ".1f")
    candidate_seconds = _number(presentation.get("candidate_seconds"), ".1f")
    if baseline is None or candidate is None:
        if baseline_seconds is None and candidate_seconds is None:
            return "Time: not recorded for this run"
        return (
            f"Time: baseline {_seconds(baseline_seconds)}, "
            f"candidate {_seconds(candidate_seconds)}"
        )
    sentence = (
        f"Work: the candidate side took {candidate} model turns against the "
        f"baseline's {baseline}"
    )
    if baseline_seconds is not None and candidate_seconds is not None:
        sentence += (
            f", and finished in {candidate_seconds}s against {baseline_seconds}s"
        )
    return (
        f"{sentence}. Turns are a property of the work. How long each side "
        "took also depends on this machine and on how busy the provider was."
    )


def _seconds(value: str | None) -> str:
    """Return one side's elapsed time, or the word for an absent one."""
    return "unavailable" if value is None else f"{value}s"


def _qualification_lines(presentation: Mapping[str, Any]) -> list[str]:
    """Return every qualification Techtree attached to this result.

    Room is made by cutting detail, never by cutting one of these. A result
    that says only what went well, in the channel it is most likely to be
    forwarded from, would be dishonest in exactly the place it matters most.
    """
    caveats = presentation.get("caveats")
    if not isinstance(caveats, Sequence) or isinstance(caveats, str):
        return []
    return [
        caveat["text"]
        for caveat in caveats
        if isinstance(caveat, Mapping)
        and isinstance(caveat.get("text"), str)
        and caveat.get("severity") != "info"
    ]


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
            _measured_difference_line(presentation),
            f"Won {presentation.get('wins')}, lost {presentation.get('losses')}, "
            f"tied {presentation.get('ties')}",
            f"Decision: {presentation.get('decision')}",
            f"Proof grade: {presentation.get('proof_grade')}",
            f"Cost: {_cost_line(presentation)}",
            *_cost_basis_lines(presentation),
            _work_line(presentation),
            *_qualification_lines(presentation),
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


def build_cli_verbs(services: Any) -> Mapping[str, CliCommand]:
    """Return the verbs of `hermes techtree`, bound to this session's services."""
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


def build_cli_command(services: Any) -> CliCommand:
    """Return the single `techtree` terminal command for this session.

    Its setup hangs every verb off the parser the host hands us, and its
    handler is what runs when a person types `hermes techtree` and stops: the
    same help the parser would print for `--help`, and nothing else.
    """

    def setup(parser: Any) -> None:
        # Kept so the handler can print the help of the parser it belongs to.
        parser.set_defaults(techtree_parser=parser)
        verbs = parser.add_subparsers(dest="techtree_verb", metavar="<verb>")
        for name, verb in build_cli_verbs(services).items():
            subparser = verbs.add_parser(name, help=verb.help, description=verb.help)
            verb.setup(subparser)
            subparser.set_defaults(func=verb.handler)

    def handler(namespace: Any) -> int:
        namespace.techtree_parser.print_help()
        return 0

    return CliCommand(help=CLI_COMMAND_HELP, setup=setup, handler=handler)


#: The one name registered with the host, which it turns into `hermes techtree`.
CLI_COMMAND = "techtree"

#: What the host shows beside `techtree` in `hermes --help`.
CLI_COMMAND_HELP = "Operate Techtree from the terminal"

#: The verbs beneath it. The verbs themselves are built per session, because
#: each one runs against that session's services.
CLI_VERB_NAMES: tuple[str, ...] = (
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
    "CLI_COMMAND",
    "CLI_COMMAND_HELP",
    "CLI_VERB_NAMES",
    "SLASH_COMMANDS",
    "CliCommand",
    "build_cli_command",
    "build_cli_verbs",
    "handle_slash_command",
    "parse_slash_args",
    "register_cli_subcommands",
    "slash_handler",
]
