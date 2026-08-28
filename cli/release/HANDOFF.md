# Handoff — finishing Climb v0.1

Written 2026-08-28 by the outgoing chief-of-staff session, for whoever
finishes the release. It is written to be read cold: nothing here assumes
you saw the conversation it came from.

Read `docs/decisions/` first. It is binding, and where a document and a
decision disagree, the decision wins. The ones that matter most for what
is left are **0035** (proof-of-concept framing), **0036** (no secret
scrubbing), **0037** (the published example result) and **0038** (the
public run log — the whole feature, its wire contract and the founder's
ruling that it ships inside v0.1).

## 1. Where the three repositories stand

| Repository | HEAD | State |
| --- | --- | --- |
| `techtree-python` | `854c586` | clean; this is the candidate freeze commit |
| `techtree-plugin` | `1050d18` | clean |
| `techtree-ash` | `2d8114d` | **shared** — another session has uncommitted front-page work in it |

**Nothing is published.** All three GitHub repositories are private, no
tags exist, `techtree` returns 404 on PyPI, and **neither frozen commit
exists on any remote**. That last one is the first step after approval:
until the commits are pushed, the published plugin install command names
a commit nobody can fetch.

## 2. The coordinates this release is built on

```
freeze commit   854c586f5e53efe885627e731e8ef37af83f70a1   (techtree-python)
wheel           beaa12e53799c2203556e9c8fac092a317e9f71ea0c843b39dd139c3994c131c
plugin commit   1050d18…  (was a8f9f7c; moved by the FAQ rewording — RE-PIN IT)
ReleaseCore     sha256:c92b602e8097a6498c49f52587a486f46f2cfd0a7adfe5cb082c5e98527e40a1
engine          sha256:29b1bbb8…   catalog  sha256:10a7fcc5…
campaign        sha256:ebf029ab…   climb    sha256:a3a5e9c5…
membership      sha256:56f697fb…   verifiers v0.3.1 at b2e4e815…
network key     sha256:84ea8ffa…  (public half; the founder holds the private half)
```

**The wheel above is stale.** It was built from `854c586`, which *is*
HEAD — so it is current as of this writing, but any commit touching
`src/` or `pyproject.toml` invalidates it. Check before trusting it:

```bash
git diff --stat 854c586..HEAD -- src/ pyproject.toml   # empty ⇒ the wheel still stands
```

## 3. What is done

The public run log is built and works end to end. `techtree publish` and
`techtree withdraw` on the CLI; a signed submission and a countersigned
receipt; seventeen checks between a submission and a database row;
`/runs` and `/runs/<bundle-digest>` on the site; an append-only log
ordered by arrival and never by score; the contributor-address table in
the founder's own schema.

A **staged publication was performed** on 2026-08-28 through the exact
packaged wheel, over https, to a local instance of the site on a
throwaway database with the founder's real signing key. Entry 1, 84
files, 238,377 bytes. Verified: newest-first ordering, all 36 task rows
on the detail page, the raw submission not downloadable (three plausible
addresses all 404), server-side idempotence (the same bytes posted twice
returned the same log sequence and a byte-identical receipt, one entry),
and a contributor address appearing in **zero** places across the list
page, the list API, the detail page, the detail API and every file on
disk.

Gates, all green at the commits above:

```
techtree-python   make check          3276 passed, 1 skipped; generated-check clean
techtree-python   make check-plugin   918 passed; plugin doctor 10/10
techtree-python   make test-integration   295 passed
techtree-plugin   make check          format, lint, types clean
techtree-ash      PGUSER=sean mix check   471 tests, 0 failures
cross-repository  tools/verify_release_core.py --bootstrap … --wheel …   26 of 26
```

## 4. What is left, in order

### 4.1 The blocker that stops a new user (P0, `techtree-python-evu`)

**The published install command does not work on a fresh Hermes
profile.** It reports verdict CAUTION and then refuses:

```
Decision: BLOCKED — Blocked (community source + caution verdict, 6 findings).
Use --force to override.
```

Already ruled out, so do not redo it: it is **not** a non-TTY artifact
(tested under a real pseudo-terminal — it never prompts), and it is
**not** caused by `--enable` (it blocks identically without it).
`--force` is the only path through and it then installs cleanly.

