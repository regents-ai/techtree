# WP11f — agent-first onboarding acceptance

Ticket `techtree-python-ndq.3.6`. Contract `docs/release/contracts/wp11f.md`.
Performed 2026-08-27. Machine-readable companion: `onboarding-e2e.json`.
Conversation record: `onboarding-e2e-transcript.md`.

**Verdict: conditional pass.** Every approval gate the contract names holds.
Nothing installed without a person answering for it. No command the product put
in front of anyone carried a floating coordinate. The paid Hello World
comparison reproduced the certified science exactly and its proof verified
offline. The one guided revision completed end to end — the first time in this
programme that it has — and the second comparison ran on its own separate
approval, and its proof verified too.

What does not hold is the half of the journey that happens before any of that.
The operator Skill — the one document a Hermes agent is told to load before it
touches a Techtree tool — states, without qualification, that this build cannot
run the Hello World comparison and that its release coordinates have not been
chosen. Both statements are false of this candidate. An agent that reads them
and believes them tells the user the journey is impossible, in its first reply,
before anything is installed.

## Who performed this, and what it does not cover

The operator was an acceptance worker, not the founder. Six approvals were
given during this journey — install the plugin despite a caution verdict,
enable it, install the CLI, start the first paid comparison, make the one host
completion, start the second paid comparison — and every one is recorded as an
operator approval and not a founder approval.

**A throwaway Hermes home.** The founder's own Hermes was not touched and not
restarted. Everything ran against a fresh Hermes home under a scratchpad, which
has no model and no provider configured. So the plugin-install and restart legs
establish that the pinned commit installs, that it is pinned, and that its
sixteen tools load — and they establish **nothing about the founder's own
working Hermes**. No live Hermes agent conversation was possible and none was
held; the journey was driven through the installed plugin's own tools, with a
minimal facade standing in for Hermes' plugin context and, for the one guided
revision, for its host-model seam. The plugin's own compose path, one-shot
wrapper, guards, digests and command bridge are the installed plugin's,
unchanged.

The founder walked the real-Hermes path himself on 2026-08-27 on a prior build
of the same lineage, producing `run_b3e25a431d3b43128deb31e99a0b6c68`. That is
the record for the leg this journey does not cover.

**Nothing is published.** `github.com/regents-ai/techtree-hermes` answers 404.
`techtree.sh/start` is live and was read, but it declares itself a placeholder
and the three commands it publishes name a forty-zero commit and a version
called `0.0.0-placeholder`. So the pinned instructions were read where they
actually live before Gate 2: the local candidate at commit `df5ead2b…`. Nothing
here covers the public path. That repeat is WP11-postpublish.

## What this certifies

| | |
|---|---|
| wheel | `dist/techtree-0.1.0-py3-none-any.whl` |
| wheel sha256 | `e486b3ea…`, recomputed here, and the digest the release record names |
| stamped source commit | `5d793b69…`, read from inside the wheel |
| plugin | `../techtree-plugin` at `df5ead2b38316a8def7837ae0bedfe8c1d5c64a4` |
| release contract | `sha256:bef3b9d4…`, carried byte-identically by the plugin and the installed CLI |

The repository was one commit past that freeze commit while this ran; that
commit is the release-record commit, and the artifact under test is the frozen
one.

## The twelve acceptance points

| # | What decision 0024 §3 asks | Verdict |
|---|---|---|
| 1 | A user with Hermes already installed can paste one instruction | partly established |
| 2 | Hermes reads the exact pinned GitHub release instructions | **not established** |
| 3 | It explains prerequisites, commands, cost, provider, local-data policy | established, with a defect |
| 4 | It asks before installing anything | established |
| 5 | It installs/enables the exact plugin release | established |
| 6 | It tells the user to restart/reset Hermes once | established |
| 7 | After restart, the plugin offers the pinned CLI installation | established |
| 8 | It asks before installing the CLI | established |
| 9 | It runs release verification and doctor | established |
| 10 | It starts Hello World only after the paid-run approval | established |
| 11 | Every CLI/plugin response includes the useful next step | partly established |
| 12 | No command uses `main`, `latest`, or an unpinned coordinate | established |

