"""The machine-readable CLI surface. Spec section 11.14.

The CLI is the stable boundary a host agent programs against, so its output has
a shape rather than a format. Every command returns one ``CliEnvelope``:
succeeded or not, what it produced, what it wants to say, and — at most three —
what could sensibly be done next.

``NextAction`` is the part that makes the boundary usable by something that is
not a person. An action carries an argv list, or a named host-agent tool with
arguments, and says whether a human must confirm it first. That last flag is
not advisory: it is how an irreversible step stays irreversible-by-a-person
even when a machine is driving.

Nothing in this module knows about the filesystem, the catalog, or a run. It is
the vocabulary those layers speak in, which is also why
:mod:`techtree.errors` can project a typed error into a ``CliError`` without
either module depending on the other's behavior.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal, Self

from pydantic import Field, model_validator

from techtree.models.base import JsonValue, NonEmptyString, ProtocolModel

__all__ = [
    "MAX_NEXT_ACTIONS",
    "CheckStatus",
    "CliEnvelope",
    "CliError",
    "CliMessage",
    "DoctorCheck",
    "MessageLevel",
    "NextAction",
]

#: A host agent that is offered ten choices is being asked to plan, not to act.
#: Three is the documented ceiling.
MAX_NEXT_ACTIONS: Final = 3


class MessageLevel(StrEnum):
    """How much attention a message deserves."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class CliMessage(ProtocolModel):
    """One thing the CLI has to say."""

    level: MessageLevel
    code: NonEmptyString | None
    text: NonEmptyString


class NextAction(ProtocolModel):
    """A concrete next step, addressed to a person or to a host agent."""

    id: NonEmptyString
    label: NonEmptyString
    reason: NonEmptyString | None
    cli: list[NonEmptyString] | None
    hermes_tool: NonEmptyString | None
    hermes_args: dict[str, JsonValue] | None
    requires_user_confirmation: bool

    @model_validator(mode="after")
    def _check_action_is_actionable(self) -> Self:
        """Reject an action nothing could carry out."""
        if self.cli is None and self.hermes_tool is None:
            raise ValueError(
                "a next action must offer a CLI argv list, a host-agent tool, or both"
            )
        if self.cli is not None and not self.cli:
            raise ValueError("a CLI next action needs at least the command name")
        if self.hermes_args is not None and self.hermes_tool is None:
            raise ValueError("hermes_args without hermes_tool has nothing to call")
        return self


class CliError(ProtocolModel):
    """The machine-safe projection of a failure."""

    code: NonEmptyString
    message: NonEmptyString
    retryable: bool
    details: dict[str, JsonValue]


class CliEnvelope[T](ProtocolModel):
    """The single response shape every command returns.

    ``data`` is command-specific, which is why the type is a parameter. The
    published schema describes the envelope; each command documents its own
    payload.
    """

    schema_version: Literal["techtree.cli.v1"]
    ok: bool
    command: NonEmptyString
    data: T | None
    messages: list[CliMessage]
    warnings: list[CliMessage]
    next_actions: list[NextAction] = Field(max_length=MAX_NEXT_ACTIONS)
    error: CliError | None

    @model_validator(mode="after")
    def _check_success_and_failure_are_distinguishable(self) -> Self:
        """Reject an envelope that reports success and failure at once."""
        if self.ok and self.error is not None:
            raise ValueError("a successful command reports no error")
        if not self.ok and self.error is None:
            raise ValueError("a failed command must say why it failed")
        if len({action.id for action in self.next_actions}) != len(self.next_actions):
            raise ValueError("next actions must have distinct identifiers")
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
