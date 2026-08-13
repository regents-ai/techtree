"""Turning a finished evaluation into a run's result. Spec section 7.20.

WP6 ends with two variants' evidence written into a run directory and a run
still in ``running_variants``. Everything between that and a completed run —
receipts, ordered commitments, the controlled comparison, the aggregation and
the report — is a sequence of pure functions over the run's own files, and this
package is where that sequence is written down once so the worker can call it.

``service``
    The stage that closes a real run: build, commit, compare, aggregate,
    report, record.

Spec section 7.20's ``UpliftService`` — sanitized improvement context and
Skill-replacement preparation — is a different object with a different job and
belongs to WP7d. It will live beside this one.
"""

from __future__ import annotations

__all__: list[str] = []
