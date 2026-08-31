"""The one step that opens a socket. Decisions document 0038.

Two of these tests are about an address and need no server: a proof bundle and a
volunteered address travel over a channel nobody can read or rewrite, and
neither is ever put where a proxy log, an access log or a browser history would
keep it.

The rest are about the exchange, and they are exercised rather than read.
Decisions 0038's founder ruling closed three holes here — a redirect that was
refused only in a docstring, an answer nobody checked the type of, and a size cap
read in a way that could not tell "four megabytes" from "at least four
megabytes" — and each of the three is a behaviour of ``urlopen`` rather than of
this repository's own code. A test that asserted over the source would pass
against a build that had silently gone back to the default opener, so instead
each one is put in front of a real HTTPS server that does the wrong thing.

The server is local, ephemeral, and speaks TLS with a certificate generated in
the test and trusted for the length of it through ``SSL_CERT_FILE``. That is what
lets the transport be exercised as itself: no argument is substituted, no method
is patched, and the request that goes out is the request a person's publication
would make.
"""

from __future__ import annotations

import datetime
import http.server
import ssl
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from fixtures.publication import COORDINATES, ENDPOINT, PINNED_ENDPOINT
from techtree.errors import TechtreeError, ValidationError
from techtree.publication import transport as publication_transport
from techtree.publication.address import (
    SKILL_GITHUB_URL_INVALID,
    canonical_skill_github_url,
)
from techtree.publication.transport import (
    PUBLICATION_ENDPOINT_INVALID,
    PUBLICATION_RESPONSE_NOT_JSON,
    PUBLICATION_RESPONSE_TOO_LARGE,
    PUBLICATION_TRANSPORT_REDIRECTED,
    HttpsPublicationTransport,
    resolved_endpoint,
    validated_endpoint,
)

# ---------------------------------------------------------------------------
# The address
# ---------------------------------------------------------------------------


def test_a_run_log_address_is_accepted_whole() -> None:
    assert validated_endpoint(ENDPOINT) == ENDPOINT


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://techtree.example/api/v1/run-log",
        "ftp://techtree.example/run-log",
        "techtree.example/run-log",
        "file:///tmp/run-log",
        "https:///run-log",
    ],
)
def test_anything_that_is_not_https_is_refused(endpoint: str) -> None:
    """A scheme that permitted plain text would be a setting got wrong once."""
    with pytest.raises(ValidationError) as raised:
        validated_endpoint(endpoint)

    assert raised.value.code == PUBLICATION_ENDPOINT_INVALID


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://techtree.example/run-log?address=0xabc",
        "https://techtree.example/run-log?run=1",
        "https://techtree.example/run-log#fragment",
    ],
)
def test_an_address_with_anything_after_the_path_is_refused(endpoint: str) -> None:
    """A submission travels in the body, so nothing may ride in the URL."""
    with pytest.raises(ValidationError) as raised:
        validated_endpoint(endpoint)

    assert raised.value.code == PUBLICATION_ENDPOINT_INVALID


def test_the_pinned_address_is_used_when_nothing_overrides_it() -> None:
    """A stable release publishes with no environment variable set."""
    assert resolved_endpoint(COORDINATES, None) == PINNED_ENDPOINT
    assert resolved_endpoint(COORDINATES, ENDPOINT) == ENDPOINT


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/owner/repo",
        "https://www.github.com/owner/repo",
        "https://github.com/owner/repo/",
        "https://github.com/owner/repo.git",
        "https://github.com/owner/repo?tab=readme",
        "https://github.com/owner/repo/issues",
    ],
)
def test_a_skill_github_url_must_be_the_canonical_repository_shape(url: str) -> None:
    with pytest.raises(ValidationError) as raised:
        canonical_skill_github_url(url)

    assert raised.value.code == SKILL_GITHUB_URL_INVALID


def test_a_skill_github_url_is_kept_in_its_canonical_spelling() -> None:
    assert canonical_skill_github_url("https://github.com/Owner/repo_name") == (
        "https://github.com/Owner/repo_name"
    )


# ---------------------------------------------------------------------------
# The exchange, against a server that misbehaves on purpose
# ---------------------------------------------------------------------------


@dataclass
class Answer:
    """What the local server is told to answer with."""

    status: int = 200
    content_type: str = "application/json"
    body: bytes = b'{"ok":true}'
    location: str | None = None


@dataclass
class LocalRunLog:
    """A run log on this machine, answering however a test tells it to."""

    url: str
    answer: Answer
    #: Every path the server was asked for, so a test can prove a redirect was
    #: not followed rather than only that it was reported.
    requested: list[str]
    headers: list[dict[str, str]]


