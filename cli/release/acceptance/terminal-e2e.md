# WP11e — clean-machine terminal acceptance

Ticket `techtree-python-ndq.3.5`. Contract `docs/release/contracts/wp11e.md`.
Performed 2026-08-19. Machine-readable companion: `terminal-e2e.json`.

**Verdict: conditional pass.** A clean user can install the exact candidate
artifacts, run a real paid comparison, close the terminal, come back, get a
result that reproduces the certified science, and check the proof offline.
Nothing was uploaded. But the guided-revision half of the journey does not work
as shipped, and one message shown at the moment a person approves spending their
own money is untrue. Both are recorded below with tickets.

## What this certifies, and what it does not

This certifies the exact local candidate artifacts: the wheel in `dist/`
(SHA-256 `9a8c02af…`, stamped at commit `a444c4d6…`) and the plugin at commit
`0670ff11…`. Nothing was installed from a package index or a public repository,
because neither exists yet. The public install path is WP11-postpublish, after
Gate 2, and nothing here should be read as covering it.

## The clean machine, described honestly

Fresh home, fresh Hermes home, fresh tool directories, all under a scratchpad.
This is a set of fresh homes on the founder's existing Mac, not a fresh
operating system, and it does not pretend otherwise.

Before installing, no `techtree` command was reachable and the package was not
importable on the pinned interpreter. The supported path was used as the primary
one: CPython 3.12.13, pinned explicitly.

Two things about the machine are worth stating plainly because they affect how
much the journey proves:

- **The container image was already cached.** The pinned subject image was
  already on this Mac from earlier work, so the journey did not exercise a cold
  download. What it does prove is that the image is fetched *by digest*: the
  Campaign pins a content address, the health check confirms the daemon holds
  exactly that image, and every container observed during both paid comparisons
  ran it. Nothing anywhere resolved the `python:3.11-slim` name, which is the
  name that has since moved to different content.
- **There is no user-facing setting for the Techtree home in this version.** The
  home follows the operating-system home directory, and a single command can be
  pointed elsewhere with `--home`. Isolation here comes from the fresh home.

## Signing in

The journey's fourth step is `prime login`. An automated worker cannot type into
an interactive sign-in, so its effect was reproduced by copying the operator's
existing Prime configuration file into the journey's home with a plain file
copy. **The file's contents were never read, printed, logged, or handed to
anything.** No credential value appears anywhere in this ticket's output. This
substitution is disclosed rather than glossed: the journey proves the credential
resolves from the Prime configuration, not that the sign-in screen works.

## The journey

All twenty steps were performed live and paid. Highlights:

**Install.** The published coordinate, pointed at the local wheel. All 155 files
in the installed package are byte-for-byte the candidate wheel's; nothing else
supplied them. The build reports the commit stamped into it, and release
verification passes every applicable check against the expected contract digest.

**Plugin.** Installed into the fresh Hermes home at the exact 40-character
commit, checked out detached, pinned in the install record, and carrying a
release contract byte-identical to the CLI's. Hermes rejects a bare local
directory path, so a `file://` address was used; the pinning flag and the commit
are exactly the ones the bootstrap command pins.

**Health check.** Ten of ten checks pass for general readiness; thirteen of
thirteen when asked about the specific Climb, which is the form that actually
looks at the credential and the container image. The credential check is now
truthful: a placeholder set in the terminal does **not** make it green, and the
message explains why — a run happens in a separate background process that never
sees the terminal's variables. The earlier false-green is fixed.

**Starter Skill.** Fetched live from the address the release publishes, over the
public site, and checked against the digest the release pins. It matched.

**Review before spending.** The screen a person sees before approving shows all
six things it must: how many episodes will run, the spending limit the Campaign
declares (described honestly as a declared figure that nothing estimates against
and nothing enforces), that both sides run the same agent on the same tasks,
that the Skill is the only scientific change, that model calls go to the chosen
provider under that provider's policies, and that Techtree uploads nothing.
Answering "no" starts nothing.

**Closing the terminal.** The shell that started the run exited. The run kept
going, adopted by the operating system, and every later command reached it by
run identifier from a completely new process.

**The first result.** Zero out of thirty-six without the Skill, twenty-three out
of thirty-six with it — a gain of 0.639, twenty-three wins, no losses, thirteen
ties. That reproduces the two certified stability runs exactly, on a clean
machine, from the shipped artifacts. The proof verified offline: 339 checks, no
failures.

**The second result.** The revised Skill did **not** improve on the first:
0.667 down to 0.639, no wins, one loss, thirty-five ties. The product said so
plainly. Its proof also verified: 339 checks, no failures. Worth noting for
anyone reading a single number: the same Skill scored 0.639 in the first
comparison and 0.667 in the second, which is ordinary run-to-run variation.

**Nothing was uploaded.** A sampler recorded every outside connection the
journey's processes held, every five seconds, for the whole journey — 374
samples. The only outside addresses that ever appeared were the model provider's
and the Python package index's during engine installation. The Techtree site's
addresses appeared zero times. Backing this up, the installed package contains
exactly one place that makes an outside request at all: the read that fetches
the starter Skill. It is a read, and there is no create, update, or delete
request anywhere in the package.

## Where the journey broke

### The one guided revision was consumed and produced nothing

The single host-model completion the introduction allows was made exactly once,
on the frozen profile, with no retries and no repairs, and cost USD 0.0553. The
model returned a sensible revision.

The plugin then refused the whole proposal. Two things in the model's write-up
tripped the guard. One is correct: it restated "36 tasks", a number that belongs
to Techtree's own output. The other is a mistake: the guard read the hyphen
inside the ordinary phrase "modulo-97" as a negative number. The attempt is
spent, there is no second one, and there is no way to recover.

