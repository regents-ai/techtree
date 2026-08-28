# Protocol v1alpha1

Status: partially written. The full document is filled in by the work packages
that land the subsystems it describes; see section 9.8 of
`docs/spec/climb-v0.1-wp0-wp5.md` for its required contents.

Two sections are recorded so far: the local proof grade, because WP6-proto
(decisions 0005, amendment 4) fixes what `proof_grade: P1` is allowed to mean
before any code is written that produces one, and the mutation kinds, because
which comparisons a Campaign can express is what decides which of them can be
public.

---

## Mutation kinds

Spec `docs/spec/climb-v0.1-wp6-wp8.md` §3.1 and §7.19. Decisions
`docs/decisions/0005-wp6-wp8-protocol-amendments-and-roadmap.md`, amendment 1.

A `MutationContract` names one of two shapes, and the shape decides what the
comparison's baseline carries.

```text
skill_insertion     baseline carries no Skill, candidate carries one
skill_replacement   baseline carries the Skill being revised, candidate carries
                    its replacement, and the two differ
```

Both are enforced in three places that do not consult each other: the
`CampaignSpec` validator, the manifest builder, and the controlled comparison.

### A replacement is local

`ClimbManifest.candidate_policy.required_mutation` is `skill_insertion` and
nothing else, and a resolved Climb refuses to exist unless its Campaign's
mutation kind matches. So no public Climb wraps a Skill replacement, and a
replacement Campaign is derived locally from a run that already finished:

```text
purpose, taskset, membership, validation receipt, environment, model,
sampling, harness, runtime, scoring, evidence, budgets and DataPolicy
propagate from the source Campaign unchanged

mutation.kind becomes skill_replacement, bounded at exactly one Skill
the subject harness carries the Skill the source run evaluated
public_context is null

the derived Campaign therefore has a new digest
```

The Skill the baseline carries is named by content address, taken from the
source run's own verified inputs. A directory that has changed since that run
cannot become the baseline a later report claims to have measured against.

### What a replacement does not change

Nothing about proof, rights, or publication is relaxed because a comparison is
local. A replacement run signs its receipts and its report, writes and verifies
its own proof bundle, states the same P1 wording, asks for the DataPolicy to be
accepted again before it starts, and sends nowhere until somebody publishes it.

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
