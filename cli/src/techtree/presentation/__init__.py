"""Showing a result without becoming part of it. Spec sections 7.13-7.17.

Spec section 3.5 draws the line this package lives on: rich terminal output is
a view, not scientific evidence. No colour, markup, prose, or channel-specific
formatting enters an ``EpisodeReceipt`` or an ``UpliftReport``, and nothing in
this package can change a number, a status, or a digest — every one of them is
copied out of a signed report and formatted.

That is why the payload is channel-neutral. One builder produces one
:class:`~techtree.presentation.models.UpliftPresentationPayload` from the
signed report; a terminal renderer, a phone-sized Markdown renderer, and the
founder's own rich-output Skill all consume the same object. A second builder
per channel would be a second place a result could be described differently.

The division of labour:

``models``
    The neutral payload, and the pieces a renderer draws.
``build``
    Turning one signed report into one payload.
``rich``
    The accessible terminal rendering.
``compact``
    The bounded, ANSI-free rendering a gateway or a phone can carry.
``sanitize``
    What may appear at all, enforced rather than intended.
"""

from __future__ import annotations

__all__: list[str] = []
