# Techtree Climb — Agent Handoff

For a new agent working on the three techtree repositories. Everything
here is checkable from the repos themselves; when this document and a
decision doc disagree, the decision doc wins.

## What this project is

Techtree Climb v0.1 ("Techtree Hello World") is the open improvement
and proof network for agent systems — v0.1 is a toy Skill-uplift
demonstration. The public experience is four statements (decision
0019): same agent and same tasks · the Skill was the only change ·
here is the measured difference · here is the local receipt and how to
verify it. Everything else exists to make those four statements true.
Rigor stays internal; the user experience stays almost trivial.

## The three repositories

- **techtree-python** — the CLI and evaluation substrate (Python, uv).
  Campaign kernel (CampaignSpec = scientific contract, ClimbManifest =
  public wrapper), content-addressed catalog, run lifecycle, receipts,
  Ed25519-signed uplift reports, offline proof verification, Rich
  terminal + compact gateway renderers. Also the hub: beads tracker,
  docs/decisions/, docs/spec/, release/ artifacts.
  Gate: `make check` (format, lint, typecheck, tests, generated-check)
  and `make test-integration`.
- **techtree-plugin** (GitHub: regents-ai/techtree-hermes) — the
  Hermes operator plugin. Talks to the CLI ONLY through its JSON
  envelope (never imports techtree Python). Registration performs no
  side effects. Native Hermes user approval gates every install and
  every paid run — there is no model-suppliable confirmation value.
  Ships two Skills: operator (product copy) and skill-improver
  (founder-frozen). Gate: `make check`.
- **techtree-ash** — the read-only website (Elixir/Phoenix/Ash).
  Serves the catalog and content-addressed objects (refuses drifted
  bytes), the agent-first install pages, and the BootstrapRelease
  behind an active-release pointer. GET/HEAD only; a 405 test locks
  the surface. Gate: `PGUSER=sean mix check`. Use the ash-vibez skill.

## Binding sources, in precedence order

1. `docs/decisions/0001–0025` (techtree-python) — every numbered doc
   is binding. Start with 0019 (symmetry/approvals/UX), 0022 (change
   discipline), 0023 (execution contracts), 0024 (agent-first
   onboarding), 0025 (regenerated lineage).
2. `docs/release/contracts/*.md` — self-contained execution contracts
   for every remaining release ticket.
3. `docs/spec/` — the four vendored spec files, with CHECKSUMS.json
   (digest-tested) and INDEX.md mapping tickets → sections →
   decisions. "Spec §9.5" means climb-v0.1-wp9-wp11.md.
4. `docs/spec/closeout-helloworld/` — the founder closeout directive
   and approval phrases.

## The frozen science (do not touch, ever, without a founder ruling)

Campaign b9e3f00c… (regenerated to be digest-identical to what every
certified run executed) · task membership 56f697fb… · engine
874cbae0… · starter Skill tree 596d1368… / file 2aff2707… ·
skill-improver e6bc16c4… · DataPolicy 6c532a43…. Subject model
qwen/qwen3.7-flash via prime (credential PRIME_API_KEY resolved from
an active Prime CLI configuration — an exported shell variable never
reaches a detached run, by design). Reference host for the guided
revision: z-ai/glm-5.2, strict json_schema, one completion, no
retries, no fallback.

## The change discipline (decision 0022 item 4 — read before editing)

After certification, NO behavior change to runs, approvals, proposals,
receipts, proof, host request composition, Skill mounting, guards, or
Campaign configuration without repeating the paid certification.
Copy/docs/test changes are allowed but must leave every scientific
digest byte-identical and pass the full battery. The Gate-2 packet
classifies every commit since certified 1ad6ecf. When in doubt,
classify your change before you make it.

## Non-negotiable invariants

- **Append-only evidence.** Never modify a completed run's files.
  Never rewrite stored bytes to be "truthful". A run this build
  cannot read gets one generic honest error (run_request_unreadable),
  never old-shape detection or a compatibility reader (a narrow
  read-only versioned-reader exception exists for v0.2 — decision
  0022 item 3).
