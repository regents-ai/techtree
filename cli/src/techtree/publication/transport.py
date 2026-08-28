"""The one place in this package that opens a socket. Decisions document 0038.

Everything else about publishing — reading a bundle, checking it, asking a
person, writing a receipt down, recording the outcome — is local work on local
files, and it is testable exactly as the rest of this project is. One step is
not: the request itself. There is no public endpoint yet, and there will never
be one a unit test may reach.

So the request is a seam and nothing else is. :class:`PublicationTransport` takes
bytes and an address and returns bytes; it knows nothing about what a submission
is, what a receipt is, or whether either verifies. That keeps the substitutable
part as small as a thing can be: a test replaces one method, and every decision
the product makes about publishing is still the real code making it.

Two rules hold here rather than at the call site, because they are properties of
the transport rather than of the product.

*Only ``https``.* What travels is a signed proof bundle, and sometimes an
address somebody typed. Neither goes over a channel anybody can read or rewrite,
and a scheme that permitted it would be a setting somebody could get wrong once.

*Nothing in the address bar.* The submission is a request body. Nothing this
module sends is ever appended to a URL or a query string, so nothing can end up
in a proxy log, in an access log, or in a browser history.

*A volunteered address travels beside the body, never inside it.* The run log
stores the submission it was given and serves those exact bytes back at a public
address, so anything inside the body is public by construction. An address is
not, so it goes in a header the log reads and does not echo. This is the shape
the receiving side settled on for the same reason, and the two halves have to
agree or the log refuses the submission.

*No redirect is followed.* This one was a docstring before it was a behaviour.
``urlopen``'s default opener follows redirects, so an address that answered
``302`` would have had the proof bundle — and the private contributor header —
re-sent to whatever origin it named, with none of the checks above applying to
the second request. The opener below is built with a redirect handler that
declines to build a redirected request at all, so a redirect is reported as a
refusal and nothing leaves this machine twice.

*The answer has to be JSON, and it has to end.* A run log answers with a
receipt; anything else is a misconfigured address or a captive portal, and
parsing it would only turn one problem into a confusing one. The size cap is
read *plus one byte*, because reading exactly the cap proves only that the cap
was reached — the response may have continued, and a truncated document that
parses is worse than one that does not.
"""

from __future__ import annotations

import http.client
import urllib.error
import urllib.request
from typing import Final, Protocol
from urllib.parse import urlsplit

from techtree.errors import TechtreeError, ValidationError
from techtree.release.models import PublicationCoordinates

__all__ = [
    "CONTRIBUTOR_ADDRESS_HEADER",
    "MAX_RESPONSE_BYTES",
    "PUBLICATION_ENDPOINT_INVALID",
    "PUBLICATION_RESPONSE_NOT_JSON",
    "PUBLICATION_RESPONSE_TOO_LARGE",
    "PUBLICATION_TRANSPORT_FAILED",
    "PUBLICATION_TRANSPORT_REDIRECTED",
    "SKILL_GITHUB_URL_HEADER",
    "SKILL_NAME_HEADER",
    "HttpsPublicationTransport",
    "PublicationMetadataTransport",
    "PublicationTransport",
    "resolved_endpoint",
    "validated_endpoint",
]

#: Stable error code for a configured endpoint that is not one.
PUBLICATION_ENDPOINT_INVALID: Final = "publication_endpoint_invalid"

#: Stable error code for a request that did not come back with a receipt.
PUBLICATION_TRANSPORT_FAILED: Final = "publication_transport_failed"

#: Stable error code for an address that answered by pointing somewhere else.
PUBLICATION_TRANSPORT_REDIRECTED: Final = "publication_transport_redirected"

#: Stable error code for an answer that is not a JSON document.
PUBLICATION_RESPONSE_NOT_JSON: Final = "publication_response_not_json"

#: Stable error code for an answer that did not end inside the size cap.
PUBLICATION_RESPONSE_TOO_LARGE: Final = "publication_response_too_large"

_MEDIA_TYPE: Final = "application/json"
_TIMEOUT_SECONDS: Final = 120.0

#: Where a volunteered address travels. Beside the body, never inside it: the
#: run log serves a stored submission back at a public address.
CONTRIBUTOR_ADDRESS_HEADER: Final = "x-techtree-contributor-address"

#: Public descriptive metadata travels beside the fixed proof body. The
#: receiving side may store these headers with the immutable log entry, while
#: the submission document itself remains the four-member contract.
SKILL_NAME_HEADER: Final = "x-techtree-skill-name"
SKILL_GITHUB_URL_HEADER: Final = "x-techtree-skill-github-url"

#: Enough for a proof bundle several times over, and small enough that a
#: misconfigured address answering with something enormous is refused rather
#: than read into memory.
MAX_RESPONSE_BYTES: Final = 4 * 1024 * 1024


class PublicationTransport(Protocol):
    """Send one submission and return whatever came back."""

    def submit(
        self, *, endpoint: str, body: bytes, contributor_address: str | None
    ) -> bytes:
        """Return the response body, or raise a typed failure."""
        ...


