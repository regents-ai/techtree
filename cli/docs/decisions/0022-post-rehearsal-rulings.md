# 0022 — Post-rehearsal author rulings, founder-confirmed

Status: binding (author rulings relayed by the founder; founder
confirmed all five, 2026-08-14). The canonical rehearsal had already
completed, within every condition these rulings set, when they were
confirmed.

## 1. No run-state schema collapse in v0.1

The twelve-to-five durable run-state collapse does NOT happen before
the v0.1 release. This amends decision 0019's durable-states item:
the five states (prepared, running, completed, failed, cancelled) are
the PUBLIC PROJECTION users see; the existing detailed internal state
machine — implemented, tested, and certified by the canonical runs —
ships unchanged. Rationale: certify → change lifecycle → ship a
different implementation either invalidates the certification or
forces another paid run. The real collapse is a v0.2 item with its
own certification. Ticket ndq.3.41 is rescoped to verifying the
public projection only.

## 2. Deferred multi-file Skill items — named and bounded

The two deferrals (ticket ndq.3.42) are, precisely:
(a) skills/starter.py _stage_document fetches only a single SKILL.md;
multi-file starters need an archive-format decision at
starter_skill_object_url; (b) uplift/source.py VerifiedSourceSkill
verifies every file but exposes only entrypoint_text to the host, so
a guided revision can never touch references/ or templates/ content.
Both are capability gaps, not integrity gaps: full-tree hashing,
per-file mounting, root-digest comparison, and the
exactly-one-component-changed check exist and are tested
(tests/integration/test_multi_file_skill.py; the v1-vs-v2 run's
records carry per-file digests). Because the improver can only edit
the entrypoint in v0.1, auxiliary files are always inherited
byte-identical from the parent — nothing the deferral omits can
silently change. Deferring is therefore safe under the author's
criterion (UX/capability yes, hashing/mounting/comparison no).

## 3. Versioned historical run readers — v0.2, read-only scope

The fresh pre-committed source run is ratified (all conditions met:
one run, committed before outcome, used regardless of score, no
rerun, all prior bytes preserved, deviation disclosed in the Gate-1
packet §0). Standing rule going forward: "no compatibility branch"
is NOT a permanent architectural statement for stored evidence. A
future versioned reader may parse old run schemas as written,
project them into current internal semantics, and mark the
projection legacy — provided it NEVER rewrites source artifacts and
never revives old shapes in live write paths. Founder explicitly
confirmed this narrow exception to the global hard rules. v0.2
ticket opened; scope is strictly reading.

## 4. Post-rehearsal change discipline

No behavior-changing edits to runs, approvals, proposals, receipts,
proof, host request composition, Skill mounting, guards, or Campaign
configuration after the canonical rehearsal without repeating that
certification. Copy/documentation-only changes (including the
ndq.3.43 error-wording fix, explicitly sanctioned) may land only
when every scientific digest and all guided-flow code remain
byte-identical, and must be followed by the full acceptance battery:
test suites, generated-file drift checks, fresh wheel install,
plugin doctor, clean terminal journey, clean gateway journey, and
proof verification against the existing canonical bundles. The
Gate-2 release packet MUST carry a post-rehearsal change
classification: every change since certification, each marked
scientific (requires re-certification) or non-scientific (battery
only).

## 5. Proof-grade display — verified as-built

The proof grade is read from the verified report
(presentation/build.py), never hardcoded into comparison labels, and
the result display attaches the attestation caveat ("integrity-bound,
participant-attested local execution") plus a weaker-attestation
warning when verification is absent. No change required; attested in
the Gate-1 packet.

## Ratified without action

Native Hermes approval replacing tokens; the explicit_cli_review
naming; symmetric insertion/replacement behavior; conservative
iteration labeling (no manufactured global sequence numbers in
receipts); the one fixed 32,768-token GLM 5.2 attempt. The
request-digest recomputation after the fresh source run happened as
required: computed before the call, matched the sent request exactly.
