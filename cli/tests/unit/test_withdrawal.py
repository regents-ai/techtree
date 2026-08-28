"""Withdrawing a published entry. Decisions document 0038.

The founder chose to implement withdrawal rather than to promise it, so what is
held here is the whole of what this side of it owes: a canonical request, signed
by the key that signed the run, sent to the one write address, and an answer
that is refused unless the pinned network key countersigned it.

The exact shape of the request is pinned as a set of members rather than
described, because the receiving side is being built against it in parallel and
a shape agreed in prose is how the two halves disagreed in the first place.
"""

from __future__ import annotations

import json
from base64 import b64decode
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from typer.testing import CliRunner

from fixtures.publication import (
    COORDINATES,
    ENDPOINT,
    ENDPOINT_VARIABLE,
    ENTRY_URL,
    PINNED_ENDPOINT,
    StubTransport,
    network_signed,
    withdrawal_receipt_for,
)
from techtree.canonical import canonical_json_bytes, digest_object
from techtree.cli.app import create_app
from techtree.cli.commands import withdraw as withdraw_module
from techtree.cli.commands.withdraw import (
    WITHDRAWAL_CONFIRMATION_REQUIRED,
    build_withdrawal_service,
)
from techtree.cli.context import build_cli_context
from techtree.crypto import (
    load_private_key,
    load_public_key,
    sign_digest,
    verify_signature,
)
from techtree.errors import EXIT_OK, EXIT_USAGE, ValidationError
from techtree.identity.service import IdentityService
from techtree.identity.store import IdentityStore
from techtree.models.base import ObjectEnvelope
from techtree.paths import paths_from_root
from techtree.publication.coordinates import packaged_publication_coordinates
from techtree.publication.models import (
    WithdrawalReceiptPayload,
    WithdrawalRequest,
)
from techtree.publication.verify import PUBLICATION_RECEIPT_INVALID
from techtree.publication.withdraw import WithdrawalService

BUNDLE_DIGEST = "sha256:" + "7" * 64
REQUESTED_AT = datetime(2026, 8, 28, 8, 0, tzinfo=UTC)

#: Decisions 0038: the withdrawal request document, member for member. A fourth
#: member — a reason, above all — is caught here rather than by a run log
#: refusing somebody's withdrawal.
REQUEST_MEMBERS = {"schema_version", "bundle_digest", "requested_at"}
ENVELOPE_MEMBERS = {"payload", "payload_digest", "signature"}


class WithdrawalTransport(StubTransport):
    """The seam, answering as a run log that marked the entry withdrawn."""

    def submit(
        self, *, endpoint: str, body: bytes, contributor_address: str | None
    ) -> bytes:
        """Record the request and answer with a countersigned receipt."""
        self.endpoints.append(endpoint)
        self.bodies.append(body)
        self.addresses.append(contributor_address)
        request = ObjectEnvelope[WithdrawalRequest].model_validate_json(body)
        if self._answer is not None:
            return self._answer(request)  # type: ignore[arg-type]
        return canonical_json_bytes(
            network_signed(withdrawal_receipt_for(request.payload.bundle_digest))
        )


@pytest.fixture
def identity(tmp_path: Path) -> IdentityService:
    """Return this machine's signing identity, freshly created."""
    service = IdentityService(IdentityStore(paths_from_root(tmp_path / "home")))
    service.ensure()
    return service


def service(
    identity: IdentityService,
    transport: WithdrawalTransport,
    *,
    endpoint: str = PINNED_ENDPOINT,
) -> WithdrawalService:
    return WithdrawalService(
        coordinates=COORDINATES,
        endpoint=endpoint,
        identity=identity,
        transport=transport,
        clock=lambda: REQUESTED_AT,
    )


# ---------------------------------------------------------------------------
# The shape on the wire
# ---------------------------------------------------------------------------


def test_the_request_has_exactly_the_members_the_contract_names(
    identity: IdentityService,
) -> None:
    """Three payload members inside the envelope every signed document uses."""
    transport = WithdrawalTransport()
    service(identity, transport).withdraw(BUNDLE_DIGEST)

    document = json.loads(transport.bodies[0])
    assert set(document) == ENVELOPE_MEMBERS
    assert set(document["payload"]) == REQUEST_MEMBERS
    assert document["payload"]["schema_version"] == (
        "techtree.publication-withdrawal.v1alpha1"
    )
    assert document["payload"]["bundle_digest"] == BUNDLE_DIGEST
    assert document["payload"]["requested_at"] == "2026-08-28T08:00:00Z"


