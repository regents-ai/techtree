"""The machine-readable CLI surface. ``docs/v0.2/MACHINE_CONTRACT.md``.

The CLI is the stable boundary a host agent programs against, so its output has
a shape rather than a format. Every command returns one ``CliEnvelope``:
which operation answered, whether it succeeded, the durable state it observed,
what it found, what it could not determine, what is in the way, what must still
be seen, the bytes it points at, and — at most three — what could sensibly be
done next.

Four things in ``techtree.cli.v2`` are worth naming, because each of them
replaces something v1 could not say.

*The envelope keys on an operation rather than on a command path.* An
:class:`Operation` is a stable identifier from a closed inventory, so a handler
can be renamed, split, or given a new option without breaking a caller.

*A missing answer and an unanswerable one are different.* :class:`CliUnknown`
carries what could not be determined and why. A cost that could not be
established is an unknown; it is never a zero.

*There is no free-text message channel.* Anything a caller must act on is a
typed fact in ``facts``, a :class:`CliUnknown`, a :class:`CliBlocker`, or a
:class:`CliWarning`. Human sentences are built by the renderer from those, and
are not part of the machine contract.

*A next action says what invoking it would do.* :class:`NextAction` carries the
operation, the exact arguments, the state it was prepared against, what it
changes, what leaves the machine, what it may cost, whether a person must
approve it, and what to do when it does not clearly succeed. ``approval_required``
is not advisory: it is how an irreversible step stays irreversible-by-a-person
even when a machine is driving.

Nothing in this module knows about the filesystem, the catalog, or a run. It is
the vocabulary those layers speak in, which is also why
:mod:`techtree.errors` can project a typed error into a ``CliError`` without
either module depending on the other's behavior.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from techtree.models.approval import MonetaryAmount
from techtree.models.base import (
    Digest,
    JsonValue,
    NonEmptyString,
    ProtocolModel,
    UtcDateTime,
)

__all__ = [
    "MAX_NEXT_ACTIONS",
    "CheckStatus",
    "CliBlocker",
    "CliEnvelope",
    "CliError",
    "CliUnknown",
    "CliWarning",
    "ContentRef",
    "DataEgress",
    "DoctorCheck",
    "EstimatedCost",
    "NextAction",
    "Operation",
    "RetryClass",
    "SideEffect",
    "command_line",
    "invocation",
]

#: A host agent that is offered ten choices is being asked to plan, not to act.
#: Three is the documented ceiling.
MAX_NEXT_ACTIONS: Final = 3

#: RFC 6901: the empty string, or one or more ``/``-prefixed tokens, in which
#: ``~`` appears only as ``~0`` or ``~1``. An unknown's subject is resolved
#: against ``facts`` by whatever the caller uses, so a spelling no resolver
#: accepts is a pointer to nothing.
JSON_POINTER_PATTERN: Final = r"^$|^(/([^~]|~[01])*)+$"

type JsonPointer = Annotated[str, StringConstraints(pattern=JSON_POINTER_PATTERN)]


class Operation(StrEnum):
    """The fourteen stable identifiers the v2 machine surface answers under.

    They *describe existing handlers* rather than create a second command
    hierarchy: ``docs/v0.2/MACHINE_CONTRACT.md`` says which handler each one
    names, and ``tests/contract/test_v02_machine_contract.py`` holds the
    document to the code in both directions.
    """

    PLAN_INSPECT = "plan.inspect"
    PLAN_PREPARE = "plan.prepare"
    ACTION_PREPARE = "action.prepare"
    ACTION_EXECUTE = "action.execute"
    RUN_STATUS = "run.status"
    RUN_WAIT = "run.wait"
    RUN_RECONCILE = "run.reconcile"
    RUN_CANCEL = "run.cancel"
    RESULT_INSPECT = "result.inspect"
    CLAIM_INSPECT = "claim.inspect"
    PROOF_VERIFY = "proof.verify"
    PROFILE_GET = "profile.get"
    PROFILE_SYNC = "profile.sync"
    PROFILE_UPDATE = "profile.update"


class RetryClass(StrEnum):
    """What to do when an action does not clearly succeed.

    Five answers where v1's ``retryable`` boolean had two. ``reconcile_first``
    is the one that matters most: an ambiguous paid submission may already have
    been accepted, so durable state is read before anything is decided.
    """

    SAFE = "safe"
    SAFE_AFTER_DELAY = "safe_after_delay"
    RECONCILE_FIRST = "reconcile_first"
    HUMAN_DECISION_REQUIRED = "human_decision_required"
    FORBIDDEN = "forbidden"


class SideEffect(StrEnum):
    """What invoking an action changes."""

    NONE = "none"
    LOCAL_STATE = "local_state"
    LOCAL_EXECUTION = "local_execution"
    PAID_REMOTE_EXECUTION = "paid_remote_execution"
    PUBLIC_PUBLICATION = "public_publication"


class DataEgress(StrEnum):
    """What leaves this machine when an action runs."""

    NONE = "none"
    PACKAGE_INDEX = "package_index"
    MODEL_PROVIDER = "model_provider"
    EXECUTION_PROVIDER = "execution_provider"
    PUBLICATION_SERVICE = "publication_service"


class CliUnknown(ProtocolModel):
    """One thing this operation could not determine, named.

    ``subject`` is a JSON Pointer into ``facts`` when the unknown is about a
    field the payload has, and null when it is about something the payload has
    no place for. It is a pointer rather than a field name so that it can reach
    into a nested payload, and it is validated as one: a caller that resolves
    it against ``facts`` must not be handed a string that no resolver accepts.
    """

    id: NonEmptyString
    subject: JsonPointer | None
    reason: NonEmptyString
    resolvable_by: Operation | None


class CliBlocker(ProtocolModel):
    """One thing that stops this operation, or the step the caller wanted next."""

    id: NonEmptyString
    text: NonEmptyString
    blocks: list[Operation]
    resolvable_by: Operation | None

    @model_validator(mode="after")
    def _check_a_blocker_blocks_something(self) -> Self:
        """A blocker that forbids nothing is a warning wearing the wrong name."""
        if not self.blocks:
            raise ValueError(
                "a blocker names the operations it forbids; one that forbids "
                "nothing is a warning"
            )
        if len(set(self.blocks)) != len(self.blocks):
            raise ValueError("a blocker names each operation it forbids once")
        return self


class CliWarning(ProtocolModel):
    """Something that did not stop the operation and must still be seen."""

    id: NonEmptyString
    text: NonEmptyString
    resolvable_by: Operation | None


class ContentRef(ProtocolModel):
    """Bytes the envelope names rather than carries.

    An envelope is a message, not a container, so a proof bundle, a worker log,
    or an export is pointed at. An entry offers at least one of ``path`` and
    ``url``, because a reference nothing can be fetched by is not a reference.
    """

    id: NonEmptyString
    kind: NonEmptyString
    digest: Digest | None
    path: NonEmptyString | None
    url: NonEmptyString | None
    media_type: NonEmptyString
    byte_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check_the_bytes_can_be_reached(self) -> Self:
        if self.path is None and self.url is None:
            raise ValueError("a content reference offers a path, a URL, or both")
        return self


class EstimatedCost(ProtocolModel):
    """What an action may cost, and the ceiling it is authorized against.

    The non-secret money statement, and only that. It never carries an account
    identifier: the billing-principal label of a
    :class:`~techtree.models.approval.RemoteExecutionEstimate` is a private
    label and stays private, so it has no field here.

    ``estimated_cost`` is null when nothing quoted one, which is a different
    answer from zero. ``execution_plan_digest`` is null for a statement that is
    not bound to a resolved plan — a Campaign's own declared maximum is a
    property of the Campaign rather than of one hosted execution.
    """

    currency: Literal["USD"]
    estimated_cost: MonetaryAmount | None
    maximum_authorized_cost: MonetaryAmount
    estimate_source: NonEmptyString
    uncertainty_disclosure: NonEmptyString
    expires_at: UtcDateTime | None
    execution_plan_digest: Digest | None


class NextAction(ProtocolModel):
    """A typed next step, addressed to a host agent or to a person through one.

    ``prepared_arguments`` is a named object rather than v1's argv array,
    because a name cannot be mis-quoted into a second command. It has exactly
    three entries — ``command``, the command path as literal segments;
    ``arguments``, the positional values in order; and ``options``, each option
    by its own name — which is what lets a caller build the invocation, or
    render it for a person to read, without parsing anything. Techtree never
    executes a displayed command string.

    ``expected_state_digest`` binds the action to the state it was prepared
    against. When it no longer equals the current ``state_digest`` the world
    moved, and the action must not be replayed on the new one.
    """

    operation: Operation
    #: One invocation, named. The published schema carries the shape as well as
    #: the type, so a consumer written from the schema alone builds the same
    #: call the validator below insists on.
    prepared_arguments: dict[str, JsonValue] = Field(
        json_schema_extra={
            "type": "object",
            "required": ["command", "arguments", "options"],
            "additionalProperties": False,
            "properties": {
                "command": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                },
                "arguments": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                },
                "options": {
                    "type": "object",
                    "propertyNames": {"pattern": "^--"},
                    "additionalProperties": {
                        "anyOf": [
                            {"type": "string", "minLength": 1},
                            {"const": True},
                        ]
                    },
                },
            },
        }
    )
    expected_state_digest: Digest | None
    side_effect: SideEffect
    approval_required: bool
    retry_class: RetryClass
    estimated_cost: EstimatedCost | None
    data_egress: DataEgress
    reason: NonEmptyString

    @model_validator(mode="after")
    def _check_the_action_can_be_invoked(self) -> Self:
        """Reject an action a caller could not turn into an invocation."""
        prepared = self.prepared_arguments
        if set(prepared) != {"command", "arguments", "options"}:
            raise ValueError(
                "prepared_arguments names one invocation with exactly "
                "'command', 'arguments', and 'options'"
            )
        command = prepared["command"]
        if not isinstance(command, list) or not command:
            raise ValueError("'command' is the command path, at least one segment")
        arguments = prepared["arguments"]
        if not isinstance(arguments, list):
            raise ValueError("'arguments' is the positional values, in order")
        for literal in (*command, *arguments):
            if not isinstance(literal, str) or not literal.strip():
                raise ValueError("a command segment or argument is a literal string")
        options = prepared["options"]
        if not isinstance(options, dict):
            raise ValueError("'options' names each option by its own name")
        for name, value in options.items():
            if not name.startswith("--"):
                raise ValueError(f"an option is named as it is spelled: {name!r}")
            # ``false`` is refused rather than read as "leave the flag out": a
            # flag that is present is spelled, and one that is absent is not
            # named at all. Accepting ``false`` would let a ``--yes`` that
            # says no render as a ``--yes`` that says yes.
            if value is True or (isinstance(value, str) and value != ""):
                continue
            raise ValueError("an option carries its value, or true where it takes none")
        return self


def invocation(
    *command: str,
    arguments: Sequence[str] = (),
    options: Mapping[str, str | Literal[True]] | None = None,
) -> dict[str, JsonValue]:
    """Return the ``prepared_arguments`` of one invocation.

    Written once so that every next action in the CLI names an invocation the
    same way, and so that a caller building a command line from one never has
    to guess where a value belongs.
    """
    return {
        "command": list(command),
        "arguments": list(arguments),
        "options": dict(options or {}),
    }


def command_line(action: NextAction) -> list[str]:
    """Return one next action as the argv a caller would run.

    Display and invocation are the same list, which is the point: a person
    reading the line and a host agent running it are looking at one thing.
    """
    prepared = action.prepared_arguments
    command = [str(segment) for segment in _sequence(prepared["command"])]
    arguments = [str(value) for value in _sequence(prepared["arguments"])]
    options: list[str] = []
    for name, value in _mapping(prepared["options"]).items():
        options.append(name)
        if value is not True:
            options.append(str(value))
    return ["techtree", *command, *arguments, *options]


def _sequence(value: JsonValue) -> list[JsonValue]:
    assert isinstance(value, list)
    return value


def _mapping(value: JsonValue) -> dict[str, JsonValue]:
    assert isinstance(value, dict)
    return value


class CliError(ProtocolModel):
    """The machine-safe projection of a failure.

    There is no ``retryable`` boolean. Whether and how to retry is stated by
    the ``retry_class`` of the repair action the failed envelope carries, which
    can say five things where a boolean said two.
    """

    code: NonEmptyString
    message: NonEmptyString
    details: dict[str, JsonValue]


class CliEnvelope[T](ProtocolModel):
    """The single response shape every command returns.

    ``facts`` is command-specific, which is why the type is a parameter. The
    published schema describes the envelope; each operation documents its own
    payload.
    """

    schema_version: Literal["techtree.cli.v2"]
    operation: Operation
    ok: bool
    state_digest: Digest | None
    #: Always an object. A caller reads one shape whatever it asked, and a
    #: payload that answers with a bare array cannot gain a second fact later
    #: without changing shape underneath everyone; the published schema says
    #: so, and the validator below holds the code to it.
    facts: T = Field(json_schema_extra={"type": "object"})
    unknowns: list[CliUnknown]
    blockers: list[CliBlocker]
    warnings: list[CliWarning]
    content_refs: list[ContentRef]
    next_actions: list[NextAction] = Field(max_length=MAX_NEXT_ACTIONS)
    error: CliError | None

    @model_validator(mode="after")
    def _check_success_and_failure_are_distinguishable(self) -> Self:
        """Reject an envelope that reports success and failure at once."""
        if self.ok and self.error is not None:
            raise ValueError("a successful command reports no error")
        if not self.ok and self.error is None:
            raise ValueError("a failed command must say why it failed")
        if not isinstance(self.facts, BaseModel | dict):
            raise ValueError(
                "facts is an object: a list or a scalar answer would be a "
                "second envelope shape for a caller to handle"
            )
        offered = [
            (
                action.operation,
                json.dumps(action.prepared_arguments, sort_keys=True),
            )
            for action in self.next_actions
        ]
        if len(set(offered)) != len(offered):
            raise ValueError(
                "next actions must be distinct: one operation with one set of "
                "prepared arguments is one step, offered once"
            )
        return self


class CheckStatus(StrEnum):
    """The outcome of one Doctor check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


class DoctorCheck(ProtocolModel):
    """One environment check and what it found."""

    id: NonEmptyString
    label: NonEmptyString
    status: CheckStatus
    detail: NonEmptyString
    blocking: bool
    metadata: dict[str, JsonValue]

    @model_validator(mode="after")
    def _check_blocking_implies_failure(self) -> Self:
        """Reject a blocking check that reports nothing wrong."""
        if self.blocking and self.status in (CheckStatus.PASS, CheckStatus.SKIP):
            raise ValueError(
                "a check that passed or was skipped cannot block; blocking is "
                "what a failure means, not a separate opinion about it"
            )
        return self
