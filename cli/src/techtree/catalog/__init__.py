"""The embedded catalog: what a build ships and what those objects resolve to.

Spec section 14, decisions 0003 A2/A6/A7.

Two modules divide the work:

:mod:`techtree.catalog.repository`
    Bytes and addresses. Reading the generated index, turning a public
    reference into a file, recomputing the digest of everything it loads, and
    refusing a path that leaves the catalog root.

:mod:`techtree.catalog.service`
    Meaning. Assembling the Climb, Campaign, DataPolicy, publisher validation
    receipt, and normalized evidence into one cross-checked graph, summarizing
    it for a reader, and answering whether this host could actually run it.

The packaged catalog of this build is valid and empty. Decisions document 0003
A2 forbids shipping hand-authored placeholder science, so the real
``hello-world-climb@1`` graph arrives with the generation chain and the graph
logic is exercised against a complete synthetic fixture instead.
"""

from __future__ import annotations

__all__: list[str] = []