def test_the_request_carries_no_free_text_and_no_public_key(
    identity: IdentityService,
) -> None:
    """Nothing a submitter writes appears on the site, so there is nowhere to write.

    The absent public key is the other half: the network looks the participant's
    key up in the publication it already accepted, and a key that travelled with
    the request would be a key the requester chose.
    """
    transport = WithdrawalTransport()
    service(identity, transport).withdraw(BUNDLE_DIGEST)

    raw = transport.bodies[0]
    for gone in (b'"reason"', b'"note"', b'"message"', b'"public_key"'):
        assert gone not in raw, gone


def test_the_request_is_signed_by_this_machine_s_own_key(
    identity: IdentityService,
) -> None:
    """The same key that signed the run, which is the only one this machine has."""
    transport = WithdrawalTransport()
    service(identity, transport).withdraw(BUNDLE_DIGEST)

    envelope = ObjectEnvelope[WithdrawalRequest].model_validate_json(
        transport.bodies[0]
    )
    public = identity.store.load_public()
    assert envelope.signature is not None
    assert envelope.signature.key_id == public.key_id
    assert envelope.payload_digest == digest_object(envelope.payload)
    assert identity.verify_envelope(envelope).verified


def test_the_withdrawal_goes_to_the_one_write_address(
    identity: IdentityService,
) -> None:
    """Decisions 0038 gives the site exactly one address that accepts anything."""
    transport = WithdrawalTransport()

    service(identity, transport).withdraw(BUNDLE_DIGEST)

    assert transport.endpoints == [PINNED_ENDPOINT]


def test_no_contributor_address_travels_with_a_withdrawal(
    identity: IdentityService,
) -> None:
    """The header is a submission's optional field; there is nothing to volunteer."""
    transport = WithdrawalTransport()

    service(identity, transport).withdraw(BUNDLE_DIGEST)

    assert transport.addresses == [None]


# ---------------------------------------------------------------------------
# What comes back
# ---------------------------------------------------------------------------


def test_the_outcome_says_where_the_entry_still_is(
    identity: IdentityService,
) -> None:
    """Withdrawn is not deleted: the answer names the address the entry keeps."""
    outcome = service(identity, WithdrawalTransport()).withdraw(BUNDLE_DIGEST)

    assert outcome.entry_url == ENTRY_URL
    assert outcome.bundle_digest == BUNDLE_DIGEST
    assert outcome.key_id == identity.store.load_public().key_id


def test_an_answer_signed_by_another_key_is_refused(
    identity: IdentityService,
) -> None:
    """The same pin the publication receipt is checked against."""
    impostor = load_private_key(bytes(range(100, 132)))

    def answer(request: ObjectEnvelope[WithdrawalRequest]) -> bytes:
        payload = withdrawal_receipt_for(request.payload.bundle_digest)
        digest = digest_object(payload)
        return canonical_json_bytes(
            ObjectEnvelope[WithdrawalReceiptPayload](
                payload=payload,
                payload_digest=digest,
                signature=sign_digest(
                    impostor, digest, key_id=COORDINATES.network_key.key_id
                ),
            )
        )

    with pytest.raises(ValidationError) as raised:
        service(identity, WithdrawalTransport(answer=answer)).withdraw(  # type: ignore[arg-type]
            BUNDLE_DIGEST
        )

    assert raised.value.code == PUBLICATION_RECEIPT_INVALID
    assert raised.value.details["check"] == "receipt.signature"


def test_an_answer_about_another_entry_is_refused(
    identity: IdentityService,
) -> None:
    """A receipt for a different entry says nothing about this one."""

    def answer(request: ObjectEnvelope[WithdrawalRequest]) -> bytes:
        return canonical_json_bytes(
            network_signed(withdrawal_receipt_for("sha256:" + "1" * 64))
        )

    with pytest.raises(ValidationError) as raised:
        service(identity, WithdrawalTransport(answer=answer)).withdraw(  # type: ignore[arg-type]
            BUNDLE_DIGEST
        )

    assert raised.value.details["check"] == "withdrawal.subject"


def test_an_answer_pointing_off_the_pinned_log_is_refused(
    identity: IdentityService,
) -> None:
    """An entry address on another origin is a link the answering server chose."""

    def answer(request: ObjectEnvelope[WithdrawalRequest]) -> bytes:
        return canonical_json_bytes(
            network_signed(
                withdrawal_receipt_for(
                    request.payload.bundle_digest,
                    entry_url="https://elsewhere.example/runs/x",
                )
            )
        )

    with pytest.raises(ValidationError) as raised:
        service(identity, WithdrawalTransport(answer=answer)).withdraw(  # type: ignore[arg-type]
            BUNDLE_DIGEST
        )

    assert raised.value.details["check"] == "receipt.entry_url"


