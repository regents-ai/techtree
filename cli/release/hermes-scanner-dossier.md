# Hermes scanner dossier — regents-ai/techtree-hermes

Prepared for a Nous Research security reviewer. Subject: the install-time
scanner verdict on the Techtree Hermes plugin, and a request for
trusted-source consideration. Every factual claim below names the file,
record, or test that carries it.

## 1. What the plugin is

`regents-ai/techtree-hermes` is the Hermes operator plugin for Techtree, a
local evaluation harness that runs the same toy task family with and without a
Skill and produces a signed, offline-verifiable receipt of the difference. The
plugin is MIT licensed (`LICENSE`). Its runtime imports only the Python
standard library and never imports Techtree's Python package — `make doctor`
fails the build if that stops being true (`doctor.py:528-565`, check id
`runtime_imports`). It performs no networking of its own: every action it can
cause is one invocation of the pinned `techtree` CLI with a fixed argument
array, returning exactly one JSON envelope (`bridge.py`, `build_cli_argv`).
Installation is pinned to an exact 40-character commit read from the active
BootstrapRelease; branch names and floating versions are refused by
documentation and by the install-plan validator alike (`README.md` "Install";
decision `docs/decisions/0024-agent-first-onboarding.md` §4).

Release candidate under appeal when this dossier was written: version 0.1.0,
commit `880aa8aeeeb168a8d2328d75d2d424ca471953f6`, ReleaseCore digest
`sha256:c037f457…`, `plugin_doctor` passed 10 checks (9 ok, 1 warn: no CLI on
PATH in a bare checkout, which the doctor states is not a plugin fault). The
release record `release/plugin-release-candidate.json` now names the cleaned
commit instead — §6.

## 2. The scan result being appealed

The Hermes 0.20.4 install-time scanner returns **DANGEROUS, 17 findings, no
override** at commit `880aa8a`. The verdict is a hard block: the install cannot
proceed even with explicit human approval.

Sixteen distinct source locations appear in our record of the scanner output;
the scanner's own report is the authoritative count and is attached to this
appeal. Every CRITICAL is either an adversarial security-test fixture or one
line of uninstall documentation. No finding is in code that runs at install
time, at registration, or during a run.

