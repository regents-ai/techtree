# Public-visibility review — full-history secret and privacy sweep

Founder directive 2026-08-26: prepare `techtree-python`, `techtree-plugin` and
`techtree-ash` for public visibility. This document PREPARES and REPORTS.
Nothing was published, nothing was changed, and no git command that writes was
run. This file is the only file this review created.

Prior security work (`release/security-review.md`) covered the **current state**
of the code. This review covers **history**, which is what actually goes public.

Reviewed at local tips `techtree-python 6118c20`, `techtree-plugin cc387bd`,
`techtree-ash 2bcdfba`. All three local `main` branches are ahead of their
private remotes; the remote tips are `19b3033`, `a14bb08` and `1af0301`.

## Verdict in one line

**No credential needs rotating and no history rewrite is required for secrets.**
One document must not go public as written, and a short list of items should be
fixed before visibility is flipped.

| Repository | Verdict |
|---|---|
| techtree-python | FIX FIRST — 5 items, none a secret |
| techtree-plugin | FIX FIRST — 2 items, none a secret |
| techtree-ash | BLOCKER — 1 document; then FIX FIRST — 2 items |

---

## 1. Method, and what it would not catch

### What was searched

Not `git log -p`. A diff only shows text that changed in a commit, skips binary
content, and can miss a blob that arrived and left inside a squash. Instead the
**entire object database** of each repository was enumerated and read:

1. `git cat-file --batch-all-objects --batch-check` listed every blob the
   repository holds — 1,375 in python, 427 in plugin, 400 in ash.
2. `git rev-list --objects --all` listed every object reachable from every ref,
   including remote-tracking branches and the ash stash, and produced a
   blob→path map covering every path each blob ever occupied.
3. The two sets were compared. **Every blob in every object database is
   reachable from a ref.** There are no dangling or unreachable objects hiding
   anything, in any of the three.
4. Every blob's full content was streamed through a 29-pattern battery
   (provider key prefixes for OpenAI, Anthropic, GitHub, AWS, Google, Slack,
   Stripe, npm, Fly and HuggingFace; PEM and OpenSSH private-key framing; JWTs;
   bearer literals; `PRIME_API_KEY` and sibling assignments; generic
   secret/password/token assignment; Phoenix `secret_key_base`; database and
   AMQP connection strings; `user:pass@host` URLs; `/Users/…`, `/home/…` and
   Windows home paths; e-mail addresses; preview/PaaS hostnames; RFC1918
   addresses).
5. Every hit was then triaged by hand against its containing file, and four
   further targeted sweeps were run over the same corpus: answer-key and
   task-content markers, provider request/response and raw-reasoning markers,
   session/pairing/deploy-credential markers, and references to unrelated
   private projects.
6. Commit **metadata** was read separately — author and committer identities on
   all 271 commits, and every commit message.
7. Remote ref namespaces were listed (a read) to confirm what the remotes
   actually hold.

### Coverage is effectively total

Only **four** blobs across all three repositories are binary and were therefore
excluded from the text battery: `tests/fixtures/skills/invalid-binary/payload.txt`
(1 KB, verified as all 256 byte values four times each — a null-byte fixture,
not data), two favicons and one woff2 font. Everything else — every version of
every text file that ever existed — was read in full.

### What this method would NOT catch

Stated plainly, because a sweep that oversells itself is worse than none.

- **A secret that does not look like one.** A bare 32-character hex string with
  no surrounding key name, a passphrase that reads like an English word, an
  account identifier that is secret by policy rather than by shape. Pattern
  matching cannot see these and neither did I.
- **Encoded or compressed payloads.** A credential base64'd into a blob without
  a recognisable prefix, or one inside the woff2/ico binaries. The three binary
  files were identified and reasoned about, not decoded.
- **Meaning.** I judged fixtures benign from their filenames, surrounding code
  and value shapes. A real key deliberately given a fixture-looking name in a
  test file would read as a fixture to me.
