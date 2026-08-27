"""The address a submission may be sent to. Decisions document 0038.

Nothing here opens a socket. What is checked is the two rules that hold before
one could be opened, because both are properties of the address rather than of
the request: a proof bundle and a volunteered address travel over a channel
nobody can read or rewrite, and neither of them is ever put where a proxy log,
an access log or a browser history would keep it.
"""

from __future__ import annotations

import pytest

from fixtures.publication import ENDPOINT
from techtree.errors import ValidationError
from techtree.publication.transport import (
    PUBLICATION_ENDPOINT_INVALID,
    validated_endpoint,
)


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
