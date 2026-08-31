"""Native Verifiers execution. Spec sections 6.3-6.14.

This package is the boundary between a resolved Techtree experiment and the
pinned Verifiers ``eval`` entrypoint. Nothing here imports ``verifiers``: the
library belongs to the managed engine environment, and everything Techtree
knows about its wire shapes was proven empirically and written down in
``docs/verifiers-eval.md``. That document, not this code's optimism, is the
source for every assumption below.

The division of labour is deliberate:

``models``
    Local integration types. Not protocol roots, not published.
``config``
    The strict, allow-listed TOML Techtree is permitted to emit. The compiler
    cannot express a Verifiers knob this module does not model, which is what
    makes "only the skill differs" checkable rather than hoped for.
``compiler``
    One resolved experiment in, one ``EvalToml`` out, deterministically.
``credentials``
    Whether the declared endpoint can authenticate, answered without ever
    returning, logging, or persisting a secret.
``outputs``
    The files a finished run must have left behind, hashed exactly.
``verify``
    Whether a compiled configuration survives the engine's own resolution.
"""

from __future__ import annotations

__all__: list[str] = []