- **Anything not in these three object databases.** Commits authored elsewhere
  and never fetched here; content in the GitHub repositories' issues, PR
  discussions, releases, wikis or Actions logs; `certification-evidence/`, which
  lives outside all three repos by design and which I did not sweep because it
  is not published.
- **`git fetch` was not run**, because fetching writes refs. I verified instead
  that every commit currently on all three remotes is already present in the
  local object database, so nothing on a remote escaped the sweep. If anyone
  pushes between now and publication, this sweep no longer covers the tip.
- **Uncommitted work.** `techtree-python` has ~30 modified files in the working
  tree. They are not history yet. I scanned them for the same patterns and found
  only one hit, a fixture constant in
  `tests/preflight/test_verifiers_eval_contract.py`. They will need re-checking
  when they land.

---

## 2. Real credentials and private data

### Credentials: none found

**No real provider key, private key, token, session or pairing credential, or
deploy credential exists anywhere in any of the three histories.** Every hit on
a credential-shaped pattern resolved to a deliberate test fixture (section 3).
Nothing here needs rotating and no history rewrite is required on this ground.

Two supporting observations:

- The value shapes are wrong for real keys in every case. The `sk-`-prefixed
  strings are 23–44 characters and spell English words; the AWS access key is
  the canonical value from Amazon's own documentation; the private-key blocks
  contain the literal words FAKE and NOT.
- `.github/workflows/publish.yml` publishes to PyPI over **OIDC trusted
  publishing with no token**, and refuses to publish unless a freshly built
  wheel matches the digest in the approval packet and its provenance stamp names
  the checked-out commit. There is no credential in CI to leak.

### Private data that is real, and is already committed

| Kind | Where | Verdict |
|---|---|---|
| Founder identity in commit metadata | `Sean Brennan <sean@regents.sh>` on 266 of 271 commits, all three repos | PASS — deliberate authorship |
| GitHub account handle | `102389629+seanonchain@users.noreply.github.com` authors 5 commits (3 python, 2 plugin) | PASS with note — publishing links the founder's name to the `seanonchain` handle |
| Founder e-mail in a governance record | `release/founder-approvals/gate1-founder-skills.md` names `build@regents.sh` | FIX FIRST — founder's call |
| Absolute home paths | `/Users/sean/…`, 53 occurrences in python, 18 in plugin | FIX FIRST — see below |
| Local directory layout | The `/Users/sean/…` values disclose `Documents/techtree-climb/` and the existence of a sibling `certification-evidence/` directory | FIX FIRST |
| Fly application origin | `techtree-sh.fly.dev`, 36 occurrences in `techtree-ash/docs/release/deploy-flyio.md` | PASS with note |
| Unrelated private project | `techtree-ash/docs/UI-AGENT-BRIEF.md` | **BLOCKER** — section 4 |

**On the home paths.** These are real and they are at the tip, not only in
history, so deleting them from the tip would not remove them from a clone. The
honest framing: the username `sean` is already disclosed by
`sean@regents.sh` on every commit, so the marginal disclosure is the *directory
layout*, not the identity. That downgrades this from "rewrite history" to "clean
up and accept". Locations:

- `release/acceptance/terminal-e2e.json`, `release/budget-contract-audit.json`,
  `release/destination-capture.json`, `release/fresh-install-report.json`,
  `release/limit-calibration.json`, `release/network-method-log.json`,
  `release/plugin-release-candidate.json` — captured machine paths in release
  evidence.
- `tests/plugin/fixtures/cli/doctor.json` — a recorded Doctor envelope carrying
  `/Users/sean/.local/bin/hermes` and the venv interpreter path.
- `tests/plugin/unit/test_improvement_service.py:310` — the only test that uses
  the founder's real username as an input string; every sibling test correctly
  uses `/Users/someone` or `/Users/example`.
- `.beads/interactions.jsonl` — 40 occurrences of `PGUSER=sean` inside work-log
  prose.