| Location | Band | Rule match | What it actually is | Why it exists |
|---|---|---|---|---|
| `tests/unit/test_guards.py:96` | CRITICAL | pipe-a-downloaded-script-to-a-shell string | Parametrised input to `test_a_narrative_may_not_tell_anyone_to_run_something` | Proves `forbid_new_commands()` rejects a narrative that tells a user to run something |
| `tests/unit/test_guards.py:324` | CRITICAL | recursive delete of the filesystem root, in a fenced code block | Input to `test_a_revision_may_not_ship_commands` | Proves `validate_revised_skill()` refuses a model-authored Skill revision that ships commands |
| `tests/unit/test_improvement_service.py:273` | CRITICAL | PEM private-key header | Parametrised hidden-material case | Proves `validate_context()` refuses improvement context carrying hidden material (decision 0007 R1's exclusion list, checked rather than trusted) |
| `tests/unit/test_models.py:325` | CRITICAL | shell metacharacter plus recursive delete inside a version string | Mutation of a bootstrap install plan | Proves `validate_install_plan()` rejects a plan whose `version` is not a version string |
| `tests/unit/test_models.py:346` | CRITICAL | PEM private-key block with base64 body | Scrubber corpus entry | Proves `scrub_text()` redacts a private key; the same table covers bearer tokens, quoted JSON API keys, env-var secrets and a token in a package-index URL's userinfo |
| `tests/unit/test_tools.py:191` | CRITICAL | command separator plus recursive delete in a climb reference | Parametrised bad reference | Proves a reference that is not a reference never reaches argv — the direct test of the injection path a reviewer would worry about |
| `README.md:217` | CRITICAL | literal recursive-delete shell line | Uninstall documentation | Real doc-hygiene issue. Being rewritten as prose (see §4) |
| `tests/unit/test_guards.py:98` | HIGH | privileged container-prune command string | Parametrised input, same test as line 96 | Same guard, second shape |
| `guards.py:86` | HIGH | alternation of command words | The plugin's own command-blocking guard. The word list *is* the guard: `techtree`, `hermes`, `uv`, `bash`, `sh`, `curl`, `pip`, `docker`, `git`, `sudo`, `rm` | A narrative surface may name no command; Techtree's own next actions are rendered from the payload, never from a sentence. Deleting the list deletes the protection |
| `scripts/typecheck.py:53` | HIGH | `subprocess.run` | Developer tooling — invokes `mypy` | Build-time type checking; not shipped in the runtime import graph |
| `tests/contract/test_cli_envelopes.py:107` | HIGH | `subprocess.run` | Optional contract test against a real CLI | Skipped unless a CLI is on PATH; read-only commands only |
| `tests/contract/test_no_registration_side_effects.py:156` | HIGH | `subprocess.run` | A deliberately failing call inside `test_the_tripwires_would_notice` | Proves the test's own seal is real: with process spawn, sockets and file writes replaced by tripwires, the tripwires must actually fire |
| `bridge.py:167` | MEDIUM | `subprocess.run` | The one machine-mode CLI call | `shell=False`, fixed argv built by `build_cli_argv()`; arguments must be non-empty NUL-free literals and may not include the machine flags, which the bridge adds itself |
| `bridge.py:216` | MEDIUM | `subprocess.run` | `techtree --version` | Two-element argv, no model input at all |
| `bridge.py:253` | MEDIUM | `subprocess.run` | Human-output passthrough for a live run view | `shell=False`; each argument re-validated as a usable literal |
| `channels.py:30` | MEDIUM | control-character class, read as obfuscation | A **stripper**, not an emitter: `[\x00-\x08\x0b-\x1f\x7f-\x9f]` | Removes ANSI escapes, NUL and the C1 range from answers before they are shown. It is the defence against terminal-escape injection, matched by a rule looking for it as an attack |

On the MEDIUM subprocess band specifically: no executable path and no command
can be supplied by the model. `schemas.py` states the rule in its module
contract — "Four things never appear in a schema here: an API key, an
executable path, an installation command, and an unbounded identifier. Anything
the plugin runs is built from release data and the fixed CLI contract, never
from these arguments" — and the schemas enforce it with bounded patterns
(run ids, draft ids, plan ids, digests, a 64-character climb-reference grammar).
The install path is validated independently in `models.py:520-571`: a plan
carrying executable fields is rejected, `argv` must be an array, the installer
must be the fixed executable, the argv must install exactly the pinned
requirement, and `requires_confirmation: false` is refused outright.

## 3. Security posture

- **Registration performs no side effects.** With every process spawn, socket
  and file write replaced by a tripwire, `register()` completes normally
  (`tests/contract/test_no_registration_side_effects.py`, 5 sealed conformance
  tests; 15 registration-related tests across the suite; 785 tests in the full
  battery). Because the runtime is stdlib-only, subprocess and socket are the
  only routes to a model, and both are sealed in that test.
- **Human approval is native and cannot be self-issued.** Installing the CLI
  and starting a paid run both go to the host's own approval surface.
  `approvals.py` states the rule and the code holds it: "It never treats a
  model's say-so as acceptance." Plugin install, CLI install and paid run are
  three separate human decisions.
- **One-completion rule.** One guided revision is one outbound generation
  request; an unusable answer or a transport failure spends the attempt and
  returns a typed failure with no repair and no retry (`llm.py:11`, decision
  0015 s4; `tests/contract/test_one_generation_request.py`, 13 tests). The
  plugin owns no HTTP client, proved statically. What Hermes does inside the
  single call it is handed is recorded per attempt and left to the host to
  account for — we do not claim more than we can hold.
- **Recursive secret scrubbing.** `scrub_text()` redacts bearer tokens, quoted
  secret keys, env-var secrets, provider tokens, URL userinfo credentials and
  PEM blocks; `scrub_borrowed()` walks nested mappings and lists so a free-
  shaped error `details` object cannot smuggle a credential through
  (`errors.py:160+`; ticket ndq.3.26, closed, both repositories).
- **No upload path.** Verifiers push is disabled in every resolved
  configuration and the check is tested
  (`test_a_resolved_config_that_would_upload_fails_the_push_check`); the
  website release surface was reduced to read-only — multipart parsing and
  method override removed, security headers added on static serving (ndq.3.34,
  closed). Of the three methods the release contract requires
  (`docs/release/contracts/wp11g.md`), the static route audit and the E2E
  destination capture were performed at WP11e
  (`release/acceptance/terminal-e2e.json`); the instrumented
  application-level HTTP method log is WP11g and is still open (ndq.3.7). We
  state that as an open item rather than claim the full proof.
- **Pinned, provenance-stamped supply chain.** The CLI wheel is
  `sha256:5a402a43…`, rebuilt twice from two independent fresh clones of commit
  `a3ea8c58…` to identical bytes; the wheel carries an internal
  `build-provenance.json` naming that commit, and the stamp exists only inside
  the artifact, never in the tree (`release/wheel-inspection.json`, verdict
  PASS, 6/6 checks). ReleaseCore is byte-identical across the three
  repositories.
- **Orphan containment, proven by kill injection.** In
  `release/orphan-bound-analysis.json` (decision 0029), the run worker was
  SIGKILLed mid-run: all four subject containers disappeared 0.55s later, both
  supervisors and both eval processes exited 1.08s later, total cleanup 1.1s,
  zero leftover running containers, supervision records written 0600.
- **Certification programme.** Five canonical runs plus three re-certification
  runs on the released lineage, each pre-committed as canonical before any
  score existed, every proof verified offline from stored bytes by an
  independent reviewer; run classification, retry accounting, incomplete-run
  cost and spend ledger are all disclosed, including the failures
  (`release/founder-skill-approval-draft.md` and
  `release/founder-skill-approval-addendum-1.md`). Ten SEC findings from our own
  security review (ndq.3.26–3.35) are closed with fixes and tests.

## 4. What we are doing regardless of this appeal

We treat the doc finding as real and the scanner's structural difficulty as
ours to reduce, not to argue away.

1. **Relocating the adversarial test corpus.** The full test battery moves into
   the certification repository (`techtree-python`), preserved and runnable in
   its entirety; the installable plugin tree ships runtime, skills, release
   core and README only. We verified by local `file://` install that the
   restructured tree scans **CAUTION**, not dangerous, with five inherent
   findings — all listed above and all in shipped code:
   - `guards.py:86` (HIGH) — the command-word list that *is* the guard
   - `bridge.py:167` (MEDIUM) — the machine-mode CLI call
   - `bridge.py:216` (MEDIUM) — the version probe
   - `bridge.py:253` (MEDIUM) — the human-output passthrough
   - `channels.py:30` (MEDIUM) — the control-character stripper
2. **Rewriting the uninstall documentation** as prose that names the one
   directory the plugin can leave behind and tells the reader to inspect it,
   rather than offering a copy-pasteable recursive delete.
3. **Teaching the confirm step honestly.** Onboarding copy (the plugin README
   and the install guide) will state that the scanner returns caution, explain
   each of the five findings in the reviewer's own terms, and tell the user
   that confirming is their decision.
4. **Two things we will not do.** We will not disguise, rename, encode or
   obfuscate a security fixture to slip past a scanner, and we will not
   instruct any user or agent to disable scanning. Both are recorded as
   binding constraints on the launch ticket (techtree-python-llv).

## 5. The ask

The scanner is behaving correctly on its own terms. Its CRITICALs match
strings that our tests must contain in order to prove our guards refuse them,
and its HIGH matches the word list that constitutes our command-blocking guard.
A security-tested plugin is, structurally, a plugin that contains the strings
it defends against; a scanner that blocks on their presence penalises the
adversarial testing we would want any operator plugin to have.

We ask Nous Research to consider **trusted-source status for
`regents-ai/techtree-hermes`**, or to point us at the verified-publisher path
and its requirements. The outcome we are asking for is narrow: that the
remaining honest findings — one guard word list, three fixed-argv subprocess
calls to a pinned CLI, and one control-character stripper — present to the user
as reviewable warnings they can read and confirm, rather than as a hard block
with no override.

Everything referenced here is available for inspection: the plugin repository
at the pinned commit, the certification repository with the full test battery
and release records, and the signed run receipts, which verify offline without
contacting us.

## 6. Addendum, 2026-08-21 — the cleaned tree exists

Sections 1 to 5 describe the tree at `880aa8a`, which is the tree the
DANGEROUS verdict was returned on. Everything §4 said we would do is done, and
the before and after of this appeal are now two commits a reviewer can install
and compare.

**The tree under appeal is now `0b0052fa68406ac4a63e4bf1fa1a6d00cf429815`.**
It carries the runtime, the two operator Skills, the release bytes and the
README, and nothing else: the adversarial test corpus and the repository
tooling live in `techtree-python` as `tests/plugin/` and `tools/plugin/`, where
the whole battery still runs: 791 tests green against this commit, which is
§3's 785 plus the six this cycle added — one for the rewritten uninstall
documentation, five for the environment allowlist below. That uninstall
documentation is now prose naming the one directory the plugin can leave
behind. ReleaseCore is still `sha256:c037f457…`, byte-identical in all three
repositories; the frozen `skill-improver` is still `sha256:e6bc16c4…`; the
CLI wheel is still `sha256:5a402a43…`, built from `a3ea8c58…`. Nothing
measured moved. The release record is
`release/plugin-release-candidate.json`, where `plugin_doctor` now passes all
ten checks.

**The verdict on that tree is CAUTION, five findings in three families.**
Verified by a local `file://` install of a scratch clone whose tree is
byte-identical to the tree of `0b0052fa` (git tree `dffe9e2e…` in both):

| Location | Band | Rule | Family |
|---|---|---|---|
| `guards.py:86` | HIGH | privilege escalation | the command-word list that *is* the command-blocking guard |
| `bridge.py:188` | MEDIUM | execution | the machine-mode CLI call |
| `bridge.py:238` | MEDIUM | execution | the version probe |
| `bridge.py:280` | MEDIUM | execution | the human-output passthrough |
| `channels.py:30` | MEDIUM | obfuscation | the control-character stripper |

The three bridge findings moved down the file when the environment allowlist
was added; the calls themselves are the same three. The install decision was
`BLOCKED — requires confirmation`, which is exactly the outcome §5 asks for:
reviewable warnings a person reads and confirms. Nothing was registered.

**Two hardening adoptions, from an independent source review.** A Hermes agent
belonging to the founder read the plugin's source against this dossier's
triage, corroborated it, and raised two things worth doing anyway. Both are in
`0b0052fa`:

1. **The CLI receives ten named variables and nothing else.** The bridge used
   to hand the child the host session's whole environment. It now builds one
   by name — `CLI_ENVIRONMENT_ALLOWLIST` in `constants.py`: PATH, HOME,
   TMPDIR, XDG_DATA_HOME, TECHTREE_HOME, TECHTREE_LOG_LEVEL, LANG, LC_ALL,
   LC_CTYPE, TERM — mirroring the scrub Techtree's own run launcher already
   performs on a worker. Model-provider credentials are deliberately absent: a
   run authenticates from Techtree's configuration under HOME, the same way
   the certified worker does. Five tests hold it, including a canary: a wallet
   key planted in the session reaches neither the child's environment nor any
   envelope the plugin returns. What the platform itself adds to any child
   process is measured rather than hardcoded, so the comparison is exact.
2. **The manifest declares what the plugin does with the machine.** Hermes'
   `capabilities:` is a consent registry for privileged host surfaces and
   `requires_env` gates loading and prompts for a value, so neither may carry
   a narrative. The declaration is therefore a labelled block at the top of
   `plugin.yaml`: one local executable with a fixed argument array and no
   shell, Docker only through that command, network and a paid provider only
   through a person-confirmed plan, a named environment list, an inherited
   HOME as Techtree's own authentication dependency — which is why nothing is
   prompted for — and no privileged host surface, hence no `capabilities:`.

**Two things still not done, and still refused.** No fixture was disguised,
renamed or encoded to slip past a scanner, and no user or agent is told
anywhere to switch scanning off. The onboarding copy — the plugin README and
the installation guide on the site — now states the caution verdict in
advance, explains each of the five findings in plain words, says the
confirmation is the reader's to give, and says outright that the scanning
stays on.