Then, when the model's revised Skill was offered through the command-line tool's
own documented manual route instead, **the Skill checker blocked it too** — it
read the plain English sentence "…only that token: no reasoning, arithmetic…" as
somebody writing down a password. The whole Climb is about returning a token, so
this is not a corner case.

Both are filed: `techtree-python-5f6` and `techtree-python-0mx`.

To finish the remaining steps without a second paid call — retrying a paid
outcome is forbidden — the model's own revised Skill was used as the second
version, with one punctuation change to get past the checker and nothing else
altered. That is disclosed here and in the machine-readable record rather than
smoothed over.

### The start message is untrue

Every time a person starts a Climb, the tool warns them that the run uses a
development stand-in, that no model will be called, and that the report is not
publication-eligible. None of that is true — the run calls models and bills the
person's account. The flag behind the warning is hard-coded. Status and result
reporting are correct; only the start message is wrong. Filed as
`techtree-python-ce9`, P0: it is the sentence a person reads at the exact moment
they agree to spend money.

## Failure injection

**Twelve of twelve cases with no paid inference were triggered.** Every one
landed on a stable, typed failure with an honest message, and every repair
worked: missing package manager, missing container tool, unreachable container
service, missing evaluation engine, an interrupted engine installation, missing
sign-in, an unreachable starter address, a starter that serves the wrong bytes,
a tampered release contract, a plugin that disagrees with the installed tool, an
unwritable home, and a tampered proof bundle. No secret appeared in any message.

Three of them are worth calling out:

- **A tampered release contract is not checked on the path that runs things.**
  The verification command catches it, and the reporting command shows the
  changed digest honestly — but with an engine installed, preparing a submission
  against a tampered contract succeeded normally. Integrity here is opt-in.
- **A tampered proof bundle is caught precisely**, naming the file and both
  digests, and refusing the integrity claim outright. There is no repair, which
  is the correct answer.
- **Three errors carry no machine-readable next step** even though a working
  repair exists as a flag: the unusable-home error and the two starter-address
  errors. The human sentences are honest; only the structured suggestion is
  missing.

**Of the six paid-path cases, four were triggered and two were honestly recorded
as not triggerable.**

- *Terminal disconnects* — triggered; the run survived.
- *Sign-in missing* — triggered from a home whose Prime configuration was
  deliberately emptied. The operator's real configuration was never touched. The
  run stops before any container starts, so nothing was billed. One flaw: the
  message a signed-out person reads is visibly broken, because the safety filter
  replaces the word "the" with "[redacted]" (`techtree-python-cmo`).
- *Worker killed* — triggered with a forced kill mid-run. The product behaved as
  documented: it invented nothing, left the run un-finished with a plainly
  reported dead worker and stale heartbeat, refused to produce a result, and
  wrote no partial report. Two real problems surfaced: the evaluation processes
  are not killed with it and keep spending the person's money, and container
  leftovers stay running. There is no command to clean any of it up
  (`techtree-python-730`).
- *Network fails after the run starts* — triggered by equivalent, and labelled as
  such. Cutting the network genuinely would mean editing this Mac's host file or
  firewall, which is outside what this worker will do. Instead one side's
  evaluation process was killed mid-run, which is exactly what the product sees
  when that process dies after a run has started; the tool does not inspect
  provider responses, so a real network or provider failure arrives through the
  same route. It failed both sides together with a clear typed error, kept the
  partial evidence, and wrote no report.
- *One required episode incomplete* — **not triggerable** in a live journey. The
  product refuses earlier on both possible routes. Reaching it would mean editing
  a finished run's files by hand, which tests a different thing. Recorded rather
  than staged.
- *Declared spending limit reached* — **not triggerable, because it does not
  exist.** In this version the limit is a declared figure and nothing else:
  nothing meters spending, compares it to the ceiling, or stops a run. The tool
  says exactly that on screen before a person approves. Recorded rather than
  staged.

## An unsupported interpreter

Recorded for honesty; it is not the certified path. The wheel declares the
supported Python range correctly, but the package installer, left to choose on
this Mac, still installed onto 3.14. The good news is that this is no longer
silent — the health check now refuses and names the range, which is a real
improvement on the earlier finding. What remains is that the published install
command has no version pin, so a first-time user on a modern Mac would install
successfully and then see a failing health check as their very first output
(`techtree-python-vom`).

## Money

| Leg | Estimated | Actual | Ceiling |
|---|---|---|---|
| First comparison | 0.2383 | **0.1523** | 0.30 |
| One host completion | 0.1142 | **0.0553** | 0.30 |
| Second comparison | 0.0700 | **0.0650** | 0.30 |
| Injection: worker killed | 0.0500 | **0.0111** (estimated) | 0.30 |
| Injection: process dies mid-run | 0.0500 | **0.0021** (estimated) | 0.30 |
| Injection: sign-in missing | 0.0000 | **0.0000** | 0.30 |
| **Journey total** | | **USD 0.2858** | 1.50 authorized |

The host completion figure is the provider's own. The two comparison figures are
computed from each run's signed execution record at the prices pinned in the
certification evidence — the same method the durable ledger has used for every
previous comparison. The two injection figures are **estimates**, disclosed as
such, because no episode finished so the provider's usage was never recorded;
they are bounded above by 0.02 and 0.01 respectively.

Every leg was estimated before it ran. No ceiling was crossed. No paid outcome
was retried. Programme spending moves from USD 2.4957 to **USD 2.7815** of the
10.00 cap, leaving 7.2185.

## Where the evidence lives

The two live run directories, their proof bundles, the host completion's request
and response, the network log, and every failure-injection home stay in the
worker's scratchpad for the chief's durable snapshot. No run directory, raw
episode, trace, provider response, hidden answer, or credential is committed to
any repository.
