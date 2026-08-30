"""Publishing one finished run to the public log. Decisions document 0038.

This is the only package in Techtree that sends anything anywhere, and it sends
one thing: a proof bundle a person asked it to publish, after that bundle's own
proof has been checked and found to hold together. Nothing here runs on its own,
nothing here runs during a run, and nothing here is reachable without somebody
answering a question first.

Four rules shape every module below.

*A result that does not verify is never offered.* The verification is the first
step of publishing, not a check somebody could skip, because the whole of what
this product is for is that a published number came with its own evidence.

*A completed run's files are final.* Publishing adds a countersigned receipt and
a journal of its own to the run directory. It rewrites nothing, including the
run's own event log, which closed when the run ended.

*The address bar carries nothing.* A submission is a request body. No proof, no
digest and no volunteered address is ever put in a URL or a query string.

*A volunteered address is sent and not kept.* It is optional, it defaults to no,
its field name says it is unverified because nobody proved control of it, and
nothing on this machine writes it down.

The division of labour:

``address``
    Trimming, shape, the EIP-55 checksum, and the canonical lowercase form.
``keccak``
    The one hash EIP-55 needs and no standard library provides.
``models``
    What a submission is and what a receipt is.
``journal``
    The append-only record of what has been published about one run.
``transport``
    The single seam that opens a socket, and the only substitutable part.
``service``
    The order the steps happen in, which is the product.
"""

from __future__ import annotations

__all__: list[str] = []
