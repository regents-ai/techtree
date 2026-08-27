# Founder Release Approval Packet — Climb v0.1

Status: FINAL, awaiting the founder's Gate-2 approval phrase
(`docs/spec/closeout-helloworld/FOUNDER_APPROVAL_PHRASES.md`, "Final
Release Approval"). Nothing has been published, tagged, deployed or
activated. The canonical packet digest is the sha256 of this file's
bytes as committed.

Gate 1 (founder Skill approval) is APPROVED; its record is in
`release/founder-approvals/` with an append-only addendum. §9 below
names the one thing that approval no longer covers.

This packet supersedes the edition of 2026-08-26. Everything in it was
re-observed after the evaluation engine moved to a released upstream
version; nothing is carried forward from the previous edition.

## §1 The exact bytes this approval covers

| Coordinate | Value |
| --- | --- |
| Release id | `climb-v0.1.0` |
| ReleaseCore | `sha256:bef3b9d4c987209c0fb580ed5eb349c096dca328efd7b0867f5a04d7bb763db4` |
| CLI wheel | `techtree-0.1.0-py3-none-any.whl`, `sha256:e486b3eaa477455566035f9b210db824e1bdda765b1ade0f44891da6b2c855c2` |
| Wheel built from | techtree-python `5d793b699ce75779269a67a7c2f0d9cc9c6b79de` |
| Plugin commit | techtree-hermes `6ef36a358ec0bb6079a6c9991cb8563acf65e91d` |
| Published install command | `uv tool install --python 3.12 techtree==0.1.0` |
| Published plugin command | `hermes plugins install regents-ai/techtree-hermes --ref 6ef36a35… --enable` |

The wheel was built twice, from two independent clean clones of the
frozen commit, and both produced byte-identical output. The commit
stamped inside the artifact reads back as the frozen commit; the build
hook asks git which commit it is packaging and refuses to stamp
anything else, so a wheel cannot claim a commit it was not built from.

techtree-python has moved past the freeze. Every commit since touches
only `release/`, `.beads/` and documentation, none of which is
packaged, so no byte inside the wheel changed. The coordinate above
names the build commit and not the tip, deliberately: rebuilding at the
tip would produce a different stamp and therefore a different wheel.

## §2 The science this release ships

The engine moved, under the founder's directive of 2026-08-26, from a
pre-release development build of Verifiers to the released `v0.3.1` at
commit `b2e4e8157783b2c0dffc7821044c87f29f1c3ccf`. That is the single
largest change since the previous packet and everything below follows
from it.

| Coordinate | Value |
| --- | --- |
| Campaign | `sha256:ebf029ab…` |
| Climb | `sha256:a3a5e9c5…` |
| Catalog | `sha256:10a7fcc5…` |
| Engine bundle | `sha256:29b1bbb8…` |
| Task membership | `sha256:56f697fb…` |
| Starter Skill tree | `sha256:596d1368…` |
| skill-improver | `sha256:d5a381be…` |
| DataPolicy | `sha256:6c532a43…` |

Subject `qwen/qwen3.7-flash` via Prime. Decision 0033 keeps Prime as
the only serving provider for v0.1.

**The measurement did not move.** The two Campaign documents were
flattened to JSON pointers and compared field by field: exactly two
fields differ, and both are names of the engine that was moved. All 36
committed task hashes are byte-identical and in the same order, the
membership digest is the same value, and recomputing it from the hashes
reproduces it. Budgets, execution contract, subject model, sampling,
runtime image digests, mutation contract and scoring contract are
unchanged. `release/certified-scientific-fingerprint.json` records the
method and the result.

**One coordinate moved for a reason worth knowing.** The taskset
package's digest covers its source tree, and the only file in that tree
that changed is one module whose entire diff is two sentences of
documentation re-pointed at the new engine commit. That docstring alone
carries the package digest, and the package digest is named inside the
Campaign. Nothing measured changed. It is recorded rather than left to
be discovered.

## §3 What was checked, and how

Every figure below was re-observed against the frozen artifacts.

| Check | Result |
| --- | --- |
| Cross-repository gate (`tools/verify_release_core.py`) | 26 of 26 |
| `make check` (techtree-python) | 3019 passed, 1 skipped; generated artifacts match |
| `make check-plugin` | 857 passed; plugin doctor 10 of 10 |
| `make check` (techtree-plugin) | format, lint and types clean |
| `mix check` (techtree-ash) | 3 doctests, 305 tests, 0 failures |
| Wheel inspection | 19 of 19, no findings |
| Fresh isolated install, interpreter pinned | Python 3.12.13, health check passes |
| Certification proofs | 339 checks each, all passing, verified from stored bytes |

Two of the twenty-six cross-repository checks hash the wheel and read
its stamp. They are what would catch a bootstrap document naming a
wheel that no longer exists, and both pass against these bytes.

## §4 The runs this release rests on

Four runs exist against the shipping Campaign. A filesystem-wide search
over 294 stored run directories found exactly these, and every proof
was verified offline by the chief: 339 checks each, all passing,
nothing fetched.

| Run | Score | What it is |
| --- | --- | --- |
| `run_c4758ddb…` | 23 of 36 | certification |
| `run_55159aeb…` | 23 of 36 | certification |
| `run_8f89ae9d…` | 24 of 36 | certification |
| `run_b3e25a43…` | 23 of 36 | the founder's own walkthrough through Hermes |

The onboarding acceptance of 2026-08-27 produced two more, both
verified: `run_618a27f7…` reproduced the certified result exactly
(0.000 → 0.639, 23 wins, no losses), and `run_4584be6d…` was the
guided revision's second comparison (0.639 → 0.667, one win).

**A correction, recorded because a packet that hides its own errors is
not evidence.** An earlier record in this project stated the engine was
re-certified by "five runs scoring 23, 23, 24, 23, 23". That was wrong.
It came from a conversation summary rather than a run directory and was
repeated without being checked. Three certification executions exist,
scoring 23, 23 and 24.

## §5 What the evidence does not support

- **No measured uplift may be claimed.** Three certification executions
  under this Campaign scored 23, 23 and 24 of 36 — a spread of one
  task. The guided revision's own second comparison moved the score by
  one task, which sits inside that spread. Public copy states the
  calibrated 20–27/36 band and never an exact score.
- **The result is participant-attested and has never been
  independently reproduced.** Nobody else has run this comparison and
  no platform witnessed it.
- **Both sides provably used the same model name, not provably the same
  model build.** The provider publishes no immutable build identifier.
  No mismatch was found.
- **Costs are not billed amounts.** Every run records cost as
  unavailable on both sides. Dollar figures anywhere in these records
  are worked out from recorded token counts against a dated rate card,
  and say so.
- **The declared 600-second run timeout is enforced by nothing.** The
  declared value is faithful to certification; claiming enforcement
  anywhere is a copy-guard violation.
- **"Proof grade" names two different things.** The shipped Climb's
  publication grade is `development_only`; the local proof's integrity
  grade is `P1`. Both are customer-visible and they mean different
  things. Nothing false is said; the collision is a v0.2 naming fix.
- **The base image tag has moved upstream and does not reach us.**
  `python:3.11-slim` no longer resolves to the index the Campaign was
  validated against. It cannot affect a participant, because the
  Campaign pins the image by digest and that digest still resolves.

## §6 Everything that changed since certification

`release/post-certification-change-classification.json` classifies all
**121 commits and 663 file changes** since certified `1ad6ecf`, checked
against git commit by commit and path by path rather than sampled.
Verdict: PASS. Every scientific change in the range is sanctioned and
certified; every non-scientific change was decided on its diff.

The engine move is its own scientific entry, certified by the three
certification runs, with the founder walkthrough cited separately as
the different thing it is. Ten diffs inside declared scientific areas
were read individually and exempted by name with their reasons.

One exemption is flagged for the founder's eye rather than buried:
`uplift/context.py` changes two published sentences in the instruction
text handed to the revising agent, because decision 0036 made the old
wording untrue. Nothing measured moves, but it is the only
non-scientific classification in the range that changes the bytes of a
shipped artifact inside a scientific area after the last certification
run.

## §7 The onboarding acceptance, and what it found

The agent-first journey was walked from these packaged bytes on
2026-08-27 (`release/acceptance/onboarding-e2e.json`). Verdict:
**conditional pass**. Spend USD 0.2189 of 1.50 authorised; every leg
estimated before it ran, every leg inside its 0.30 ceiling, nothing
retried.

Nine of the twelve contract acceptance points are established. Two are
partly established: whether a live Hermes agent given the pasted prompt
actually carries the journey out could not be tested from a throwaway
Hermes home, and the next-step chain loops rather than arriving at
Hello World. One cannot close before publication: the pinned GitHub
release does not exist yet.

**The guided revision completed end to end for the first time in this
programme.**

It found eleven defects. One blocked Gate 2 and is fixed: the operator
Skill — the document a Hermes agent loads before it touches any
Techtree tool — stated without qualification that this build stops
before preparing a comparison, that the release coordinates have not
been chosen, that it will not install Techtree, and that there is
nothing to fix locally. Every one was true of the placeholder build
that preceded this one and false of this candidate. A guard now holds
each claim as a claim rather than as a phrasing.

Nine remain open and are ticketed. The four worth naming: the install
guide promises the security scan will show five findings and it shows
six, the sixth a HIGH flag on the page that explains the other five;
the evaluation engine can never reach a verified state, so the main
onboarding surface offers a next step nobody can clear; the guided
introduction is lost by the restart the guide itself instructs; and
agent-driven calls default to the bounded chat shape, silently dropping
the record fields.

The operator of that journey was an acceptance worker, not the founder.
It contaminated its own test by putting the local bin directory on the
path, briefly ran an older globally-installed Techtree instead of the
candidate, caught it, corrected it and disclosed it in the record.

## §8 Current state of the world

- **Nothing is published.** All three repositories are private. No tags
  exist in any of them. `techtree` returns 404 on PyPI.
- **Neither frozen commit exists on the remote.** GitHub answers 422
  for both `5d793b69` and `6ef36a35`. The freeze is local. The
  published plugin command therefore names a commit nobody can fetch
  today, which makes pushing the frozen commits the first step after
  approval and before anything is made public.
- **The founder's local site database has an active stable release with
  superseded coordinates** — CLI 0.1.0 against plugin commit
  `cc387bd3`, and an active development catalog at the
  pre-recertification `ae300ef6`. This is the database on the founder's
  machine and reaches nobody. Nothing here has been activated or
  deactivated: that is a Gate-2 action and it is the founder's.

## §9 What this approval must decide, beyond the phrase

**The shipping skill-improver Skill is not the one Gate 1 approved.**
Gate 1 approved `sha256:e6bc16c4…`. The release ships
`sha256:d5a381be…`. The difference is one line: the Skill told the
revising model that the improvement context omits "secrets", and
decision 0036 deleted every secret-shaped-string detector from the
project, so that word had to go. The change makes the Skill more honest
and follows the founder's own binding ruling — but the bytes are not
the approved bytes, and extending the approval to them is a founder
decision, not a chief's. The starter Skill's tree digest is unchanged
and still matches what Gate 1 approved.

## §10 Not covered by this approval

- The public-coordinate smoke check runs only after publication.
- The live-Hermes half of the onboarding journey. The founder's own
  walkthrough of 2026-08-27 is the record for it, taken on a prior
  build of the same lineage.
- Nine open defects from the onboarding journey, four of them P1.
- The public run log (`techtree-python-4q8`), which the founder has
  directed be built on this frozen base after approval.

## §11 The approval

Nothing publishes, tags, deploys or activates without the exact phrase
in `docs/spec/closeout-helloworld/FOUNDER_APPROVAL_PHRASES.md`. After
approval, any changed byte invalidates it: the wheel digest and the
plugin commit are what the phrase authorizes, and a rebuild produces
different bytes.

Recommended order:

1. **Push the frozen commits.** Until then the published plugin command
   names a commit that cannot be fetched.
2. Make the repositories public. Branch protection is not configured,
   by founder ruling of 2026-08-26.
3. Activate the release on the site.
4. **Publish the wheel last.** A version number on a public index is
   spent permanently and cannot be reissued with different bytes, so
   everything falsifiable belongs before this step.
5. Run the post-publish smoke check (`techtree-python-rlf`).