The finding count is **no longer part of this**. On 2026-08-28 the
founder had the FAQ reworded to describe the deny-list rather than
repeat its words, and the scan now reports **five findings in three
families** — exactly what the guide and both READMEs promise. Plugin
commit `1050d18`; ticket `techtree-python-an6` is closed.

The block survived that, which isolates its cause: *"community source +
caution verdict"*. The verdict comes from the one remaining HIGH, the
deny-list in `cli/guards.py`, which is genuine — a deny-list has to name
what it denies — and must not be evaded. **So reducing findings has
already been tried and is spent.**

One further wrinkle: `--force` is documented in Hermes's own help only
as "Remove existing plugin and reinstall", so a user told to use it
cannot tell from the help what they are agreeing to.

**This needs a founder ruling, not an implementation.** Do not put
`--force` into the published one-line command, and never suggest turning
Hermes scanning off. What remains is a choice between telling the truth
in the guide — show the plain command, say Hermes will refuse it, list
the five findings, then give the override as a deliberate second step —
and a trusted-source path, if Hermes has one. Both options and what has
already been ruled out are on the ticket.

### 4.2 Finish the end-to-end journey

The founder asked for a full journey on a fresh Hermes profile ending
with the receipt visible on the site. It stopped at 4.1 before spending
anything. Once that is ruled on: fresh profile → plugin → CLI → doctor →
prepare → start (a paid run, roughly USD 0.12) → publish → view.

Budget discipline, non-negotiable: estimate before every paid leg, stop
on a shortfall, and **never retry a paid outcome** — a failure is the
result.

### 4.3 Re-freeze and re-pin

Only after 4.1 and 4.2, because both may change packaged source.

1. Build the wheel twice from two independent clean clones of the freeze
   commit; both digests must match. The build hook refuses to stamp a
   dirty tree — that is deliberate, so commit first.
2. Read the stamp back out of the wheel and confirm it names the freeze.
3. Regenerate `release/wheel-inspection.json`,
   `release/fresh-install-report.json`,
   `release/plugin-release-candidate.json` — every value re-observed,
   never transcribed.
4. Update the site's `priv/releases/climb-v0.1.0/bootstrap.json`
   (`cli.source_revision`, `cli.wheel_sha256`, the plugin revision and
   its install argv), regenerate `checksums.json`, and re-run
   `scripts/sync_catalog.exs`.
5. Re-run the cross-repository gate; it must report **26**.
6. Append the range to
   `release/post-certification-change-classification.json`.

### 4.4 Reissue the Gate-2 packet

`release/founder-release-approval-packet.md` is the current one and is
now stale: it predates the publication feature. Rewrite it, do not patch
it. It must name the publication feature explicitly, carry the new
coordinates, and record the founder's approval of the improver Skill
bytes (given 2026-08-28, see §6).

An independent re-verification of
`release/product-claim-evidence-matrix.{md,json}` was arranged with
another session and has not been delivered. That matrix has **no row for
publishing at all**, which is a whole shipped feature with no
claim-to-evidence mapping.

### 4.5 Publication, after the founder gives the phrase

The phrase is in `docs/spec/closeout-helloworld/FOUNDER_APPROVAL_PHRASES.md`.
Nothing publishes, tags, deploys or activates without it.

1. **Push the frozen commits.** Nothing works before this.
2. Make the repositories public. **No branch protection** — founder
   ruling, 2026-08-26.
3. Activate the release on the deployed site. Note the founder's local
   database currently has an active stable release with *superseded*
   coordinates (plugin `6ef36a35`); it reaches nobody, but the deployed
   one must import and activate the frozen bootstrap.
4. **Publish the wheel last.** A version number on a public index is
   spent permanently. Everything falsifiable belongs before this step.
5. Post-publish smoke check (`techtree-python-rlf`).

## 5. How this work is done here

These are not preferences. They come from the founder's standing rules
and from things that went wrong.

- **Never push to GitHub unless explicitly asked.** Commit freely.
- **Verify by running.** A claim in a report is not evidence. Re-run the
  gate, re-measure the bytes, reproduce the defect before and after.