### Run evidence and the hidden answer key (decision 0015)

**Clear.** No live run directory, episode, trace or proof bundle has ever been
committed to any of the three repositories. Searched by path shape
(`run_[0-9a-f]{8}`, `runs/`, `episode`, `trace`, `proof`, `evidence`) across
every path any blob ever occupied, and by content for answer-key markers.

The two committed recorded fixtures were audited structurally rather than
skimmed:

- `tests/fixtures/receipts/recorded/{baseline,candidate}/normalized-episodes.jsonl`
  — 36 lines each. Every field is a digest, an identifier, a count, a token
  number or a reward score. `last_reply` is `null` on every trace. `cost_usd` is
  `null` throughout. No prompt, no reply, no answer, no absolute path, no
  hostname, no username. This satisfies decision 0015 §5 as written.
- `tests/golden/real-episode-receipt.json` — digests and sizes only.

No provider request or response body, and no raw model reasoning, exists in any
history. The only matches for `chat/completions` are five endpoint *labels* in
two test files; there are no `reasoning_content`, `<think>` or
`system_fingerprint` occurrences anywhere.

One thing a reader should understand rather than discover: the task answers for
BranchCode v1 are **computable from the shipped engine** —
`src/techtree/resources/engines/default/packages/procedure-transfer-v1/` carries
the oracle that generates them. That is the design of a toy demonstration, not a
history leak, and it is not something publication changes.

---

## 3. The adversarial fixtures — alarming, benign, and deliberate

This project tests its own scanners and scrubbers, so it must contain the things
they defend against. Every one of these will light up GitHub secret scanning and
any third-party scanner pointed at the repository. **None is a secret.** They are
listed here so nobody has to work that out under pressure.

All of them live in `techtree-python`. That is deliberate: the plugin checkout is
what an install-time scanner reads before a host will install it, so the corpus
was moved out of it (see 5.2 for the history consequence).

### The corpus itself

| Path | What it is |
|---|---|
| `tests/unit/test_skill_scanner.py` | The Skill scanner's positive corpus. Fake GitHub, Slack and AWS tokens, `-----BEGIN PRIVATE KEY-----` framing, `Authorization:` headers. Each entry is paired with the rule id it must trigger. |
| `tests/unit/test_errors.py` | The error scrubber's corpus. Tokens in URL userinfo, tokens in query strings, quoted API keys, an AWS access key, a Stripe-shaped live key. Several assertions are of the form "this value is NOT in the output". |
| `tests/unit/test_presentation_sanitize.py` | Sanitiser corpus. Tracebacks carrying `/Users/someone/secret.py`, prose pointing at run directories. |
| `tests/unit/test_run_service.py`, `tests/integration/test_run_logs.py` | `Bearer sk-live-…` literals, proving a credential in a log line is redacted. |
| `tests/unit/test_verifiers_credentials.py`, `test_run_launcher.py`, `test_verifiers_*.py` | Fake `sk-…` values driving the worker environment scrub. Named to say so: `sk-child-…`, `sk-supervisor-…`, `sk-compile-…`, `sk-verify-…`, `sk-doctor-…`. |
| `tests/preflight/test_verifiers_eval_contract.py` | `PRIME_API_KEY=sk-preflight-secret-value`, exported specifically to prove it reaches no child. |
| `tests/plugin/unit/test_models.py`, `test_guards.py`, `test_assets.py`, `test_improvement_service.py` | The plugin's side of the same corpus — token prefixes, a truncated PEM stub, `OPENAI_API_KEY=` assignments. |
| `tests/fixtures/skills/invalid-secret/notes.md` | A Skill that must be refused. Contains a private-key block whose body reads `xxxxxxxxxxFAKExxxxxxxxxxNOTxxxxxxxxxxAxxxxxxxxxxKEYxxxxxxx`. |
| `tests/fixtures/skills/invalid-binary/payload.txt` | 1 KB containing all 256 byte values four times. A Skill carrying non-text content, which must be refused. Reads as an unidentified binary to any scanner. |
| `tests/fixtures/skills/invalid-symlink/` | A Skill containing a symbolic link, which must be refused. |

