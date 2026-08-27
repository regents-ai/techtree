# 0038 — The public run log

Status: **DRAFT, not binding.** Founder direction 2026-08-27; three
sub-questions answered, the design below awaiting a ruling.

## What the founder asked for

An append-only log of runs that participants publish, shown on the site
newest first, with a detail page per entry showing each task. The stated
purpose: make the site feel real and alive.

Three sub-questions were answered on 2026-08-27.

1. **Identity is only what is signed.** Nothing a submitter writes ever
   appears on the site. A future release may let somebody sign for an EVM
   address or an ENS name; that would be a new attestation kind, not a
   free-text field.
2. **It ships in v0.1.** A feed that arrives after launch is empty during
   the one week it most needs not to be.
3. **A published entry is withdrawn, never deleted.** Withdrawal is an
   appended event.

## Why this is smaller than it looks

The protocol was built for this and then stopped one step short.

- The proof directory is 364 KB and contains **no transcripts**. An
  episode receipt carries digests, task hashes, scores and a
  `trace_digest` — never a prompt or a reply. The raw episodes, all
  11 MB of them, are outside it.
- The DataPolicy the participant already accepts says
  `uplift_report: public`, `aggregate_scores: public`,
  `redacted_trace_projection: public`, and
  `candidate_skill.public_release: required_for_climb`. It says
  `raw_episodes.server_upload: prohibited`, which is exactly what the
  proof directory already excludes. Publishing the bundle is on the
  permitted side of a line this policy already drew.
- `revocation.immutable_published_proofs_remain: true` — the policy
  already contemplates published proofs that stay put. That is the
  founder's withdrawal ruling, written down before it was asked.
- The uplift report already carries `primary_result` (the feed row) and
  `task_deltas` (the detail page, 36 entries with both sides' rewards).
- `PublicationStatus` already exists with `not_requested`, `pending`,
  `published`, `blocked`, `failed`. Today every report is
  `not_requested`, because `_PUBLICATION_ELIGIBLE` is a hardcoded
  `False` whose comment says why: "Upload does not exist: no route, no
  credential, no server."
- The site can verify a submission with nothing added to it. Ed25519
  signing and verification work in this Elixir install through OTP's own
  `:crypto`; no dependency is needed. Confirmed by running it.

## What it is, stated so it cannot drift

**A log, not a leaderboard.** Ordered by arrival and never by score. No
rank, no position number, no "top", no sort control. The Climb's own
manifest says `leaderboard: {enabled: false}` and that does not change.

**Every field shown is derived from bytes that verify.** The identity is
the executor key's fingerprint. The agent is the harness and version the
Campaign pins. The model is the subject model. The scores come from the
signed report. No submitter-supplied string is stored or rendered, which
removes impersonation, spam and moderation as categories rather than
managing them.

**Participant-attested, still.** The site checks that a bundle is
internally consistent and signed by the key it names. It does not
reproduce the run and never will on this path. Every entry says so.

## The four promises this changes

Each is guarded by a test today. None may be quietly edited.

1. **The site accepts nothing.** `TechtreeWeb.MethodSurface` answers
   every mutating method with 405 and "this address publishes and does
   not accept anything", and `router_test.exs` pins the exact route
   list. This gains exactly one write address, named in the plug's own
   documentation.
2. **"Techtree does not upload your results."** On four pages. Becomes:
   nothing is uploaded unless you publish a run yourself, and then only
   the receipt, never the episodes.
3. **The plugin cannot open a network connection.** Left true:
   publishing is a CLI command only. The plugin may offer it as a next
   action for a person to run, and reaches no network itself.
4. **"No leaderboard, and no submission goes anywhere"** in the operator
   Skill. Rewritten to say what the log is and is not.

## What is deliberately not in this release

Raw episodes, transcripts, participant display names, accounts, sorting
by score, comparison between entries, reproduction attestations, and
bundle download. `/proofs/<digest>` download and reproduction
attestations remain techtree-python-8j2.9, for v0.2.
