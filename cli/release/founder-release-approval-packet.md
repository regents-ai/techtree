# Founder Release Approval Packet — Climb v0.1

Status: FINAL, awaiting the founder's Gate-2 approval phrase
(`docs/spec/closeout-helloworld/FOUNDER_APPROVAL_PHRASES.md`, "Final
Release Approval"). Nothing has been published, tagged, deployed or
activated. The canonical packet digest is the sha256 of this file's
bytes as committed.

Gate 1 (founder Skill approval) is APPROVED; its record is in
`release/founder-approvals/` with an append-only addendum.

## §1 The exact bytes this approval covers

| Coordinate | Value |
| --- | --- |
| Release id | `climb-v0.1.0` |
| ReleaseCore | `sha256:c037f4578134185cc22717908bce58749bbb5086536fc955881a2b831abd8530` |
| CLI wheel | `techtree-0.1.0-py3-none-any.whl`, `sha256:90a543ca7353e38b4fa3d8fb16a2c190d59308fc2c84222141ce8f38cc37b49a` |
| Wheel built from | techtree-python `8d9068cfca818d3ae39f7ea130a90f596b33d4f5` |
| Plugin commit | techtree-hermes `cc387bd3340d574924e93d216aaa1ab99df9d8c0` |
| BootstrapRelease | `sha256:5cdc9f530493e2e37b722d009e772c74bf0804fcc388f20ee17915cb900fe504` |
| Published install command | `uv tool install --python 3.12 techtree==0.1.0` |
| Published plugin command | `hermes plugins install regents-ai/techtree-hermes --ref cc387bd3… --enable` |

The wheel was built twice, from two independent clean clones of the
frozen commit, and both produced byte-identical output. The commit
stamped inside the artifact reads back as the frozen commit; the build
hook asks git which commit it is packaging and refuses to stamp
anything else, so a wheel cannot claim a commit it was not built from.

techtree-python has moved one commit past the freeze, to
`425372ce62db7b442a722f6ea8468fac27fd993c`. That commit touches only
files under `release/`, which are records and are not packaged. No
byte inside the wheel changed. Rebuilding at the later commit would
produce a different stamp and therefore a different wheel, which is
why the coordinate above names the build commit and not the tip.

## §2 What was checked, and by whom

Every figure below was re-observed against the frozen artifacts, not
transcribed from the previous revision of a record.

| Check | Result |
| --- | --- |
| Cross-repository gate (`tools/verify_release_core.py`) | 26 of 26 |
| `make check` (techtree-python) | 3015 passed, 1 skipped; generated artifacts match |
| `make check-plugin` | 850 passed; two typecheck passes clean; plugin doctor 10/10 |
| `make check` (techtree-plugin) | format, lint and types clean |
| `PGUSER=… mix check` (techtree-ash) | 3 doctests, 295 tests, 0 failures |
| Wheel inspection | 19 of 19, no findings |
| Fresh isolated install, published command | Python 3.12.13, health check passes |
| Certification proofs | 339 checks each, all passing, verified again from stored bytes |

Two of the twenty-six cross-repository checks did not exist a day ago
and both were added because the gate could pass while something real
was wrong. One hashes the wheel it is handed and compares it to the
digest the bootstrap document publishes — the number a participant's
installer checks against, which nothing had ever verified. The other
refuses a release whose install command and stated Python requirement
disagree.

## §3 The frozen science

Unchanged, and not re-certified: decision 0033 rules that v0.1 ships
exactly the certified lineage.

Campaign `ad393bc0…` · task membership `56f697fb…` · engine
`874cbae0…` · starter Skill tree `596d1368…` · skill-improver
`e6bc16c4…` · DataPolicy `6c532a43…`. Subject `qwen/qwen3.7-flash`
via Prime.

`release/product-claim-evidence-matrix.md` maps every sentence
intended for the public to the evidence behind it, and was rebuilt
against this lineage for this packet. It previously anchored on the
first certification, which two Campaign regenerations had superseded.

## §4 What the evidence does not support

Stated here rather than left to be discovered.

- **No measured uplift may be claimed.** Under this Campaign the
  unchanged Skill scored 24, 23 and 23 of 36 across three executions
  of an identical arm. The one measured improvement is +1, inside
  that spread. The same frozen bytes under the earlier lineage moved
  the score by exactly zero. Public copy states the calibrated
  20–27/36 band and never an exact score.
- **The result is participant-attested, never independently
  reproduced.** Nobody else has run this comparison and no platform
  witnessed it.
- **Both sides provably used the same model name, not provably the
  same model build.** The provider publishes no immutable build
  identifier. No mismatch was found.
- **The image claim is narrower than it was.** The final runs' receipts
  leave the platform field empty, so what is proven is the same image
  index digest across all 288 episodes, not the same platform-specific
  digest. Recorded as a gap rather than smoothed over.
- **Costs are not billed amounts.** Every run records cost as
  unavailable on both sides. The dollar figures in the matrix are
  worked out from recorded token counts against a dated rate card, and
  the matrix says so.
- **The declared 600-second run timeout is enforced by nothing.** The
  declared value is faithful to certification; claiming enforcement
  anywhere is a copy-guard violation.
- **"Proof grade" names two different things.** The shipped Climb's
  publication grade is `development_only`; the local proof's integrity
  grade is `P1`. Both are customer-visible and they mean different
  things. Nothing false is said; the collision is a v0.2 naming fix.
- **The base image tag has moved upstream, and it does not reach us.**
  `python:3.11-slim` no longer resolves to the index the Campaign was
  validated against; the preflight drift check found this during the
  freeze. It cannot affect a participant, because the Campaign pins the
  image by digest — `python@sha256:90744cff…` — not by tag, and that
  digest still resolves at the registry (confirmed, HTTP 200). Anyone
  reproducing the validation by tag on a clean machine would now get
  different bytes; anyone running the Climb gets the certified ones.

## §5 Current state of the world

- **Nothing is published.** All three repositories are private. The
  wheel is not on any package index. The plugin commit is not tagged.
- **Nothing is active on the site.** Asked directly of the local
  database: the stable channel is empty, the development channel holds
  six placeholder entries with a zero plugin commit, and the real
  candidate has never been imported. It exists only as staged files.
  This is the database on the founder's machine; the deployed site has
  its own, which this packet makes no claim about. The post-publish
  smoke check settles that, after approval.

## §6 Everything that changed since certification

`release/post-certification-change-classification.json` classifies all
93 commits and 438 file changes since certified `1ad6ecf`, checked
entry by entry against git rather than sampled. Nothing in the range
touches the certified scientific surface.

Two changes in the freeze range sit inside areas the change discipline
protects — Skill preparation and the proof command — and each is
exempted by name with its reason recorded. In the proof case the
envelope the plugin reads as a contract lies outside every changed
region, verified two ways.

## §7 What was found and fixed on the way to this packet

Recorded because a packet that lists only successes is not evidence.

- The approval screen told every participant "the baseline runs first
  and the candidate second". This Campaign runs both sides at once. A
  false statement about how a controlled comparison was controlled,
  made where someone decides to spend money. The sentence is now
  derived from the Campaign, and a census guard stops any other copy
  in the tree ordering the two sides.
- The result screen led with "24 WIN / 0 LOSS / 12 TIE" — a clean
  sweep — while concealing that twelve tasks were still failing,
  because in a Skill-insertion comparison a tie means both sides
  failed.
- The cross-repository gate had never hashed the wheel it was handed.
- A guided revision that produced nothing still spent the
  participant's single attempt, and reported "the host model could not
  answer" when the host had answered and charged.
- A size limit of 3500 bytes, from no specification and no host
  documentation, governed nearly every answer the plugin gave — not
  just phones — and destroyed whole results at that threshold.
- The claims ledger contained five errors of fact, not merely stale
  citations.

## §8 Not covered by this approval

- The agent-first Hermes journey has not been recorded from these
  packaged bytes. The path has been walked before, and nine defects
  found that way are fixed, but no record exists for this build.
  It costs money and needs the founder's separate authorization.
- No paid run was made during the freeze. Programme cap USD 15.00.
- The public-coordinate smoke check runs only after publication.
- **The engine pin has a shelf life.** The bundle pins verifiers
  `0.3.1.dev21` at an exact commit. Probed during the freeze: the
  released `v0.3.1` tag of the same library fails 10 of the 23 engine
  contract checks, because the module the engine's install path imports
  no longer exists there. Nothing to fix for this release — the pin is
  exact and the certification ran against it, and this is the pin doing
  its job — but the upstream API is still moving, and moving with it
  costs a new certification. Tracked as techtree-python-0a8.

## §9 The approval

Nothing publishes, tags, deploys or activates without the exact phrase
in `docs/spec/closeout-helloworld/FOUNDER_APPROVAL_PHRASES.md`. After
approval, any changed byte invalidates it: the wheel digest, the
plugin commit and the bootstrap digest are what the phrase authorizes,
and a rebuild produces different bytes.

Recommended order, which differs from the reviewers' in two places
that matter: configure branch protection **before** making the
repositories public, not after, so there is no window in which a
default branch is exposed and unprotected; and treat publishing the
wheel as the point of no return, because a version number on a public
index is spent permanently and cannot be reissued with different
bytes. Everything falsifiable belongs before that step.