class PublicationMetadataTransport(Protocol):
    """Transport seam extended with optional public Skill metadata headers."""

    def submit(
        self,
        *,
        endpoint: str,
        body: bytes,
        contributor_address: str | None,
        skill_name: str | None = None,
        skill_github_url: str | None = None,
    ) -> bytes:
        """Return the response body, or raise a typed failure."""
        ...


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """A redirect handler that builds no redirected request.

    Returning ``None`` from :meth:`redirect_request` is urllib's own way of
    saying "this redirect is not to be followed". The handler chain then falls
    through to the default error handler, which raises the ``3xx`` as an
    :class:`urllib.error.HTTPError`, and :class:`HttpsPublicationTransport`
    turns that into a refusal naming the redirect rather than a bare status.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        """Decline to build the second request."""
        return None


def _opener() -> urllib.request.OpenerDirector:
    """Return the opener every publication request goes through.

    Built rather than taken from :func:`urllib.request.urlopen`, whose default
    opener follows redirects. ``build_opener`` leaves out the default handler of
    any class an argument is an instance of, so passing the subclass above is
    what replaces redirect-following rather than adding to it.
    """
    return urllib.request.build_opener(_RefuseRedirects())


class HttpsPublicationTransport:
    """The real request: one POST, one response, no redirects followed."""

    def submit(
        self,
        *,
        endpoint: str,
        body: bytes,
        contributor_address: str | None,
        skill_name: str | None = None,
        skill_github_url: str | None = None,
    ) -> bytes:
        """POST ``body`` to ``endpoint`` and return the response bytes."""
        headers = {
            "Content-Type": _MEDIA_TYPE,
            "Accept": _MEDIA_TYPE,
            "Content-Length": str(len(body)),
        }
        if contributor_address is not None:
            headers[CONTRIBUTOR_ADDRESS_HEADER] = contributor_address
        if skill_name is not None:
            headers[SKILL_NAME_HEADER] = skill_name
        if skill_github_url is not None:
            headers[SKILL_GITHUB_URL_HEADER] = skill_github_url
        request = urllib.request.Request(
            validated_endpoint(endpoint),
            data=body,
            method="POST",
            headers=headers,
        )
        try:
            with _opener().open(request, timeout=_TIMEOUT_SECONDS) as response:
                return _response_bytes(response)
        except urllib.error.HTTPError as error:
            if 300 <= error.code < 400:
                raise TechtreeError(
                    f"the run log answered HTTP {error.code} and pointed "
                    "somewhere else, and a proof bundle is not re-sent to an "
                    "address that was not the one agreed to",
                    code=PUBLICATION_TRANSPORT_REDIRECTED,
                    retryable=False,
                    details={"status": error.code},
                ) from error
            raise TechtreeError(
                f"the run log refused this submission: HTTP {error.code}",
                code=PUBLICATION_TRANSPORT_FAILED,
                retryable=error.code >= 500,
                details={"status": error.code},
            ) from error
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            raise TechtreeError(
                "the run log could not be reached, so nothing was sent",
                code=PUBLICATION_TRANSPORT_FAILED,
                retryable=True,
                details={"reason": type(error).__name__},
            ) from error


def _response_bytes(response: http.client.HTTPResponse) -> bytes:
    """Return the answer, having proved it is a JSON document that ended.

    Both refusals are here rather than at the call site because both are
    properties of the exchange rather than of what the document turns out to
    say. A receipt is refused later for being the wrong receipt; this is refused
    now for not being an answer at all.
    """
    media_type = response.headers.get_content_type()
    if media_type != _MEDIA_TYPE:
        raise TechtreeError(
            f"the run log answered with {media_type} rather than {_MEDIA_TYPE}, "
            "so what came back is not a publication receipt",
            code=PUBLICATION_RESPONSE_NOT_JSON,
            retryable=False,
            details={"content_type": media_type},
        )

    # One byte past the cap. Reading exactly the cap and getting exactly the cap
    # back says the answer reached the limit, not that it stopped there.
    raw = bytes(response.read(MAX_RESPONSE_BYTES + 1))
    if len(raw) > MAX_RESPONSE_BYTES:
        raise TechtreeError(
            f"the run log's answer is longer than {MAX_RESPONSE_BYTES} bytes, "
            "which no publication receipt is, so none of it was read further",
            code=PUBLICATION_RESPONSE_TOO_LARGE,
            retryable=False,
            details={"limit": MAX_RESPONSE_BYTES},
        )
    return raw


def resolved_endpoint(coordinates: PublicationCoordinates, override: str | None) -> str:
    """Return the address a publication or a withdrawal is sent to.

    The override first, then the release coordinate. A stable release publishes
    with nothing configured, because the address is pinned in the ReleaseCore
    the wheel carries (decisions 0038's founder ruling of 2026-08-27): a wheel
    somebody installed can publish the moment it is installed, and nobody has to
    be told to set a variable they could set wrongly.

    The override stays for development, where a throwaway local instance stands
    in for the deployed one. It is checked as an address and the pinned one is
    not, because the pinned one was already checked when the release document
    was validated and the override is the one a person can get wrong today.
    """
    if override is not None:
        return validated_endpoint(override)
    return coordinates.submission_endpoint


def validated_endpoint(endpoint: str) -> str:
    """Return the endpoint, or refuse an address nothing may be sent to."""
    parts = urlsplit(endpoint)
    if parts.scheme != "https" or not parts.netloc:
        raise ValidationError(
            "a run log address is an https URL, and this one is not",
            code=PUBLICATION_ENDPOINT_INVALID,
            details={"scheme": parts.scheme},
        )
    if parts.query or parts.fragment:
        raise ValidationError(
            "a run log address carries no query string: a submission travels "
            "in the request body and never in a URL",
            code=PUBLICATION_ENDPOINT_INVALID,
            details={"scheme": parts.scheme},
        )
    return endpoint