def test_an_answer_that_is_not_a_withdrawal_receipt_is_refused(
    identity: IdentityService,
) -> None:
    with pytest.raises(ValidationError) as raised:
        service(
            identity,
            WithdrawalTransport(answer=lambda _request: b"<html>hello</html>"),
        ).withdraw(BUNDLE_DIGEST)

    assert raised.value.code == PUBLICATION_RECEIPT_INVALID


def test_a_receipt_the_network_really_signed_verifies_here(
    identity: IdentityService,
) -> None:
    """The control: the countersignature this side checks is a real one."""
    payload = withdrawal_receipt_for(BUNDLE_DIGEST)
    envelope = network_signed(payload)

    assert envelope.signature is not None
    assert verify_signature(
        _pinned_public_key(), envelope.payload_digest, envelope.signature
    )


def _pinned_public_key() -> Ed25519PublicKey:
    """Return the pinned network key, loaded the way the verifier loads it."""
    return load_public_key(b64decode(COORDINATES.network_key.public_key, validate=True))


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a Techtree home with an identity and a stubbed run log."""
    root = tmp_path / "home"
    root.mkdir()
    IdentityService(IdentityStore(paths_from_root(root))).ensure()
    monkeypatch.setattr(
        withdraw_module, "HttpsPublicationTransport", WithdrawalTransport
    )
    # The release pins a real key whose private half nobody in this repository
    # holds, so a test that wants an answer to verify has to withdraw against
    # coordinates it can sign for. Only the coordinates are substituted; every
    # check made against them is the real one, and the test below this file's
    # last fixture reads the unsubstituted ones straight off the wheel.
    monkeypatch.setattr(
        withdraw_module, "packaged_publication_coordinates", lambda: COORDINATES
    )
    return root


def invoke(home: Path, *arguments: str, stdin: str | None = None) -> Any:
    return CliRunner().invoke(
        create_app(), ["--home", str(home), *arguments], input=stdin
    )


def test_a_machine_that_cannot_be_asked_is_told_which_flag_to_pass(
    home: Path,
) -> None:
    """Withdrawing changes a public page, so somebody has to say so."""
    result = invoke(home, "--json", "withdraw", BUNDLE_DIGEST)

    assert result.exit_code == EXIT_USAGE
    assert WITHDRAWAL_CONFIRMATION_REQUIRED in result.stdout


def test_saying_no_at_the_prompt_sends_nothing(home: Path) -> None:
    result = invoke(home, "withdraw", BUNDLE_DIGEST, stdin="n\n")

    assert result.exit_code == EXIT_USAGE
    assert "no request left this machine" in result.stdout


def test_the_review_says_what_withdrawal_does_and_does_not_do(home: Path) -> None:
    """The honest claim: the entry stays, marked, and nothing is erased."""
    result = invoke(home, "withdraw", BUNDLE_DIGEST, stdin="n\n")

    printed = " ".join(result.stdout.split())
    assert "It is not a deletion" in printed
    assert BUNDLE_DIGEST in printed


def test_something_that_is_not_a_bundle_digest_is_refused(home: Path) -> None:
    result = invoke(home, "--json", "withdraw", "run_123", "--yes")

    assert result.exit_code != EXIT_OK
    assert "digest must be sha256" in result.stdout


def test_withdrawing_reports_what_the_log_answered(home: Path) -> None:
    result = invoke(home, "--json", "withdraw", BUNDLE_DIGEST, "--yes")

    assert result.exit_code == EXIT_OK
    data = json.loads(result.stdout)["data"]
    assert data["entry_url"] == ENTRY_URL
    assert data["bundle_digest"] == BUNDLE_DIGEST
    assert data["endpoint"] == PINNED_ENDPOINT


def test_the_development_override_moves_the_withdrawal_too(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One address for the whole feature, wherever that address is pointed."""
    monkeypatch.setenv(ENDPOINT_VARIABLE, ENDPOINT)

    result = invoke(home, "--json", "withdraw", BUNDLE_DIGEST, "--yes")

    assert json.loads(result.stdout)["data"]["endpoint"] == ENDPOINT


def test_the_command_uses_the_coordinates_this_build_actually_ships(
    tmp_path: Path,
) -> None:
    """Nothing is substituted here: this is the release the wheel carries.

    Deliberately outside the ``home`` fixture, which replaces the pinned
    coordinates so that a stubbed run log can produce a verifying signature. A
    build whose commands read anything but its own ReleaseCore fails here.
    """
    context = build_cli_context(
        home=tmp_path / "unpatched",
        json_output=True,
        no_color=True,
        no_input=True,
        debug=False,
    )

    service = build_withdrawal_service(context)

    assert service.endpoint == packaged_publication_coordinates().submission_endpoint
    assert service.endpoint == "https://techtree.sh/api/v1/publications"