**1 — partly established.** The one instruction exists and is published
verbatim on the pinned guide; the plugin's README publishes a second wording of
it. That a *live* Hermes agent given that prompt carries the journey out was
not established and could not be, for the reason stated above.

**2 — not established.** The repository the guide names does not exist, and the
guide itself is a declared placeholder. What was established is the substitute
the contract allows before Gate 2. This point cannot close before publication.

**3 — established, with a defect.** Between the guide, the README and the
operator Skill, all five are covered: the prerequisites, the exact commands,
that money is spent and that no figure is worked out in advance, that model
calls go to the configured provider under that provider's policies, and that
Techtree uploads nothing. The CLI's own pre-spend review repeats every one of
them. The defect is inside the operator Skill itself — see the first finding.

**4 — established.** Three gates, all held. A plugin install with no terminal
anyone could answer at was refused outright and installed nothing. On a real
terminal Hermes asked twice and installed nothing until both questions were
answered. The CLI install went through the host's own terminal approval; the
plugin builds the command and hands it over, and never runs an installer
itself. Replaying a spent installation plan was refused. `--force` was never
used.

**5 — established.** Installed at the exact forty-character commit, checked out
detached, clean, recorded as pinned in Hermes' install metadata, enabled in the
home's configuration, and carrying a release contract byte-identical to the
CLI's.

**6 — established.** The guide and the README both say it, and Hermes says it
itself after enabling. No Techtree-authored runtime surface says it: the
instruction lives only in the documents and in Hermes' own output.

**7 — established.** The plugin offered exactly one plan,
`uv tool install --python 3.12 techtree==0.1.0`, generated from release data and
marked as needing confirmation.

**8 — established.** The plan is single-use, expires in fifteen minutes, and is
looked up by opaque identifier rather than received, so the command that ran is
the command that was offered.

**9 — established.** Release verification passed twelve checks against the
expected contract digest. The health check passed fourteen of fourteen for the
specific Climb, including the credential check and — for the first time in a
Techtree acceptance — the check that the plugin is installed and switched on
for this Hermes. WP11e's journey had no Hermes on its path, so that one was
skipped there.

**10 — established.** A start that was not approved exited with
`policy_acceptance_required` and started nothing. Both paid runs recorded that a
person approved them on the host agent's surface, and the first recorded that
the executor was not a fake one. Replaying an already-started draft returned the
same run identifier and started nothing new. The second comparison took its own
approval.

**11 — partly established.** Twenty-one of the twenty-three product responses
this journey captured carry a machine-readable next step, and they are useful
ones. Three do not, and — more seriously — the chain itself loops: browsing
Climbs leads to looking at one, which leads to "check that the installed
evaluation engine is intact", which can never be satisfied. An agent following
next steps never arrives at Hello World.

**12 — established.** Every command the product surfaced was scanned. All are
pinned, including the placeholder guide's stand-ins, which are pinned-shaped.

## The restart question, asked of the software

This was re-checked rather than assumed, because a previous diagnosis of it was
wrong.

A brand-new `hermes` process sees a newly enabled plugin immediately, with
nothing restarted: the plugin health check reported sixteen tools and two hooks
registered, and the toolset showed as enabled, in fresh processes with no
restart of anything in between. Hermes runs plugin discovery once per process at
startup, so what needs restarting is any process that was **already running**
when the plugin was enabled.

On the agent-first path that is exactly the situation — the session the user
pasted the prompt into is such a process — so the guide is right for this path.
It is over-broad for a terminal, where no restart is needed at all. And Hermes'
own line after enabling, "restart the gateway for the plugin to take effect",
is narrower than the case that actually matters here: it names the background
service, not the chat session.

## What it cost