- **Mutation-check every guard you add**: break the code, watch the test
  go red, restore it, watch it go green. A guard nobody has seen fail is
  not a guard. Use `PYTHONDONTWRITEBYTECODE=1` — stale `.pyc` files have
  faked a pass here.
- **Hard cutover.** No fallbacks, no compatibility branches, no shims,
  no aliases, no dual-shape support. Delete old handling rather than
  police it.
- **Evidence is append-only.** A completed run's files are never
  modified. Adding a file to a run directory is permitted.
- **Workers never run git commands that write.** The chief commits.
- **Never read `.env`. Never handle the founder's private key.** The
  staged run works because *he* exports it in the shell that starts the
  server; it never passes through a session.
- **Copy guards encode rulings.** When copy must change, move the guard
  with it and mutation-check the move. Four guards were found on
  2026-08-27 *requiring sentences that had become false* — that is the
  worst failure mode in this codebase, because that copy is exactly the
  copy a reader trusts.

## 6. Decisions the founder has already made

- **The public run log ships inside v0.1** (2026-08-27). Ten blockers,
  all closed; see decision 0038.
- **`techtree publish`**, not `techtree proof publish`. Hard cut, no alias.
- **Server-side verification is the eight bundle checks**, not a second
  full implementation of the offline verifier. What the server does not
  check is written into its own documentation.
- **The network key id is the sha256 of its own public key.**
- **A run is addressed by its bundle digest**: `/runs/sha256:…`.
- **The improver Skill bytes `sha256:d5a381be…` are approved**
  (2026-08-28), extending the Gate-1 approval. The difference from the
  approved bytes is one line, required by his own decision 0036.
- **`/crown` and `/prism` are previews, not routes.** They sit behind
  `dev_routes`; `router_test.exs` pins the published surface and has a
  source-level test asserting each preview is declared inside that guard.
- **No branch protection.**
- **No further paid scientific evaluation** unless a scientific artifact
  changes. A post-run publication command is not one.

## 7. Traps that cost this session time

- **`TECHTREE_HOME` is not the CLI's home variable.** It is the
  *worker's*, passed to a subprocess by the launcher. The CLI resolves
  its home from `$HOME`. Setting `TECHTREE_HOME` to isolate a CLI run is
  a silent no-op.
- **`config/config.exs` is evaluated at compile time.** An environment
  variable read there is read once, at build time. Runtime overrides
  belong in `config/runtime.exs`.
- **Running a script that imports the catalog against the test database
  breaks ~100 unrelated tests.** `PGUSER=sean MIX_ENV=test mix ash.reset`
  fixes it. Use a throwaway database instead.
- **`techtree-ash` is shared with other sessions.** Stage only your own
  paths. Check `git status` before committing and never `git add -A`
  there.
- **`git checkout <path>` discards a worker's in-flight changes**, not
  just your own edit. Undo a mutation by editing it back.
- **The offline verifier and the publish path both once read the stored
  `publication_eligible` flag.** That flag records what the build that
  *wrote* the report allowed. Reading it refused every run in existence.
  Both are fixed; if a third place appears, fix it the same way — decide
  from the report's own grade and rights.

## 8. Where the staged harness lives

Under the session scratchpad, which will not survive:
`…/scratchpad/staged/` holds a one-day self-signed certificate, a TLS
terminator (`tls.py`, 4443 → 4010) and an isolated CLI install. Rebuild
rather than hunt for it. The site command the founder runs is:

```bash
cd techtree-ash && PGUSER=sean PGDATABASE=techtree_staged \
  TECHTREE_CATALOG_CHANNEL=stable PHX_HOST=techtree.sh PORT=4010 \
  MIX_ENV=dev mix phx.server
```

`PHX_HOST=techtree.sh` is required: the CLI checks a receipt's entry URL
against the origin ReleaseCore pins and refuses anything else.

## 9. Open tickets

`beads list --status open`. As of this handoff: 3 P0, 11 P1, 15 P2,
12 P3. The P0s are the two long-running epics (`85a`, `ndq`) and the
install blocker (`evu`). Nine defects from the WP11f onboarding journey
are open and none is fixed.
