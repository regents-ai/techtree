"""Where this build publishes, read off the release it belongs to.

Decisions document 0038, founder ruling of 2026-08-27.

One function, in one place, because two commands need the same answer and an
answer that differed between them would be a build that publishes to one address
and withdraws at another.

It is read from the ReleaseCore the wheel carries rather than from a setting,
which is what makes a stable release able to publish the moment it is installed.
A build that ships no ReleaseCore was not produced by the release generator, and
it says so: publishing needs to know not only where the run log is but which
key's countersignature would be worth anything, and neither is a thing to guess.
"""

from __future__ import annotations

from techtree.release.document import packaged_release_core_bytes, parse_release_core
from techtree.release.models import PublicationCoordinates

__all__ = ["packaged_publication_coordinates"]


def packaged_publication_coordinates() -> PublicationCoordinates:
    """Return the publication coordinates this build's release pins."""
    return parse_release_core(packaged_release_core_bytes()).publication
