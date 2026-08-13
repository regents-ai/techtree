"""One-time draft confirmation tokens. Spec PR6 §6.6.

A confirmation token answers one question: is the thing about to be started the
exact thing that was prepared? It is bound to the digest of the complete draft,
which transitively covers the Campaign, the DataPolicy, both manifests, and the
snapshotted skill, so a token cannot be replayed against a draft that differs
in any respect.

It answers no other question. Possessing a token is not accepting a rights
policy — decisions document 0003 A5 keeps acceptance on the run request, where
it is recorded as a deliberate act with a method and a time. Anything that read
possession as consent would be manufacturing agreement from a handle.

Three rules protect the token itself:

* Only its SHA-256 digest is ever stored. A stolen state directory yields a
  hash, not a usable token.
* Comparison is constant-time. The failure a timing attack would recover is the
  one this module exists to make hard.
* Nothing here logs, formats, or embeds the raw token — not in an error
  message, not in error details, not in the record. It is returned exactly once
  by :meth:`ConfirmationService.issue` and is the caller's problem thereafter.

The clock is injected so that expiry can be tested without sleeping, and so a
caller that has already read the time can hand it in rather than sampling it
again mid-decision.
"""

from __future__ import annotations

import hmac
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Final

from techtree.canonical import sha256_digest_bytes, validate_digest
from techtree.constants import DEFAULT_CONFIRMATION_TTL_SECONDS
from techtree.errors import AuthenticationError, ValidationError
from techtree.models.base import Digest
from techtree.models.skill import ConfirmationRecord

__all__ = [
    "CONFIRMATION_TOKEN_BYTES",
    "ConfirmationService",
    "utc_now",
]

#: How much entropy a token carries, in bytes handed to
#: :func:`secrets.token_urlsafe`. Thirty-two bytes is 256 bits, which is the
#: same order as the digest it is compared through.
CONFIRMATION_TOKEN_BYTES: Final = 32

#: Stable error codes. A caller distinguishes "you gave me the wrong token"
#: from "that token has already been used" without parsing prose.
_TOKEN_INVALID: Final = "confirmation_token_invalid"
_TOKEN_WRONG_DRAFT: Final = "confirmation_token_wrong_draft"
_TOKEN_EXPIRED: Final = "confirmation_token_expired"
_TOKEN_CONSUMED: Final = "confirmation_token_consumed"
_RECORD_MALFORMED: Final = "confirmation_record_malformed"


def utc_now() -> datetime:
    """Return the current instant in UTC."""
    return datetime.now(UTC)


class ConfirmationService:
    """Issues, verifies, and consumes one-time draft confirmations."""

    def __init__(
        self,
        *,
        ttl_seconds: int = DEFAULT_CONFIRMATION_TTL_SECONDS,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValidationError(
                "a confirmation that expires immediately could never be used",
                details={"ttl_seconds": ttl_seconds},
            )
        self._ttl = timedelta(seconds=ttl_seconds)
        self._clock = clock

    @property
    def ttl_seconds(self) -> int:
        """Return how long an issued confirmation stays valid."""
        return int(self._ttl.total_seconds())

    def issue(self, draft_digest: Digest) -> tuple[str, ConfirmationRecord]:
        """Return the raw token once, and the record that will be persisted."""
        token = secrets.token_urlsafe(CONFIRMATION_TOKEN_BYTES)
        record = ConfirmationRecord(
            token_hash=self.token_digest(token),
            draft_digest=validate_digest(draft_digest),
            expires_at=self._clock() + self._ttl,
            consumed_at=None,
        )
        return token, record

    def verify(
        self,
        *,
        token: str,
        record: ConfirmationRecord,
        expected_draft_digest: Digest,
        now: datetime | None = None,
    ) -> None:
        """Raise unless this token confirms this draft, right now, first time.

        The digest is computed before any decision is taken, so every rejection
        path does the same work regardless of which check will fail.
        """
        offered = self.token_digest(token)
        moment = self._moment(now)

        if not _is_utc(record.expires_at) or (
            record.consumed_at is not None and not _is_utc(record.consumed_at)
        ):
            raise AuthenticationError(
                "the stored confirmation does not name an instant, so it cannot "
                "be checked for expiry",
                code=_RECORD_MALFORMED,
            )

        if not hmac.compare_digest(offered, record.token_hash):
            raise AuthenticationError(
                "that confirmation token does not match the prepared draft",
                code=_TOKEN_INVALID,
            )

        if not hmac.compare_digest(
            validate_digest(expected_draft_digest), record.draft_digest
        ):
            raise AuthenticationError(
                "that confirmation was issued for a different draft",
                code=_TOKEN_WRONG_DRAFT,
                details={"expected_draft_digest": expected_draft_digest},
            )

        if moment >= record.expires_at:
            raise AuthenticationError(
                "that confirmation has expired; prepare the draft again",
                code=_TOKEN_EXPIRED,
                details={"expired_at": record.expires_at.isoformat()},
            )

        if record.consumed_at is not None:
            raise AuthenticationError(
                "that confirmation has already been used; a draft starts once",
                code=_TOKEN_CONSUMED,
                details={"consumed_at": record.consumed_at.isoformat()},
            )

    def consume(
        self,
        record: ConfirmationRecord,
        *,
        now: datetime | None = None,
    ) -> ConfirmationRecord:
        """Return a copy marked used, refusing a record that already was."""
        if record.consumed_at is not None:
            raise AuthenticationError(
                "that confirmation has already been used; a draft starts once",
                code=_TOKEN_CONSUMED,
                details={"consumed_at": record.consumed_at.isoformat()},
            )
        return ConfirmationRecord(
            token_hash=record.token_hash,
            draft_digest=record.draft_digest,
            expires_at=record.expires_at,
            consumed_at=self._moment(now),
        )

    def token_digest(self, token: str) -> Digest:
        """Hash UTF-8 token bytes with SHA-256."""
        return sha256_digest_bytes(token.encode("utf-8"))

    def _moment(self, now: datetime | None) -> datetime:
        moment = self._clock() if now is None else now
        if not _is_utc(moment):
            raise ValidationError(
                "a confirmation is checked against an instant, and a naive "
                "datetime does not name one",
            )
        return moment.astimezone(UTC)


def _is_utc(moment: datetime) -> bool:
    return moment.tzinfo is not None and moment.tzinfo.utcoffset(moment) is not None