### The pattern definitions, which look like the thing they detect

| Path | What it is |
|---|---|
| `src/techtree/skills/scanner.py:109-176` | The secret-detection rule table: PEM framing, provider token prefixes, `AKIA\|ASIA` and `aws_secret_access_key\|aws_session_token`. A detector has to spell what it detects. |
| `src/techtree/errors.py`, `src/techtree/release/models.py` | `user:pass@host` URL patterns, used to reject a credential riding inside a release URL. |
| `techtree-plugin/cli/guards.py:44-136` | The deny-list of command words — `sudo`, `curl`, `chmod`, `rm`, `docker`, `pip`, `bash` — that a model-authored Skill is refused for containing. Hermes's own scanner reports this as privilege escalation; it is the list of what to refuse. |
| `techtree-plugin/cli/bridge.py` | The three places the plugin starts the Techtree CLI. Reported as execution; it is the entire plugin↔CLI boundary. |
| `techtree-plugin/host/channels.py` | A control-character stripper. Reported as obfuscation; it is one regex removing terminal control codes. |

The last three are already documented for the public in
`techtree-plugin/README.md` under "Install-time security scanning", which is the
right place for them and reads well. The `techtree-python` corpus has no
equivalent public note. **Recommendation:** add a short `tests/fixtures/README.md`
or a README section saying what the corpus is, so the first stranger who runs a
scanner over the CLI repository finds an answer instead of filing an issue.

### Example hosts and identifiers that are not real

For completeness, so they are not re-investigated: `pypi.corp.example`,
`pypi.internal`, `git.internal`, `objects.example`, `index.example`,
`localhost:8080`, `hunter2token@pypi.internal`, `s3cr3t-p4ss@pypi.corp.example`,
`p4ssw0rd@git.internal`, `token@techtree.sh`, `reproducer@example.org`,
`/Users/someone`, `/Users/example`, `/home/me`, `/home/someone`. All fixtures.

---

## 4. Public readiness — techtree-ash

### BLOCKER — `docs/UI-AGENT-BRIEF.md`

This is an internal brief to an agent working on the site, and it must not be
published as written. It contains, in order:

1. **An unrelated private project.** A section headed "A name collision that has
   already cost this project a day" describes a second effort at
   `/Documents/regent` — "Regent's research tree", BBH branch, marimo notebooks,
   deck.gl maps, libp2p. Publishing this discloses the existence, location and
   subject matter of work the founder has not decided to disclose. This is the
   single reason the verdict is BLOCKER rather than FIX FIRST.
2. **Internal governance in the open.** "a founder is about to approve", "raise
   it with the chief session", "One session commits to this repository until
   Gate 2 clears, and that is the chief-of-staff session".
3. **`PGUSER=sean mix check`** as the mandatory pre-handoff command — the exact
   class of non-reproducible instruction the directive named.
4. **Incident history stated as fact.** "two agents refused to run the product
   over this", "which is exactly why the rules below exist".

The *substance* of this document is good and worth keeping — the copy-guard
rationale in particular explains genuinely useful constraints. The fix is not
deletion of the ideas but relocation: keep the brief out of the public tree, or
rewrite the parts worth publishing as a contributor guide with the other project,
the governance roles, the incident anecdotes and the personal `PGUSER` removed.

### FIX FIRST — `.claude/launch.json` is tracked and carries `PGUSER=sean`

```json
"runtimeArgs": ["PGUSER=sean", "mix", "phx.server"]
```

A local editor convenience committed to the repository. A stranger who uses it
gets a Postgres role that does not exist on their machine. Either untrack it or
make the role come from the environment. Note the README already handles this
correctly — it documents `PGUSER`, `PGPASSWORD` and `PGHOST` as overrides — so
the launch file is the only place the personal value is baked in.

