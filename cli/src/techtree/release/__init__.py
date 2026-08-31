"""The release document that binds this build to one Climb v0.1 release.

Spec sections 6.6, 9.3-9.5 and 9.7. Everything here is about *coordinates*:
which CLI version, which source commit, which engine, which catalog, which
Skills. Nothing in this package runs a Climb, calls a model, or writes to the
network, and nothing outside it is allowed to invent a release coordinate.
"""

from __future__ import annotations
