"""One-time draft confirmations. Spec PR6 §6.6 and §6.11.

A confirmation is a small thing that has to be exactly right, so these tests
are written around the four ways it could be wrong: the wrong token is
accepted, the right token works on the wrong draft, an old token still works,
or a used token works twice.

Two properties are checked repeatedly rather than once, because they are the
ones a later refactor is most likely to break quietly: the raw token never
appears in the stored record or in any error a caller can see, and every
rejection is a typed failure with its own code rather than a boolean.

Time is injected. Nothing here sleeps, and expiry is tested at the boundary
instant rather than near it.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from techtree.constants import DEFAULT_CONFIRMATION_TTL_SECONDS
from techtree.drafts.confirmation import ConfirmationService, utc_now
from techtree.errors import AuthenticationError, ValidationError
from techtree.models.skill import ConfirmationRecord

DRAFT_DIGEST = f"sha256:{'1' * 64}"
OTHER_DIGEST = f"sha256:{'2' * 64}"
START = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class FrozenClock:
    """A clock a test moves by hand."""

    def __init__(self, now: datetime = START) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock()


@pytest.fixture
def service(clock: FrozenClock) -> ConfirmationService:
    return ConfirmationService(clock=clock)


# ---------------------------------------------------------------------------
# Issuing
# ---------------------------------------------------------------------------


def test_a_token_is_thirty_two_bytes_of_url_safe_randomness(
    service: ConfirmationService,
) -> None:
    first, _ = service.issue(DRAFT_DIGEST)
    second, _ = service.issue(DRAFT_DIGEST)

    assert first != second
    assert set(first) <= set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )
    padded = first + "=" * (-len(first) % 4)
    assert len(base64.urlsafe_b64decode(padded)) == 32


def test_the_record_holds_only_the_hash_of_the_token(
    service: ConfirmationService,
) -> None:
    token, record = service.issue(DRAFT_DIGEST)

    expected = f"sha256:{hashlib.sha256(token.encode('utf-8')).hexdigest()}"
    assert record.token_hash == expected
    assert token not in record.model_dump_json()
    assert record.consumed_at is None


def test_the_record_expires_fifteen_minutes_from_now_by_default(
    clock: FrozenClock, service: ConfirmationService
) -> None:
    _, record = service.issue(DRAFT_DIGEST)

    assert DEFAULT_CONFIRMATION_TTL_SECONDS == 900
    assert record.expires_at == clock.now + timedelta(
        seconds=DEFAULT_CONFIRMATION_TTL_SECONDS
    )
    assert service.ttl_seconds == DEFAULT_CONFIRMATION_TTL_SECONDS


def test_the_record_is_bound_to_the_draft_it_was_issued_for(
    service: ConfirmationService,
) -> None:
    _, record = service.issue(DRAFT_DIGEST)

    assert record.draft_digest == DRAFT_DIGEST


def test_a_service_that_expires_immediately_is_refused() -> None:
    with pytest.raises(ValidationError):
        ConfirmationService(ttl_seconds=0)


def test_the_token_digest_is_sha256_of_the_utf8_bytes(
    service: ConfirmationService,
) -> None:
    digest = service.token_digest("héllo")

    assert digest == f"sha256:{hashlib.sha256('héllo'.encode()).hexdigest()}"


# ---------------------------------------------------------------------------
# Verifying
# ---------------------------------------------------------------------------


def test_the_right_token_on_the_right_draft_verifies(
    service: ConfirmationService,
) -> None:
    token, record = service.issue(DRAFT_DIGEST)

    service.verify(token=token, record=record, expected_draft_digest=DRAFT_DIGEST)


def test_a_wrong_token_is_refused(service: ConfirmationService) -> None:
    _, record = service.issue(DRAFT_DIGEST)

    with pytest.raises(AuthenticationError) as caught:
        service.verify(
            token="not-the-token",
            record=record,
            expected_draft_digest=DRAFT_DIGEST,
        )

    assert caught.value.code == "confirmation_token_invalid"


def test_a_token_from_another_draft_is_refused(
    service: ConfirmationService,
) -> None:
    """A record and a token can both be genuine and still not belong together."""
    token, record = service.issue(DRAFT_DIGEST)

    with pytest.raises(AuthenticationError) as caught:
        service.verify(token=token, record=record, expected_draft_digest=OTHER_DIGEST)

    assert caught.value.code == "confirmation_token_wrong_draft"


def test_an_expired_token_is_refused(
    clock: FrozenClock, service: ConfirmationService
) -> None:
    token, record = service.issue(DRAFT_DIGEST)

    clock.advance(DEFAULT_CONFIRMATION_TTL_SECONDS - 1)
    service.verify(token=token, record=record, expected_draft_digest=DRAFT_DIGEST)

    clock.advance(1)
    with pytest.raises(AuthenticationError) as caught:
        service.verify(token=token, record=record, expected_draft_digest=DRAFT_DIGEST)

    assert caught.value.code == "confirmation_token_expired"


def test_a_consumed_token_is_refused(service: ConfirmationService) -> None:
    token, record = service.issue(DRAFT_DIGEST)
    consumed = service.consume(record)

    with pytest.raises(AuthenticationError) as caught:
        service.verify(token=token, record=consumed, expected_draft_digest=DRAFT_DIGEST)

    assert caught.value.code == "confirmation_token_consumed"


def test_a_record_with_a_naive_expiry_is_refused(
    service: ConfirmationService,
) -> None:
    token, record = service.issue(DRAFT_DIGEST)
    malformed = record.model_copy(update={"expires_at": datetime(2026, 1, 1, 12, 30)})

    with pytest.raises(AuthenticationError) as caught:
        service.verify(
            token=token, record=malformed, expected_draft_digest=DRAFT_DIGEST
        )

    assert caught.value.code == "confirmation_record_malformed"


def test_a_naive_instant_cannot_be_checked_against(
    service: ConfirmationService,
) -> None:
    token, record = service.issue(DRAFT_DIGEST)

    with pytest.raises(ValidationError):
        service.verify(
            token=token,
            record=record,
            expected_draft_digest=DRAFT_DIGEST,
            now=datetime(2026, 1, 1, 12, 1),
        )


def test_no_rejection_ever_repeats_the_token(service: ConfirmationService) -> None:
    token, record = service.issue(DRAFT_DIGEST)
    consumed = service.consume(record)

    for expected, offered in (
        (DRAFT_DIGEST, "wrong"),
        (OTHER_DIGEST, token),
    ):
        with pytest.raises(AuthenticationError) as caught:
            service.verify(token=offered, record=record, expected_draft_digest=expected)
        assert token not in f"{caught.value.message}{caught.value.details}"

    with pytest.raises(AuthenticationError) as caught:
        service.verify(token=token, record=consumed, expected_draft_digest=DRAFT_DIGEST)
    assert token not in f"{caught.value.message}{caught.value.details}"


# ---------------------------------------------------------------------------
# Consuming
# ---------------------------------------------------------------------------


def test_consuming_returns_a_copy_and_leaves_the_original_alone(
    clock: FrozenClock, service: ConfirmationService
) -> None:
    _, record = service.issue(DRAFT_DIGEST)

    consumed = service.consume(record)

    assert consumed is not record
    assert record.consumed_at is None
    assert consumed.consumed_at == clock.now
    assert consumed.token_hash == record.token_hash
    assert consumed.draft_digest == record.draft_digest
    assert consumed.expires_at == record.expires_at


def test_consuming_twice_is_refused(service: ConfirmationService) -> None:
    _, record = service.issue(DRAFT_DIGEST)
    consumed = service.consume(record)

    with pytest.raises(AuthenticationError) as caught:
        service.consume(consumed)

    assert caught.value.code == "confirmation_token_consumed"


def test_a_caller_may_supply_the_instant_it_already_read(
    service: ConfirmationService,
) -> None:
    _, record = service.issue(DRAFT_DIGEST)
    moment = START + timedelta(seconds=42)

    assert service.consume(record, now=moment).consumed_at == moment


def test_the_default_clock_is_utc() -> None:
    now = utc_now()

    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_a_record_loaded_from_disk_verifies_the_same_way(
    service: ConfirmationService,
) -> None:
    """The stored form is all a later process has, and it has to be enough."""
    token, record = service.issue(DRAFT_DIGEST)

    reloaded = ConfirmationRecord.model_validate_json(record.model_dump_json())

    service.verify(token=token, record=reloaded, expected_draft_digest=DRAFT_DIGEST)