### FIX FIRST (verify) — committed `secret_key_base` in dev and test config

`config/dev.exs:27` and `config/test.exs:21` each carry a full-length
`secret_key_base`. This is what `mix phx.new` generates and it is conventional to
commit them, but they are real 64-byte secrets and every public scanner will flag
them.

Production is safe **by construction**: `config/runtime.exs` raises unless
`SECRET_KEY_BASE` is present in the environment, and `fly.toml` states that
`SECRET_KEY_BASE`, `PHX_HOST` and `DATABASE_URL` are set with `flyctl secrets
set` rather than baked into the image. I could not verify what value is actually
set on the deployed application without reading Fly secrets, which I did not do.

**Ask before publishing:** confirm that the `SECRET_KEY_BASE` set on
`techtree-sh` is not either of the two committed development values. If it is,
rotate it — and that is a rotation, not a history rewrite, because these values
are conventional and disclosing them costs nothing once production differs.

### PASS with a note — `techtree-sh.fly.dev`

`docs/release/deploy-flyio.md` names the Fly application `techtree-sh` and its
`.fly.dev` origin 36 times. This discloses the direct origin behind
`techtree.sh`. For a read-only GET/HEAD-only site with no writable surface this
is close to harmless, and the runbook is genuinely useful documentation. Worth a
conscious decision rather than an accident.

### The rest — PASS

- **LICENSE** — MIT, "Copyright (c) 2026 Sean Brennan". Matches decision 0011 §1.
- **README** — genuinely excellent for a stranger. Says what the site is, that
  it runs no evaluations and accepts nothing, lists every route, explains the
  refusal shapes, gives `mix setup` / `mix check`, documents every runtime
  variable, and states plainly that no model-provider credential is read.
- **`.gitignore`** — thorough and commented, including the generated
  `priv/catalog/` and the digested static assets. Nothing that should stay local
  is tracked; 144 tracked files, no `.DS_Store`, no `.env`, no build output.
- **`config/runtime.exs`** — clean. Every production secret comes from the
  environment and raises when absent. The one `user:pass@host` string is the
  Phoenix-generated `ecto://USER:PASS@HOST/DATABASE` example.
- **`AGENTS.md`** — 373 lines of Phoenix/Tailwind conventions. Internal-facing
  but neither confusing nor embarrassing, and increasingly normal in public
  repositories.
- **Stash and branches** — one stash holding small doc and release-coordinate
  edits (stashes are never pushed; scanned anyway, clean).
  `wip/public-evidence-site` contains no commit `main` does not already have.

---

## 5. Public readiness — techtree-plugin

### FIX FIRST — the adversarial corpus is gone from the tip but lives in history

The whole point of moving the plugin's tests into `techtree-python` was that this
checkout is what an install-time scanner reads. That worked: it took the Hermes
verdict from DANGEROUS-no-override to CAUTION-with-confirm. But the move was a
deletion in commit `09bd48b`, not a rewrite, and **58 paths under `tests/`
remain in history** while the tip tracks none, carrying the full corpus — fake tokens, PEM stubs,
`OPENAI_API_KEY=` assignments, and `/Users/sean` inside
`tests/fixtures/cli/doctor.json`.

This does not affect the install scanner, which reads the working tree. It does
affect anything that reads history: GitHub secret scanning, and any reader who
runs `git log -p` on a repository whose README explains that the tests were
deliberately moved elsewhere.

Two honest options, and this is a founder decision, not a technical one:

- **Accept and explain.** Add one paragraph to the README saying the suite used
  to live here, why it moved, and that history therefore contains fixtures that
  look like credentials and are not. Cheapest, and consistent with the project's
  stated refusal to disguise fixtures.
- **Rewrite history.** Removes the noise permanently, invalidates every commit
  hash in the repository, and the release candidate is pinned to an exact
  40-character commit that is referenced from `release-core.json`, the
  BootstrapRelease, the security review and the scanner dossier. **Not
  recommended** at this point in the release.