- **One generation request** per guided proposal at the provider
  boundary; zero transport retries; zero repairs; an unusable
  proposal never silently retries.
- **The model never approves its own action.** Approval lives at the
  CLI y/N (or explicit --yes) and Hermes's native approval surface;
  one run.approved audit event records it.
- **Nothing uploads.** No receipt, episode, trace, proof, or Skill
  proposal leaves the machine; push=false everywhere; the website is
  read-only.
- **Secrets.** Never read .env. PRIME_API_KEY is never stored,
  logged, echoed, or passed through arguments. The worker environment
  scrub (runs/launcher.py) must never be loosened.
- **Hard cutover style.** No fallbacks, no compatibility branches, no
  shims, no legacy-shape policing (user's global rules). Delete dead
  code rather than preserve it.

## Copy rules (customer-facing text)

Plain language only — no internals jargon (no "enum", "schema",
"fallback", "server-rendered"...). Binding wording boundaries
(decision 0013): "no Techtree account" (never "no account");
participant-attested, never independently-verified; the score band
("roughly two-thirds", 20–27/36), never a promised exact score;
qualified privacy (model calls go to the provider); toy/synthetic
framing. Never claim: a price estimate, a running cost total, a
time-bounded run, a certified phone journey, or measured uplift from
the guided revision. Copy-guard test suites in all three repos
enforce most of this — extend them when adding claim surfaces.
Guided revision is single-SKILL.md in v0.1 (decision 0023 §4).

## Working practices

- Task tracking: beads (`bd`) — DB lives in techtree-python. One
  ticket per work item; note evidence on tickets; close only when the
  battery is green.
- Worker agents never run git; the orchestrating session commits per
  ticket after independently re-running the gates. Never push unless
  the founder explicitly asks. All three repos push to private
  regents-ai remotes (techtree-python, techtree-hermes, techtree-ash).
- Certification evidence lives OUTSIDE the repos at
  techtree-climb/certification-evidence/ (durable, local-only, never
  uploaded, never committed — run dirs contain task answers). Verify
  proofs with `uv run techtree proof verify <run-dir>/proof`.
- Money: estimate before any paid run; programme cap USD 10.00
  (decision 0025), ~2.50 spent; USD 0.30 ceiling per comparison; a
  hard-stop violation stops the sequence — never retry a paid
  outcome.
- Python: always uv. Ash: ash-vibez skill, idiomatic functional
  Elixir. Postgres: PGUSER=sean.

## Release state (as of 2026-08-14)

Gate 1 (founder Skill approval) is APPROVED — record in
release/founder-approvals/, packet + append-only addendum in
release/. The certified lineage was regenerated (decision 0025) so
the shipped Campaign is digest-identical to what certification ran,
re-certified by three fresh product-path runs. Wheel built
reproducibly and inspected; plugin release candidate recorded
(release/plugin-release-candidate.json); website release
infrastructure (content-addressed starter serving, placeholder
rejection, pointer rollback) built and rehearsed. Hermes ≥0.20.1
supplies `plugins install --ref <40-char SHA>` — the pinned install.

Remaining v0.1 work: docs/v0.1-remaining-tickets.md (the open tickets
verbatim plus their contracts). Nothing publishes, tags, deploys, or
flips placeholder_release before the founder's exact
`APPROVE CLIMB V0.1 RELEASE` phrase — and after approval, any changed
byte invalidates it.

## Known sharp edges

- The wheel intentionally carries the certified placeholder
  ReleaseCore; concrete coordinates live in the BootstrapRelease
  (packet explains the split).
- uv will happily install onto an unsupported Python (observed
  3.14.3 vs declared <3.14) — pin 3.12 for supported journeys.
- `doctor --for-evaluation` is truthful about credentials now, but a
  present-yet-revoked Prime key still passes shape checks and fails
  at first model call (documented limitation).
- The declared 600-second run timeout is enforced by nothing — the
  declared value is faithful to certification; claiming enforcement
  anywhere is a copy-guard violation.
- The evidence fixture rules (decision 0015): committed fixtures are
  sanitized conformance assets; never commit live run evidence (it
  contains the hidden answer key).