| leg | estimate | actual | where the actual came from | ceiling |
|---|---|---|---|---|
| first comparison | 0.2383 | **0.1168** | derived from the run's token counts | 0.30 ✓ |
| one guided-revision host completion | 0.1816 | **0.0441** | reported by the provider | 0.30 ✓ |
| second comparison | 0.1200 | **0.0580** | derived from the run's token counts | 0.30 ✓ |
| host call refused at the provider edge | 0.0000 | **0.0000** | nothing was generated | 0.30 ✓ |
| **total** | | **0.2189** | | authorised **1.50** |

Every leg was estimated before it ran. No leg exceeded its ceiling. No paid
outcome was retried. The provider reported a figure for the host completion and
for neither comparison; the comparison figures are Techtree's own arithmetic
over the runs' token counts at prices recorded 2026-08-20, and the record says
so rather than presenting them as billed amounts.

## The results

**First comparison** — `run_618a27f7fde4465ebe02a6bf33b71f7c`.
Zero out of thirty-six without the Skill, twenty-three with it: 0.000 → 0.639, a
gain of 0.639, twenty-three wins, no losses, thirteen ties. That reproduces the
certified stability pair exactly, on a fresh home, from the shipped artifacts.
Proof grade P1. The proof verified from the stored bytes with nothing fetched:
**339 checks, no failures**.

**The one guided revision.** One host completion on the frozen profile — one
outbound request, no retries, no repairs, finish reason `stop`. A usable
proposal came back and neither guard rejected it, which is the first time that
has happened in this programme. The model proposed reducing each
position-weighted product as it went rather than summing everything and
reducing once at the end — the same arithmetic, but nothing intermediate grows
large. Fourteen lines added, five removed, nineteen changed. It stated its own
confidence as medium.

**Second comparison** — `run_4584be6d8e1248ce9495a51ce2059fee`.
0.639 → 0.667, a gain of 0.028: one win, no losses, thirty-five ties. The
revision moved one task out of thirty-six. That is what the product said, with
no verdict attached, and no verdict is attached here either. Proof grade P1,
and its proof also verified: **339 checks, no failures**. Worth noting for
anyone reading a single number: the same Skill scored 0.639 as the first
comparison's candidate and 0.639 as the second's baseline, which is the two runs
agreeing with each other.

## Where the journey breaks

### The operator Skill tells the agent the journey is impossible

This is the finding that matters. The operator Skill is loaded before any
Techtree tool is used, and it contains a section headed "What this build cannot
do yet" which says, flatly, that Techtree Hello World stops before preparing a
comparison because the starter Skill has not been chosen for this release, and
that proposing a revision stops for the same reason. Its troubleshooting
reference goes further: the release coordinates have not been chosen, it will
not install Techtree, it cannot prepare the guided introduction, and — the
sentence that closes the door — "there is nothing to fix locally, and a
published build is the answer."

None of that is true of this candidate. Both founder Skills are pinned by
digest. The CLI installed. The introduction prepared. Both comparisons ran and
both proofs verify. The text is left over from before the founder Skills were
chosen, and it survived because the copy contract that scans these documents
checks for forbidden claims and required framing — it has no rule that a claim
about what the build cannot do must match what the release actually pins.

### The install-time scan says something different from what the user was promised

Both the guide and the README tell the user in advance exactly what the security
scan will report: five findings in three families, and they list all five.
The scan reports six, in four. Hermes' own decision line says "6 findings". The
sixth is a HIGH privilege-escalation flag on the very document that explains the
other five, because that document quotes the list of command words the plugin
refuses. A careful user comparing the promise to the screen finds an
unexplained HIGH finding at exactly the moment they are being asked to trust the
plugin — and the promise was made to spare them that.

### The engine can never become verified