### FIX FIRST (minor) — `.gitignore` is thin

Five lines: `__pycache__/`, `*.py[cod]`, `.venv/`, `.mypy_cache/`, `.ruff_cache/`.
Missing `.DS_Store`, `dist/`, `build/`, `*.egg-info/` and `.pytest_cache/`.
Nothing unwanted is tracked *today* — the tree is 46 files and clean — but this
is one careless `git add .` away from a problem, and the sibling repository's
`.gitignore` is the model to copy.

### The rest — PASS

- **LICENSE** — MIT, founder as copyright holder. Byte-identical to the other two.
- **README** — the best of the three for a stranger. Opens with a prompt to paste
  into Hermes, states what the plugin does and does not upload, states that the
  evaluated agent is never the agent you are talking to, explains the caution
  scan verdict finding by finding *before* you meet it, documents disabling,
  removing, and the one directory removal can leave behind, and refuses to print
  a `rm -rf` line on the reasonable grounds that nobody should paste one out of
  a README.
- **No personal development assumptions.** No `PGUSER`, no `/Users/sean`, no
  home path anywhere in the tip.
- **A stranger cannot run the tests**, because they are in the sibling
  repository. This is documented in both the README and the Makefile with the
  reason. PASS — it is a stated design consequence, not an omission.
- **Working tree clean**, no tracked build output, no `.DS_Store`, no `.env`.

---

## 6. Public readiness — techtree-python

### FIX FIRST — `PGUSER=sean` in instructions a stranger would follow

The directive named one instance; there are four files plus a deleted one.

| File | Occurrences |
|---|---|
| `docs/agent-handoff.md` | 12 across history, 1 at the tip |
| `docs/product-architecture.md` | 6 |
| `docs/v0.1-remaining-tickets.md` | 3 |
| `.beads/interactions.jsonl` | 40, inside work-log prose |
| `docs/architecture-handoff.md` | 1 — file no longer at the tip |

The fix is the same everywhere and `techtree-ash/README.md` already shows it:
name `PGUSER` as an override for machines whose Postgres does not use the
Phoenix defaults, rather than hard-coding one person's role.

### FIX FIRST — absolute home paths in release evidence

Seven files under `release/` plus `tests/plugin/fixtures/cli/doctor.json` carry
captured `/Users/sean/…` paths (enumerated in section 2). These are recorded
evidence, and decision 0015 §5 explicitly forbids absolute paths in committed
fixtures — so `tests/plugin/fixtures/cli/doctor.json` is a rule violation, not
just untidiness, and `tests/plugin/unit/test_improvement_service.py:310` should
use `/Users/someone` like its neighbours.

The `release/*.json` files are a different question, because they are *evidence*
and rewriting them to be tidier is exactly the kind of retroactive truth-fixing
this project refuses. The honest resolution is probably to leave the evidence
alone and note in `release/README.md` that captured machine paths appear in it —
but that is a founder ruling, not mine to make.

### FIX FIRST — internal-only documents

None of these is embarrassing. Several are excellent internal writing. The
question is only whether a stranger who opens the repository should meet them.

