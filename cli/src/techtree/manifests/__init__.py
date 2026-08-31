"""Campaign-derived experiment variants and the comparison between them.

Spec PR6 §6.3.

A Campaign states what is to be measured. It does not state which side of a
comparison a particular execution is. Two modules turn one into the other:

:mod:`techtree.manifests.builder`
    Derivation. Copying the Campaign's scientific configuration unchanged into
    a baseline variant carrying no skill and a candidate variant carrying
    exactly one, and sealing each with the digest of its configuration.

:mod:`techtree.manifests.compare`
    Control. Requiring the structural invariants outright, then diffing the two
    configurations down to their leaves as RFC 6901 JSON Pointers, and
    reporting whether the only place they disagree is the one place the
    Campaign's mutation contract permits.

Together they are the reason an uplift number means something: the candidate
run and the baseline run are provably the same experiment apart from the skill
that was inserted, and the proof is a list of pointers anyone can re-derive
from the two documents.
"""

from __future__ import annotations

from techtree.manifests.builder import (
    build_baseline_manifest,
    build_candidate_manifest,
    build_experiment_configuration,
)
from techtree.manifests.compare import compare_manifests

__all__ = [
    "build_baseline_manifest",
    "build_candidate_manifest",
    "build_experiment_configuration",
    "compare_manifests",
]
