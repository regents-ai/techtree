# 0013 — Release-copy boundaries and the certification protocol

Status: binding (author rulings relayed by the founder, 2026-08-13).

## 1. Four wording boundaries (apply to ALL public copy and chief reports)

1. **Attestation.** Say "without trusting a Techtree-hosted execution
   claim" / "a third party can verify the integrity of the
   participant-attested proof bundle offline; the execution has not
   been independently reproduced." Never "without trusting us,"
   "independently proven," or "verified by Techtree."
2. **Account.** Say "no Techtree account is required." Never "no
   account required" — a Prime/provider account, API credential, and
   network access for inference, installation, and image retrieval may
   all be needed.
3. **Model.** Say "a pinned subject model runs twice under the same
   configuration, using the participant's inference credentials."
   Never "your own model" — the Campaign pins qwen/qwen3.7-flash. The
   host Hermes operator model (user's ordinary model) and the pinned
   Docker Hermes subject must never be blurred.
4. **Privacy.** Say "Techtree does not upload the user's Episodes,
   Traces, receipts, proof bundles, or Skill proposals. Model
   inference is still sent to the selected model provider under that
   provider's policies." Never "nothing leaves the laptop" /
   "fully offline evaluation" — push=false prevents the additional
   Verifiers platform upload; it does not make remote inference local.

The author's refined product statement (in the founder relay of
2026-08-13) is the authoritative v0.1 description for release copy.

## 2. Three release-copy tests (required, all three repos' public copy)

- **Privacy test:** fail unqualified "nothing leaves the laptop" /
  "nothing is sent anywhere" / "fully offline evaluation"; require
  nearby qualification that model calls go to the inference provider.
- **Account test:** fail "no account required"; permit "no Techtree
  account required."
- **Attestation test:** fail "Techtree verified the execution" /
  "independently verified" / "trustless proof" / "proof of honest
  compute"; permit "participant-attested local execution" /
  "integrity verified" / "offline-verifiable evidence bundle" /
  "not independently reproduced."

## 3. Certification protocol

Pre-paid gate: the static starter prediction must land in 20–27/36
(prefer ≈24), every intended failure explained by the singular
total-vs-distinct defect (at least one repeated character), every
intended success all-distinct or rule-agreeing, and zero wrong/correct
collisions among intended failures. If the static result misses, fix
membership or the singular defect BEFORE spending.

Paid order after static approval:
1. Two-task discovery probe (one all-distinct, one repeated-character)
   with trace evidence: Skill discovered and opened, description
   triggered the right Skill, procedure came from the body not the
   description, all-distinct task succeeds under the incomplete rule,
   repeated-character task exhibits the defect.
2. Full baseline-vs-starter-v1 calibration comparison (baseline 0–2,
   v1 20–27, comparison valid, proof verifies, cost under ceiling).
3. Repeat the calibration comparison from clean run state — the band
   must be stable, not a one-off provider outcome.
4. One complete guided v1→v2 rehearsal along the exact conversational
   path. No automatic retry of the one-turn proposal, ever.

If both certification rehearsals produce poor proposals: revise the
founder Skill improver ONCE before freeze, then rerun the formal
certification. Never select the best of many hidden proposals.

## 4. Hard release gates vs demo-quality targets

Hard gates (must hold): proposal structurally valid; one-turn limit
holds; no answer/membership material copied; second comparison
executes; second proof verifies; tie/loss/invalid outcomes render
honestly. Demo-quality target (strongly desired for the canonical
rehearsal, never a hidden product guarantee): v2 ≥32/36, ≥6 task
uplift, ≤1 regression. The product guarantee is that the one-turn
revision is proposed, scanned, diffed, explicitly approved, evaluated,
and reported honestly — improvement is a calibrated demo target.

## 5. Gate packet contents

**Gate 1 (founder Skill approval):** final bytes + SHA-256 of both
Skills; any diff from the supplied drafts; static calibration table
for all 36 tasks; discovery-probe traces or safe summaries; two paid
calibration run IDs with baseline/v1 scores; guided rehearsal run IDs
with v1/v2 scores; both proof-verification reports; cost/timing
record; known warnings; canonical approval-packet digest.

**Gate 2 (release coordinates):** ReleaseCore and BootstrapRelease
exact bytes + digests; wheel filename + SHA-256; full source and
plugin commits; engine/catalog/Climb/Campaign/DataPolicy/Skill
digests; OCI image-index + platform digests; exact install and Doctor
argv; Hermes tested range; model/provider profile; cost ceilings;
placeholder_release value; cross-repo equality report; fresh-install
transcript; terminal and phone/gateway acceptance results; no-upload
network assertion; rollback commands; approval-packet digest. No
publication or deploy before this packet is approved by exact digest.
