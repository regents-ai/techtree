"""Turning a real evaluation into receipts. Spec sections 7.6-7.8.

This package is where measured evidence becomes a Techtree claim. Everything
above it — the child processes, the containers, the provider calls — has
finished by the time anything here runs, and nothing here may change what was
measured. Three rules shape every module:

*The engine's normalizer is the boundary.* Nothing in this package reads
``traces.jsonl``. The raw upstream record is read once, by the pinned Verifiers
build that wrote it, inside the engine bundle (spec section 6.12); this package
reads that projection and no other source. A receipt built by re-parsing
upstream wire records with a different library version would be an
interpretation wearing the authority of a measurement.

*Rewards are copied, never computed.* A reward reaches a receipt exactly as
Verifiers recorded it — not rescored, not rounded, not re-weighted. The only
decisions taken here are about *status*: whether the number may be presented as
a result at all.

*A structural doubt is a refusal, a recorded failure is a status.* An
evaluation missing a committed task, scoring one twice, or carrying a trace in
the wrong seat cannot be turned into receipts at all, and those are the typed
refusals of spec section 15. An episode that genuinely failed, or a trace whose
scoring genuinely errored, is recorded with an honest ``score_status`` — the
receipt exists and says what happened.

The division of labour:

``episode``
    The parsing boundary and one immutable receipt per committed task.
``set``
    The ordered, content-addressed commitment over one variant's receipts.
``observed``
    What the engine actually resolved, fingerprinted for comparison against
    what the manifest declared.
``compare``
    Whether the two variants' executions were one experiment: declared against
    declared, observed against observed, and observed against declared.
``uplift``
    The paired rewards, the aggregate over them, and the report — which is the
    only place in this package where two variants meet.
"""

from __future__ import annotations

__all__: list[str] = []
