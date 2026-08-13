"""Immutable submission drafts and the one-time confirmation that starts one.

Spec PR6 §6.6 and §6.7.

A draft is the complete, reviewable statement of what a participant is about to
run: the public graph it came from, the two experiment variants, the proof that
those variants differ only where permitted, the snapshotted candidate skill,
and the rights the participant is being asked to accept. Once written it is
never edited. A change of mind is a new draft.

Two modules divide the work:

:mod:`techtree.drafts.confirmation`
    Proof of intent. A single-use token, held only as a SHA-256 hash, bound to
    the digest of one complete draft and valid for fifteen minutes.

:mod:`techtree.drafts.store`
    Placement, verification, and the start claim. Where each file lives under
    ``drafts/draft_<id>/``, how the whole graph is re-verified offline without
    consulting the catalog, and the exactly-once handover to a run.

Confirming a draft is not accepting its data policy. The token says "this is
the thing I prepared"; acceptance is recorded separately, on the run request,
by decisions document 0003 A5. Nothing here may be read as consent.
"""

from __future__ import annotations

__all__: list[str] = []
