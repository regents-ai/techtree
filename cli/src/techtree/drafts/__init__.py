"""Immutable submission drafts and the one-time handover that starts one.

Spec PR6 §6.7.

A draft is the complete, reviewable statement of what a participant is about to
run: the public graph it came from, the two experiment variants, the proof that
those variants differ only where permitted, the snapshotted candidate skill,
and the rights the participant is being asked to accept. Once written it is
never edited. A change of mind is a new draft.

Two modules divide the work:

:mod:`techtree.drafts.source`
    What a draft is prepared against: a Campaign, its DataPolicy, its
    publisher validation receipt, and the public Climb that invited it when
    there is one. A Skill replacement (spec section 7.19) is derived locally
    and no Climb wraps it, so the Climb is the one part that may be absent.

:mod:`techtree.drafts.store`
    Placement, verification, and the start claim. Where each file lives under
    ``drafts/draft_<id>/``, how the whole graph is re-verified offline without
    consulting the catalog, and the exactly-once handover to a run.

Preparing a draft is not accepting its data policy. Decisions document 0019
section 2 puts the acceptance where a person can act on it: the draft is
reviewed, the review is answered, and the run records that it was — nothing
here may be read as consent.
"""

from __future__ import annotations

__all__: list[str] = []