| Path | What it is |
|---|---|
| `docs/agent-handoff.md` | The three-repository handoff. Programme spend, private remote names, "the founder", "the chief", `PGUSER=sean`, `certification-evidence/` outside the repos, an unreleased-work section. Internal orientation, not documentation. |
| `docs/v0.1-remaining-tickets.md`, `docs/handoff-v0.1-tickets.md`, `docs/wp6-handoff.md`, `docs/plan/wp9-plus-plan.md` | Open work lists and planning. `README.md` links to `docs/v0.1-remaining-tickets.md` from a public paragraph. |
| `.beads/interactions.jsonl` | 281 lines of the private issue tracker's audit trail — every status change, assignee and priority edit, actor `Sean Brennan`, with 54 free-text work-log entries and 40 `PGUSER=sean`. Tracked because beads tracks its config and metadata by default. Nothing sensitive; it is simply not a public artifact. |
| `release/hermes-scanner-dossier.md` | Opens "Prepared for a Nous Research security reviewer… a request for trusted-source consideration". Private correspondence between two companies about one of them's security verdict. Publishing it is a relationship decision. |
| `release/founder-approvals/`, `release/founder-skill-approval-draft.md`, `release/founder-skill-approval-addendum-1.md`, `release/founder-release-approval-packet.md` | Internal governance records. The first names `Sean Brennan, build@regents.sh`. |
| `docs/spec/closeout-helloworld/CHIEF_CLOSEOUT_DIRECTIVE.md`, `FOUNDER_APPROVAL_PHRASES.md` | The closeout directive and the exact phrases that authorise publication. The phrases are templates requiring digests, so publishing them does not hand anyone a working key — but it does publish, to any agent that reads the repository, the literal sentence that authorises a release. Worth a deliberate decision. |

**Good news on the tracker:** I confirmed by listing remote refs that **no
`refs/dolt/data` namespace exists on any of the three remotes**. The beads Dolt
database — the full internal ticket history — is not on the remotes and will not
become public. Only the four tracked `.beads/` files will.

### FIX FIRST (cosmetic) — `CLAUDE.md` ships unfilled template placeholders

Lines 63 and 77 read `_Add your build and test commands here_` and `_Add your
project-specific conventions here_`, in a repository whose README documents both
thoroughly. It reads as abandoned. Either fill them in, point them at the README,
or cut the sections.

### The rest — PASS

- **LICENSE** — MIT, "Copyright (c) 2026 Sean Brennan". Matches decision 0011 §1.
- **README** — 10 KB, and suitable for a stranger. States what Climb v0.1 is and
  that it is a toy synthetic demonstration; gives `uv sync --python 3.12`;
  explains the evaluation credential and, unusually well, why exporting it in a
  shell is not enough; documents every command; explains what a verified proof
  does and does not claim; lists the security boundaries; names the generated
  files that must not be hand-edited. It says what the project does NOT do —
  no upload, no account, participant-attested rather than independently
  reproduced — which is the part most READMEs skip.
- **`.gitignore`** — the best of the three. Ignores the usual build and cache
  output, the local Techtree home directories a `--home .` invocation would
  create (`/runs/`, `/cache/`, `/drafts/`, `/engines/`, `/config.toml`), the
  build-provenance stamp that must exist only inside a wheel, and the beads Dolt
  database and credential key. Nothing that should stay local is tracked.
- **CI** — one workflow, OIDC trusted publishing, no tokens, digest-and-
  provenance gated, `workflow_dispatch` only.
- **Secrets** — clear, as covered in section 2.

---

## 7. What must be fixed, in order

1. **`techtree-ash/docs/UI-AGENT-BRIEF.md`** — do not publish as written. It
   discloses an unrelated private project. Remove it from the public tree, or
   rewrite it as a contributor guide without the other project, the governance
   roles, the incident anecdotes and `PGUSER=sean`. *(BLOCKER)*
2. **Confirm the deployed `SECRET_KEY_BASE` on `techtree-sh` is not either
   committed development value.** Rotate if it is. This needs the founder; I did
   not read Fly secrets. *(FIX FIRST — verify)*
3. **Untrack or de-personalise `techtree-ash/.claude/launch.json`.** *(FIX FIRST)*
4. **Remove `PGUSER=sean` from every instruction a stranger would follow** —
   `docs/agent-handoff.md`, `docs/product-architecture.md`,
   `docs/v0.1-remaining-tickets.md`. Follow the pattern the ash README already
   uses. *(FIX FIRST)*
5. **Decide the fate of the internal documents** in section 6 — the handoffs, the
   ticket lists, `.beads/interactions.jsonl`, the scanner dossier, the founder
   approval records, the closeout directive and approval phrases. Each is a
   keep/move/redact call. *(FIX FIRST)*
