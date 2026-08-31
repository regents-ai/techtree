"""Candidate skill validation, scanning, and snapshot archiving.

Spec section 15.

A source skill is never evaluated where the participant wrote it. It is
validated against a policy, scanned for secrets, and copied into an immutable
snapshot whose archive bytes are fully determined by the file contents. This
package holds the three pieces that make that possible: the policy, the
scanner, and the deterministic archive.
"""

from __future__ import annotations

__all__: list[str] = []