@pytest.fixture
def run_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[LocalRunLog]:
    """Serve one local HTTPS run log, trusted for the length of one test."""
    certificate, key = _self_signed(tmp_path)
    monkeypatch.setenv("SSL_CERT_FILE", str(certificate))

    answer = Answer()
    requested: list[str] = []
    received_headers: list[dict[str, str]] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            requested.append(self.path)
            received_headers.append(dict(self.headers.items()))
            self.send_response(answer.status)
            if answer.location is not None:
                self.send_header("Location", answer.location)
            self.send_header("Content-Type", answer.content_type)
            self.send_header("Content-Length", str(len(answer.body)))
            self.end_headers()
            self.wfile.write(answer.body)

        def log_message(self, *args: object) -> None:
            """Keep the server out of the test output."""

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate, key)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield LocalRunLog(
            url=f"https://localhost:{server.server_address[1]}/api/v1/publications",
            answer=answer,
            requested=requested,
            headers=received_headers,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _submit(run_log: LocalRunLog, *, address: str | None = None) -> bytes:
    """Make the real request the real way."""
    return HttpsPublicationTransport().submit(
        endpoint=run_log.url, body=b'{"hello":true}', contributor_address=address
    )


def test_skill_metadata_travels_in_headers_beside_the_fixed_body(
    run_log: LocalRunLog,
) -> None:
    HttpsPublicationTransport().submit(
        endpoint=run_log.url,
        body=b'{"schema_version":"example"}',
        contributor_address=None,
        skill_name="Branch Code v1",
        skill_github_url="https://github.com/example/branch-code",
    )

    assert len(run_log.headers) == 1
    assert run_log.headers[0]["X-Techtree-Skill-Name"] == "Branch Code v1"
    assert (
        run_log.headers[0]["X-Techtree-Skill-Github-Url"]
        == "https://github.com/example/branch-code"
    )


def test_a_well_behaved_run_log_is_answered_normally(run_log: LocalRunLog) -> None:
    """The control: everything below is the same request, answered badly."""
    assert _submit(run_log) == b'{"ok":true}'
    assert run_log.requested == ["/api/v1/publications"]


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_a_redirect_is_refused_and_never_followed(
    run_log: LocalRunLog, status: int
) -> None:
    """The hole the docstring claimed was closed. Decisions 0038 blocker three.

    A followed redirect would re-send the whole proof bundle, and the private
    contributor header with it, to an origin nobody agreed to. The second
    request is not made at all, which the server's own record of what it was
    asked for is what proves.
    """
    run_log.answer.status = status
    run_log.answer.location = "https://elsewhere.example/collect"

    with pytest.raises(TechtreeError) as raised:
        _submit(run_log, address="0x0000000000000000000000000000000000000001")

    assert raised.value.code == PUBLICATION_TRANSPORT_REDIRECTED
    assert raised.value.retryable is False
    assert run_log.requested == ["/api/v1/publications"]


def test_a_redirect_back_to_the_same_origin_is_refused_too(
    run_log: LocalRunLog,
) -> None:
    """Same origin or not, a second request is one nobody agreed to."""
    run_log.answer.status = 307
    run_log.answer.location = f"{run_log.url}/again"

    with pytest.raises(TechtreeError) as raised:
        _submit(run_log)

    assert raised.value.code == PUBLICATION_TRANSPORT_REDIRECTED
    assert run_log.requested == ["/api/v1/publications"]


@pytest.mark.parametrize(
    "content_type",
    ["text/html", "text/plain", "application/octet-stream", "application/jsonl"],
)
def test_an_answer_that_is_not_json_is_refused(
    run_log: LocalRunLog, content_type: str
) -> None:
    """A captive portal answers 200 with a login page, and it is not a receipt."""
    run_log.answer.content_type = content_type
    run_log.answer.body = b"<html>sign in</html>"

    with pytest.raises(TechtreeError) as raised:
        _submit(run_log)

    assert raised.value.code == PUBLICATION_RESPONSE_NOT_JSON
    assert raised.value.details["content_type"] == content_type


def test_a_json_answer_with_parameters_on_its_type_is_still_json(
    run_log: LocalRunLog,
) -> None:
    """``application/json; charset=utf-8`` is the media type plus a parameter."""
    run_log.answer.content_type = "application/json; charset=utf-8"

    assert _submit(run_log) == b'{"ok":true}'


def test_an_answer_that_does_not_end_inside_the_cap_is_refused(
    run_log: LocalRunLog,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One byte over, which is the case reading exactly the cap cannot see.

    Reading ``MAX_RESPONSE_BYTES`` and getting ``MAX_RESPONSE_BYTES`` back says
    the answer reached the limit, not that it stopped there. Reading one more is
    what tells the two apart, and this is the answer that only the second
    reading refuses.
    """
    limit = 1024
    monkeypatch.setattr(publication_transport, "MAX_RESPONSE_BYTES", limit)
    run_log.answer.body = b"x" * (limit + 1)

    with pytest.raises(TechtreeError) as raised:
        _submit(run_log)

    assert raised.value.code == PUBLICATION_RESPONSE_TOO_LARGE
    assert raised.value.details["limit"] == limit


def test_an_answer_exactly_at_the_cap_is_read_whole(
    run_log: LocalRunLog,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The boundary from the other side: at the cap is not over it."""
    limit = 1024
    monkeypatch.setattr(publication_transport, "MAX_RESPONSE_BYTES", limit)
    run_log.answer.body = b"y" * limit

    assert _submit(run_log) == run_log.answer.body


def _self_signed(directory: Path) -> tuple[Path, Path]:
    """Return a certificate and key for ``localhost``, valid for this test only."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    certificate_path = directory / "run-log-cert.pem"
    key_path = directory / "run-log-key.pem"
    certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return certificate_path, key_path