6. **Decide on the adversarial corpus in `techtree-plugin` history.** Recommended:
   one README paragraph explaining it. Not recommended: rewriting history, which
   invalidates the pinned release commit. *(FIX FIRST)*
7. **Fix the two decision-0015 §5 violations in committed fixtures** —
   `tests/plugin/fixtures/cli/doctor.json` and
   `tests/plugin/unit/test_improvement_service.py:310`. *(FIX FIRST)*
8. **Add a note explaining the adversarial corpus in `techtree-python`**, so the
   first stranger who scans it finds an answer. *(FIX FIRST)*
9. **Widen `techtree-plugin/.gitignore`** to match the CLI repository's.
   *(FIX FIRST — minor)*
10. **Fill in or remove the `CLAUDE.md` template placeholders.**
    *(FIX FIRST — cosmetic)*
11. **Decide whether `techtree-sh.fly.dev` and the founder e-mail in the Gate-1
    approval record should be published.** Both are defensible either way.
    *(judgement)*

Nothing on this list requires rewriting history to remove a secret, because no
secret was found.

## 8. What I was unsure about, and what I left alone

- **The deployed `SECRET_KEY_BASE`.** I did not read Fly secrets. Item 2 above is
  an ask, not a finding.
- **Whether the founder e-mail in `release/founder-approvals/gate1-founder-skills.md`
  is deliberate.** A signed approval record naming its signer is normal
  provenance. I flagged it rather than assuming either way.
- **Whether the release evidence under `release/` should be sanitised of captured
  machine paths.** Editing recorded evidence to be tidier runs against this
  project's append-only posture. Founder ruling.
- **`refs/pull/1/head` on the python and plugin remotes.** These are GitHub's
  read-only PR refs. Both point at commits already present locally and already
  swept. What is written in the PR *discussion* is outside git and outside this
  review.
- **The ash stash.** Read (its blobs are in the object database and were swept;
  it is clean), but stashes are never pushed, so it cannot reach the public
  regardless.
- **`certification-evidence/`.** Deliberately outside all three repositories and
  never committed. I confirmed it is absent from every history and did not sweep
  its contents, because it is not published.
- **The ~30 uncommitted files in `techtree-python`.** Someone else's work in
  flight. I scanned but did not touch them; they need re-checking when they land.
- **Everything else.** I changed nothing in any repository. No git command that
  writes was run: no fetch, no commit, no gc, no rewrite.

---

## Remediation record (chief session, 2026-08-26, founder-directed)

The founder ruled: fix the blocker and the home-path family now; every
other finding is accepted as-is.

1. **BLOCKER cured by history rewrite.** `docs/UI-AGENT-BRIEF.md` was
   already deleted at the techtree-ash tip (552ba38); it has now been
   filtered out of the repository's entire history with git filter-repo
   and the rewritten history force-pushed (with lease) to the private
   remote while no external clone exists. Old tip e50f107 → new tip
   0a000fd; zero objects referencing the document remain in the object
   database, verified by enumeration. Consequence: every techtree-ash
   commit hash from 1af0301 forward changed — any record citing an old
   ash hash (tickets, packet drafts, decision notes) is citing
   pre-rewrite history. A full pre-rewrite bundle, the document's
   content, and the stash patch are preserved outside the repositories
   at certification-evidence/pre-rewrite-backup/. The publishable
   substance of the brief was rewritten as
   techtree-ash/docs/contributor-guide.md with the unrelated project,
   governance roles, incident anecdotes and personal values removed.
2. **Home paths redacted at the tip, accepted in history**, exactly as
   this review prescribed: `/Users/sean` → `/Users/redacted` across the
   seven release evidence files (26 occurrences); the test and the
   doctor fixture had already been fixed by the tidy-up commit. The
   redaction alters recorded report bytes and is disclosed here; the
   underlying runs and their signed artifacts are untouched.
