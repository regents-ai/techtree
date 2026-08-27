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
"""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Final, Protocol
from urllib.parse import urlsplit

from techtree.errors import TechtreeError, ValidationError

__all__ = [
    "PUBLICATION_ENDPOINT_INVALID",
    "PUBLICATION_TRANSPORT_FAILED",
    "HttpsPublicationTransport",
    "PublicationTransport",
    "validated_endpoint",
]

#: Stable error code for a configured endpoint that is not one.
PUBLICATION_ENDPOINT_INVALID: Final = "publication_endpoint_invalid"

#: Stable error code for a request that did not come back with a receipt.
PUBLICATION_TRANSPORT_FAILED: Final = "publication_transport_failed"

_MEDIA_TYPE: Final = "application/json"
_TIMEOUT_SECONDS: Final = 120.0

#: Enough for a proof bundle several times over, and small enough that a
#: misconfigured address answering with something enormous is refused rather
#: than read into memory.
_MAX_RESPONSE_BYTES: Final = 4 * 1024 * 1024


class PublicationTransport(Protocol):
    """Send one submission and return whatever came back."""

    def submit(self, *, endpoint: str, body: bytes) -> bytes:
        """Return the response body, or raise a typed failure."""
        ...


class HttpsPublicationTransport:
    """The real request: one POST, one response, no redirects followed."""

    def submit(self, *, endpoint: str, body: bytes) -> bytes:
        """POST ``body`` to ``endpoint`` and return the response bytes."""
        request = urllib.request.Request(
            validated_endpoint(endpoint),
            data=body,
            method="POST",
            headers={
                "Content-Type": _MEDIA_TYPE,
                "Accept": _MEDIA_TYPE,
                "Content-Length": str(len(body)),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                return bytes(response.read(_MAX_RESPONSE_BYTES))
        except urllib.error.HTTPError as error:
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