`techtree setup` says the engine is installed, verified and active.
`techtree engine verify` says "installed and verified, active". And every Climb
surface — list, show, inspect, and the guided introduction's own preparation —
keeps reporting the engine as unverified, keeps warning about it, and keeps
offering "Check that the installed evaluation engine is intact" as the next
step. It is not a stale cache: the code that answers that question can only ever
say "not installed" or "installed but unchecked". There is no third answer to
reach. So a user is told to do something they have already done, and doing it
again changes nothing.

### The guided introduction does not survive a restart

The run survives session loss exactly as the contract requires — it kept going
after the process that started it exited, and every later command reached it by
run identifier from a completely new process. The *introduction* does not. Its
session lives only in the memory of the Hermes process that created it, so it is
lost by an ordinary session end, by a crash, or by the restart the guide itself
instructs. The first comparison takes about eleven minutes, which is a wide
window. Afterwards the run is still there and its result still reads, but asking
for the revision refuses with "there is no guided comparison in this
conversation to improve on", and offers no repair. The store carries a seven-day
expiry constant that never applies, which suggests keeping it was intended.

### The answer an agent gets is the phone-shaped one by default

The plugin returns a bounded, chat-safe form of every answer unless the caller
names the terminal explicitly. Hermes publishes no field the plugin could read
to work it out, and the operator Skill never mentions the argument, so an agent
that does not happen to pass it gets the compact form. This journey hit it live:
the guided-revision proposal came back without its request accounting, its
draft digest or its provenance — the fields the record is made of. For a release
whose framing dropped the phone client entirely, the phone-shaped answer is
still the default.

### Smaller things

- The approval event recorded for both runs carries no draft digest. The plugin
  looks for one where the CLI does not put one. That is the single field that
  makes "a person approved this exact draft" checkable by eye.
- The published install command on the guide omits the interpreter pin, while
  the same page's prose promises the installer brings its own Python 3.12. Only
  the plugin's generated command actually names it. This is WP11e's
  `techtree-python-vom` surviving on the website surface.
- `techtree run status` prints "Progress — not started" directly above a table
  showing episodes completing on both sides.
- The second comparison's result does not say how many tasks it ran; the first
  one does.
- One successful response gives its next step only as a sentence rather than as
  a next action, and two typed refusals carry no repair at all.
- The wheel ships with no checksum file beside it, so a participant has nothing
  local to check a download against.
- The guide's own plugin-install command ends in `--enable`, which pre-answers
  one of the two questions a user would otherwise be asked. The one that
  matters — install this at all? — still fires.

## What WP11e found, re-checked

| ticket | was | now |
|---|---|---|
| `ce9` (P0) | the approval screen said no model would be called | **fixed** — no such claim, and the run recorded a real executor |
| `5f6` (P1) | a guard ate the one revision over a hyphen | **did not fire** — the revision completed |
| `0mx` (P1) | the scanner blocked an ordinary sentence about tokens | **did not fire** — the proposal passed |
| `cmo` (P2) | the sanitizer redacted the word "the" | **fixed** — decision 0036 removed shape-based inspection entirely |
| `g5m` (P2) | the README named the wrong health-check flag | **fixed** |
| `vom` (P2) | the published install command landed on Python 3.14 | **fixed in the plugin, still wrong on the website** |
| `730` (P2) | a killed worker orphans its children | **not retested** — no worker was killed here |

## Stop conditions

None triggered. Nothing installed without an explicit approval. No surfaced
command carried `main`, `latest`, or an unpinned coordinate. No surface claims a
certified phone path — the public guide contains no reference to a phone, a
mobile client or iOS, and says plainly that Hello World needs a host with a
terminal and Docker. There was no budget shortfall: USD 0.2189 of the 1.50
authorised.

## One correction to this journey's own method

An early attempt put the whole of the operator's local bin directory on the
journey's path in order to reach Hermes. That directory also holds the founder's
own globally installed Techtree, and three health-check runs silently used it
instead of the candidate — which is how an older build's smaller check set
appeared and was briefly mistaken for a defect in the candidate. It was
corrected by putting only Hermes on the path. The affected files are kept and
named so, and nothing in this record rests on them.
