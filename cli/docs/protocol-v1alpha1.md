# Protocol v1alpha1

Status: partially written. The full document is filled in by the work packages
that land the subsystems it describes; see section 9.8 of
`docs/spec/climb-v0.1-wp0-wp5.md` for its required contents.

The one section recorded so far is the local proof grade, because WP6-proto
(decisions 0005, amendment 4) fixes what `proof_grade: P1` is allowed to mean
before any code is written that produces one.

---

## Local proof semantics

Spec `docs/spec/climb-v0.1-wp6-wp8.md` §3.4. Decisions
`docs/decisions/0005-wp6-wp8-protocol-amendments-and-roadmap.md`, amendment 4.

`proof_grade` is already a literal on `UpliftReport`. The conditions below were
recorded before anything signed anything, so that the grade could not acquire a
looser meaning by being implemented first and defined afterwards. WP7 activated
the Ed25519 primitives against them: `techtree.identity` owns the one local key
a machine has, every receipt and every report travels in a signed
`ObjectEnvelope`, and `techtree.receipts.bundle` evaluates each condition below
by name before a report is entitled to the grade.

### When P1 is permitted

A real local report may use:

```text
proof_grade: P1
```

only when:

```text
all referenced artifact digests verify
all EpisodeReceipts are wrapped in signed ObjectEnvelopes
the UpliftReport is wrapped in a signed ObjectEnvelope
the local public key is included in the bundle
the comparison is controlled or controlled_with_warnings
score status is valid
```

Every one of those is a condition on stored bytes. None of them is satisfied by
a claim in a document about itself, and none of them is taken on trust: the
conditions are evaluated a second time, from the written bytes, by
`techtree.receipts.verify.verify_local_bundle`, and a run whose proof does not
re-establish them does not record its report as a result. `techtree proof
verify` runs the same check offline on any bundle.

### What P1 means

The key is self-issued and local in this push. P1 therefore means:

```text
integrity-bound, participant-attested local execution
```

It does not mean independent or platform-witnessed execution. A P1 report says
that the participant's own key vouches for bytes that verify against each
other — nothing about who ran them, and nothing a third party has checked.

A run that cannot meet every condition above does not carry P1. The fake
executor's reports carry `proof_grade: development_only`, and a development-only
report can never present itself as evidence.

### What does not enter the protocol for this

Rich terminal output is a view, not scientific evidence (§3.5). No terminal
markup, colour, emoji, prose, or channel-specific formatting enters
`EpisodeReceipt` or `UpliftReport`. Presentation models and builders are
separate objects, delivered under WP7.
