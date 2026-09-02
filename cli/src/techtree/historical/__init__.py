"""Read-only projectors for evidence earlier releases wrote.

Every projector here is versioned by the release whose evidence it reads, and
every one of them only reads. Nothing in this package writes a file, signs an
object, or hands a v0.1 shape back to a live write path; the v0.2 producers
have one shape and it is the only shape they emit.

:mod:`techtree.historical.v01` is the v0.1 projector.
"""

from __future__ import annotations

__all__: list[str] = []
