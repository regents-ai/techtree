# Techtree v0.2 WP0 founder approval packet

Prepared: 2026-09-01  
Ticket: `techtree-31k.1.8` — WP0.8  
Base commit: `3355bff7fcd80ee493c8384a0ba23bf4951ab2d5`

## 1. What this packet is

WP0 has finished capturing what Techtree v0.2 will depend on. Every upstream
component was captured as far as its own surface allows — for Prime's hosted
path that was not far, and it is recorded as inadmissible for v0.2.0 rather
than worked around. Every coordinate has a digest, and every unresolved
question has been written down instead of guessed at. This packet asks you for
two things in one sitting: your signature on one exact lock digest, and your
answers to sixteen questions that WP0 deliberately did not answer for you.
Approving it fixes the coordinates the rest of v0.2 builds against and records
your sixteen answers. It does **not** adopt the lock, publish anything, start a
paid run, deploy anything, sign anything, or send anything to an upstream
vendor. Adoption is a separate follow-up ticket that the lane opens once your
answers are recorded; until then the lock's own status says
`proposed_awaiting_founder_approval_of_this_exact_digest`, and nothing in v0.2
may be described as locked.

## 2. The approval request

You are approving the exact bytes of one file. Its digest is below. The
capability matrix travels with it as a companion figure, because the lock pins
the matrix by digest and the two must be approved as one pair.

- Lock file: `docs/v0.2/UPSTREAM_CONTRACT_LOCK.json`
- Lock digest: `sha256:f4066f775f28893cc7ad7ed62b77877bcf16553e4d9de612e7c37cd808e7d5e0`
- Companion matrix file: `docs/v0.2/FABRIC_CAPABILITY_MATRIX.json`
- Matrix digest: `sha256:e769033edf1a48b5a0bc6b0693ff539a84dc1bf18680946501483f9d72939bae`
- Base commit: `3355bff7fcd80ee493c8384a0ba23bf4951ab2d5`

Each digest is a plain SHA-256 over the committed bytes of its file. You can
recompute either one yourself from the repository root:

```
shasum -a 256 docs/v0.2/UPSTREAM_CONTRACT_LOCK.json
shasum -a 256 docs/v0.2/FABRIC_CAPABILITY_MATRIX.json
```

If either file changes by one byte, this packet is void and a new one must be
prepared. That is what the lock's freeze policy means.

**Approve / Change:**

**Signature line:**

## 3. The sixteen decisions

Each decision is self-contained: what the question is, where the evidence
lives, the options, what the lane recommends, and what your answer changes.
Leave the recommendation in place by writing "as recommended", or write your
own answer.

### Decision 1 — What `claim.inspect` means

The v0.2 plan lists an operation called `claim.inspect` but never says what a
"claim" is. Two readings are possible. One is the claim a result is entitled to
make about itself: its proof grade, its decision, whether it can be published,
and any warning that it supports a weaker claim than it appears to. The other
is the release's own coordinate claims, which the existing `release verify`
command already checks. WP0 took the first reading, because everywhere else in
this codebase "claim" means what a piece of evidence is entitled to assert.

Evidence: `docs/v0.2/MACHINE_CONTRACT.md`, "Open questions for the founder",
item 1.

Options: (a) claim about a result's evidence; (b) claim about the release's
coordinates.

Recommendation: (a). Reading (b) would leave the evidence claim with no
operation of its own, and `release info` and `release verify` are already
described by `plan.inspect`.

What your answer changes: the meaning of one of the eleven stable operation
identifiers that WP1 implements. Choosing (b) would require a new operation for
evidence claims and a rewrite of the operation inventory.

Answer:

### Decision 2 — How "prepare" and "execute" map onto the existing commands

The plan lists `action.prepare` and `action.execute` as two separate machine
operations. The commands they describe already have exactly two modes: a dry
preview, and the real thing when you pass `--yes`. WP0 mapped the two
operations onto those two existing modes rather than adding a second set of
commands.

Evidence: `docs/v0.2/MACHINE_CONTRACT.md`, open question 2.

Options: (a) the two operations are the two existing modes; (b)
`action.prepare` becomes a new preparation command of its own.

Recommendation: (a). Option (b) creates a second command hierarchy, which the
v0.2 plan forbids.

What your answer changes: whether WP1 adds new commands or only new names for
the modes that exist. Option (b) would add commands, tests, and documentation
for every action.

Answer:

### Decision 3 — Keeping the three-suggestion ceiling

When the CLI answers a host agent, it offers at most three suggested next
actions. The v0.2 plan does not mention a ceiling at all. WP0 kept the existing
limit of three.

Evidence: `docs/v0.2/MACHINE_CONTRACT.md`, open question 3.

Options: (a) keep the ceiling at three; (b) remove it; (c) set a different
number.

Recommendation: (a). The reason for the limit has not changed: an agent handed
ten choices is being asked to plan rather than to act.

What your answer changes: one constant in the v2 envelope, and how much
guidance a host agent receives per response.

Answer:

### Decision 4 — Dropping the old "retryable" flag

The v1 machine output carried a plain true/false "retryable" flag on errors.
v0.2 puts a typed retry class on each suggested next action instead, which says
more. WP0 deleted the old flag rather than carrying both.

Evidence: `docs/v0.2/MACHINE_CONTRACT.md`, open question 4.

Options: (a) delete the flag; (b) keep both.

Recommendation: (a). Keeping both is dual-shape support, which the workspace
rules forbid, and the two could disagree.

What your answer changes: whether v2 consumers read one retry signal or two.
This is a hard cutover either way; there is no compatibility period.

Answer:

### Decision 5 — The side-effect and data-egress lists

Every machine response says what a command would do to the outside world (its
side effect) and what data would leave the machine (its data egress). The plan
names both fields but never lists their allowed values. WP0 derived five values
for each from what the existing commands actually do.

Evidence: `docs/v0.2/MACHINE_CONTRACT.md`, "Side-effect classes" and
"Data-egress classes", plus open question 5.

Options: (a) adopt the derived value sets; (b) supply your own.

Recommendation: (a). They are read off the real commands rather than invented,
so a host agent's safety check matches what the command does.

What your answer changes: the vocabulary every host agent uses to decide
whether it may run something without asking a human.

Answer:

### Decision 6 — How long a "wait" may wait

`run.wait` lets a host agent hold a request open until a run changes state,
rather than polling in a loop. The plan requires an explicit upper bound but
does not give a number. WP0 chose 30 seconds by default and 90 seconds
maximum, derived from the Hermes bridge's existing 120-second timeout on the
process it calls.

Evidence: `docs/v0.2/MACHINE_CONTRACT.md`, "Bounded `run.wait`", plus open
question 6.

Options: (a) 30 default and 90 maximum; (b) different numbers.

Recommendation: (a). Ninety seconds leaves headroom under the bridge's own
120-second timeout, so a wait can never outlive the transport carrying it,
which a larger maximum would.

What your answer changes: two numbers in the contract and the responsiveness a
host agent sees while a run is in progress.

Answer:

### Decision 7 — What "withdrawal removes discovery" actually means

This is the one real contradiction WP0 found. The v0.2 planning documents say
withdrawing a published result removes it from discovery. The shipped v0.1
platform deliberately does the opposite: a withdrawn entry stays in the public
log, marked as withdrawn, because a log that quietly dropped entries would have
unexplained holes in it. Decision 0038 says the same. Both cannot be true. The
question is whether "discovery" means the append-only log itself, or only the
new browsable and filtered surfaces WP5 is going to add.

Evidence: `docs/v0.2/PUBLICATION_WITHDRAWAL_AUDIT.md` §6.3 and §7.1, and
`docs/v0.2/DECISION_LEDGER.md`, section "Decisions and amendments, 2026-09-01",
entry 5.

Options: (a) "discovery" means only the new filtered surfaces; the shipped log
is untouched. (b) "discovery" includes the log listing; withdrawn entries
disappear from it, and decision 0038 must be amended.

Recommendation: (a). It keeps a shipped, deliberate v0.1 behaviour intact and
needs no amendment to a binding decision; the stored evidence, receipt, and
tombstone are preserved under either answer, and the bundle download already
returns "gone" once withdrawn.

What your answer changes: WP5 cannot build the browsable surfaces until this is
answered. Option (b) additionally requires amending decision 0038 and changing
shipped platform behaviour.

Answer:

### Decision 8 — Whether to rename the published-result envelope early

The public metadata address for a published result currently answers with the
envelope name it inherited from v0.1. v0.2 will rename it to
`techtree.published-result.v1` when it also starts carrying the new evidence
facets. The narrower question is whether to do the rename sooner, before those
facets exist.

Evidence: `docs/v0.2/PUBLICATION_WITHDRAWAL_AUDIT.md` §7.2, and
`docs/v0.2/DECISION_LEDGER.md`, section "Decisions and amendments, 2026-09-01",
entry 4.

Options: (a) rename in the same cutover as the facets; (b) rename now.

Recommendation: (a). Publishing a versioned name that is known to be about to
gain members invites consumers to depend on a half-finished shape.

What your answer changes: whether WP5 does one public cutover or two. Nothing
about the bundle download changes either way.

Answer:

### Decision 9 — Admitting NeMo Fabric 0.2.0 and its two adapters

WP0 tested NeMo Fabric 0.2.0 with the Hermes and Codex adapters in isolated,
throwaway environments. Every capability each adapter claims was admitted, and
every capability it does not claim was refused before anything ran. Nothing was
installed into, or read from, your own Hermes or Codex setup. What the test did
not do is complete a model turn: the runs were pointed at a closed local port
on purpose, so no model was called and nothing was spent. Five safety
responsibilities came out of it that Fabric will not do for us: check the
harness is present and at the right version before admitting a run; give every
Codex subject its own home directory rather than inheriting yours; treat a
started subject as impossible to cancel and bound it with a timeout instead;
work out usage from our own evidence, because Fabric reports none; and handle
Fabric's tool-definition check throwing an error rather than reporting a
failure. There is also a hard limit on what Codex can be asked to do at all:
neither adapter accepts inline tool definitions, service-account authentication
for connected tools, or tool filters, and Codex additionally accepts no tool
allow-list, tool block-list, turn limit, or temperature setting — so a Campaign
that normalises tool policy or turn limits simply cannot run on Codex. Section
4 lists this in full.

Evidence: `docs/v0.2/FABRIC_CONTRACT.md`,
`docs/v0.2/FABRIC_CAPABILITY_MATRIX.json`, and the retained evidence under
`cli/tests/fixtures/fabric/`.

Options: (a) admit both adapters as v0.2 candidates with those five gates owned
by Techtree; (b) admit only Hermes; (c) admit neither and wait for a Fabric
release that closes the gates upstream.

Recommendation: (a). The gates are all things Techtree can enforce before any
spend, they are already written down as required, and holding both adapters
back would stall WP2, WP3, and WP6 on an upstream change we do not control.

What your answer changes: the matrix's admitted-adapter list, and whether WP2
and WP6 can start. Option (c) removes Fabric-backed subjects from v0.2.0
entirely.

Answer:

### Decision 10 — Whether a Fabric-Codex comparison may claim reproducibility

When Codex starts in a brand-new home directory, it reaches out over the
network and fetches something that is not pinned to a version. WP0 observed
this. It means two Codex runs a week apart may not be running identical
software, even with every Techtree-controlled input pinned.

Evidence: `docs/v0.2/FABRIC_CONTRACT.md` and the
`codex_fresh_home_network_fetch` finding recorded against the Codex adapter in
`docs/v0.2/FABRIC_CAPABILITY_MATRIX.json`.

Options: (a) Codex comparisons are valid but must not be labelled reproducible
until the startup fetch is pinned; (b) they may claim reproducibility on the
strength of the pinned Codex version alone; (c) no Codex comparison ships in
v0.2.0.

Recommendation: (a). The claim would be one we cannot defend if challenged, and
the honest narrower claim still supports everything WP6 needs.

What your answer changes: the public wording on any Codex comparison and one
rule in the comparison-validity checks. Option (b) would make a claim the
evidence does not support.

Answer:

### Decision 11 — Pinning Hermes Agent at 0.19.0

The Hermes adapter does not install a Hermes harness; Techtree has to pin one
itself. The vendor states, and the package index agrees, that 0.19.0 is the
newest version installable this way. WP0 pinned 0.19.0 and recorded that the
statement is vendor-stated and index-consistent rather than independently
proven.

Evidence: `docs/v0.2/FABRIC_CONTRACT.md`; the `hermes_harness_supply` entry in
`docs/v0.2/UPSTREAM_CONTRACT_LOCK.json`; and the
`hermes_agent_supply_above_0_19_0` blocker in
`docs/v0.2/FABRIC_CAPABILITY_MATRIX.json`.

Options: (a) accept the 0.19.0 pin; (b) block until a newer Hermes Agent is
installable this way.

Recommendation: (a). 0.19.0 is what is actually available, and the pin is
recorded with its exact wheel digest, so a future move is a deliberate change
rather than a drift.

What your answer changes: the Hermes version every Fabric-Hermes run uses in
WP2 and WP3. Option (b) blocks WP2 on an upstream release.

Answer:

### Decision 12 — Whether the Codex trace path is in v0.2.0 at all

Relay is the optional, observe-only trace evidence. On the Hermes side almost
nothing constrains the version: the Hermes harness installs no Relay at all and
declares only a wide range, from 0.5 up to but not including 1.0, under an
optional extra. So Techtree picks the Hermes-side version itself, and the
proposed lock picks the current stable 0.8.2, which sits inside that range. On
the Codex side the version is dictated to
us: the Codex adapter in the proposed lock accepts a Relay command-line tool
only in the 0.7.2-to-0.7.x range and refuses 0.8.2. So Codex trace evidence
needs an older Relay generation, or it waits for an adapter release that widens
the range. Bear in mind while answering that no subject has yet run under Relay
through either adapter — see section 4.

Evidence: `docs/v0.2/RELAY_CONTRACT.md` and
`docs/v0.2/RELAY_COVERAGE_PROFILES/codex.relay-coverage-profile.json`, whose
recorded version conflict names the exact accepted range.

Options: (a) keep the Codex trace path in v0.2.0 on the older Relay; (b) defer
Codex trace evidence to v0.2.x and ship v0.2.0 with Hermes traces only.

Recommendation: (a). The Codex coverage profile is already drafted, and Relay
holds no authority over a score, a spend, or an execution decision, so carrying
the older generation for Codex costs supply-chain surface and nothing else.

What your answer changes: whether WP3 and WP6 build the Codex trace path now or
later, and whether decision 13 is needed at all.

Answer:

### Decision 13 — Carrying two Relay generations

This only applies if you kept the Codex path in decision 12. The release line
would then ship Relay 0.8.2 for Hermes and Relay 0.7.3 for Codex at the same
time. Neither can affect a score, a spend, or an execution decision. Both have
exact wheel digests on record: the lock names the 0.8.2 wheel digest itself and
names the 0.7.3 client by version, and the 0.7.3 digests sit in the Relay
evidence index, which the lock pins by digest in turn.

Evidence: `docs/v0.2/RELAY_CONTRACT.md`, both profiles under
`docs/v0.2/RELAY_COVERAGE_PROFILES/`, and
`cli/tests/fixtures/relay/evidence_manifest.json`.

Options: (a) accept two Relay generations in one release line; (b) refuse, which
forces answer (b) on decision 12.

Recommendation: (a), conditional on decision 12 keeping Codex. Two pinned
observe-only versions are ordinary supply-chain surface, not two behaviours in
the product.

What your answer changes: the supported version matrix and what the release
notes have to say. Nothing about scientific results changes either way.

Answer:

### Decision 14 — Admitting Relay for release

Separately from which versions ship, Relay itself is not yet admitted. The lock
currently records it as blocked pending your release admission and the answer
to decision 12. One limitation is worth knowing before you answer. Trace
coverage is a count of the events a run was expected to produce. Any event that
turns up unexpectedly is recorded as unexpected and is never a reason to call
coverage incomplete — which also means the calculation itself cannot notice if
the list of expected events were quietly shortened to make coverage look
complete. Nothing in the arithmetic protects that list. What protects it is
that the two coverage profiles, which define the expected events, are pinned by
digest inside the lock. Editing a profile does not alter the lock's own bytes;
it breaks the digest the lock records for that profile, which fails the Relay
contract test straight away. Making the two agree again means editing the lock,
and that changes the lock digest and voids the approval you are giving here.

Evidence: `docs/v0.2/RELAY_CONTRACT.md`, the two profiles under
`docs/v0.2/RELAY_COVERAGE_PROFILES/`, and the `nemo_relay` section of
`docs/v0.2/UPSTREAM_CONTRACT_LOCK.json`.

Options: (a) admit Relay for v0.2.0 as observe-only evidence; (b) leave it
unadmitted and ship v0.2.0 without trace evidence.

Recommendation: (a). It cannot influence a result, its failure modes are
recorded, and the two known weaknesses (a failed trace delivery can pass
silently, and the derived trace summary loses detail the raw stream keeps) are
both recorded in the contract and are why it stays observe-only.

What your answer changes: whether WP3 ships in v0.2.0. Option (b) removes trace
coverage from published results.

Answer:

### Decision 15 — Republishing the Prime conformance environment

The conformance environment is public at `techtree/techtree-v02-conformance`
version 0.1.0, published at zero cost on 2026-09-01 with your approval. Prime's
hub runs four checks on it. Three pass: the project file is present, the readme
is present, and it installs and imports. The fourth fails because the hub wants
a `tags` list in the project file, which is not a standard Python metadata
field. So 0.1.0 is published, installable, and importable, but not
hub-validated, and every document describes it that way. Adding `tags` changes
the source tree and the wheel digest, so it means publishing a new version.

Evidence: `docs/v0.2/PRIME_CONTRACT.md`,
`docs/v0.2/PRIME_CONFORMANCE_ENVIRONMENT.json`, and
`docs/v0.2/IMPLEMENTATION_ORDER.md`.

Options: (a) prepare a zero-cost packet to republish as 0.1.1 with the `tags`
key; (b) leave 0.1.0 published but unvalidated until Prime hosting work starts
in v0.2.x.

Recommendation: (b). Prime hosting is v0.2.x by your own decision of
2026-09-01, nothing in v0.2.0 uses the hosted path, and republishing spends a
protected action to fix a badge on a release that has no hosted consumer yet.

What your answer changes: nothing in v0.2.0 either way. Answering (a) only
authorises the lane to *prepare* a packet; publishing is still a separate
protected action needing its own approval. This is tracked as `techtree-2qy`.

Answer:

### Decision 16 — Approving the exact lock digest

This is the approval request in section 2, repeated here so the list of
decisions is complete. Your answer is the **Approve / Change** line in section
2; the lock's own approval record points at that line. If you approve, the lock
is frozen at
`sha256:f4066f775f28893cc7ad7ed62b77877bcf16553e4d9de612e7c37cd808e7d5e0`, and
replacing any coordinate in it later requires a fresh founder decision,
regenerated fixtures, and a rerun of the affected conformance checks. One
coordinate rides along without a question of its own: approving the digest also
admits the evaluation engine, Verifiers 0.3.1, as the proposed candidate, with
the development build 0.3.2.dev17 recorded only as a discovered fallback that
was never run because the stable release passed.

Evidence: `docs/v0.2/UPSTREAM_CONTRACT_LOCK.json`, its `verifiers` section, and
`docs/v0.2/UPSTREAM_CANDIDATES.json`; plus the companion
`docs/v0.2/FABRIC_CAPABILITY_MATRIX.json`.

Options: approve the digest, or ask for a change and a new packet.

Recommendation: approve, once decisions 1 to 15 are answered. Approval fixes
coordinates; it does not adopt them into production, and adoption is a separate
ticket.

What your answer changes: whether WP1 onwards may treat these coordinates as
settled.

Answer: see section 2.

## 4. What this does not authorise, and what is still broken upstream

### Not authorised by approving this packet

- Adopting the lock into production code. Approval freezes the digest; a
  separate follow-up ticket does the adoption.
  (`docs/v0.2/IMPLEMENTATION_ORDER.md`)
- Publishing anything: no package, no environment version, no release.
  (`docs/v0.2/DECISION_LEDGER.md`, "Protected actions")
- Any paid run, hosted evaluation, or model call.
  (`docs/v0.2/DECISION_LEDGER.md`, "Protected actions")
- Sending anything upstream. Issues and pull requests may be drafted locally
  and not sent. (`docs/v0.2/DECISION_LEDGER.md`, "Upstream adoption")
- Deploying to production, activating a release, or signing anything.
  (`docs/v0.2/DECISION_LEDGER.md`, "Protected actions")
- Republishing the conformance environment, even if you answer (a) to decision
  15; that needs its own packet. (`docs/v0.2/PRIME_CONTRACT.md`)

### Known upstream limitations, recorded rather than worked around

Prime (`docs/v0.2/PRIME_CONTRACT.md`, "What is still blocked", and
`docs/v0.2/PRIME_HOSTED_CONTRACT.json`). The recorded limits are unchanged by
the read-only capture, which proved response shapes and not upstream
guarantees:

- the hosted resolver forces `@latest`, so a hosted run cannot be pinned to an
  exact immutable environment version;
- creating a run, reading its logs, and stopping it have no structured
  machine output;
- there is no supported provider guarantee that a repeated submission will not
  create a second paid job;
- there is no bounded transport integrity commitment;
- there is no plan-bound cost estimate;
- there is no safe provider record of who is billed;
- there is no terminal confirmation that a cancellation actually took effect;
  and
- the provider's own documentation disagrees with its own tools about status
  and sample-pagination shapes, so live completeness is unproven.

The hub's non-standard `tags` requirement from decision 15 is a further gap on
top of these. `PRIME_HOSTED_CONTRACT.json` groups the list above into six
confirmed release blockers, with cancellation recorded separately in the lock
as unproven, and counts the hub gap as the seventh confirmed blocker. All of it
together is why hosted execution is inadmissible for v0.2.0.

Relay (`docs/v0.2/RELAY_CONTRACT.md`, and the blind spots
`no_real_hermes_relay_run` and `no_real_codex_relay_run` in the two profiles
under `docs/v0.2/RELAY_COVERAGE_PROFILES/`): **no subject has ever run under
Relay through either adapter.** The Hermes trace lifecycle was captured from a
deterministic probe with an exporter registered by hand, not from a Hermes
trajectory, and the whole Codex gateway lifecycle was read from the adapter's
source rather than executed — no gateway was launched and the Relay
command-line tool was never run. Both profiles record that as an unobserved
blind spot instead of assuming it works. On top of that, a failed trace
delivery can pass silently: a successful flush never proves anything was
delivered, and a stream sink failure is not reported at all. The derived trace
summary is lossy: two producers of the same summary format disagree on how many
steps a run had, and both erase a refused model call that the raw stream
recorded. The raw stream is therefore the only authority for coverage, and
Relay stays observe-only.

Fabric (`docs/v0.2/FABRIC_CONTRACT.md`, "What the contract does not support",
and `docs/v0.2/FABRIC_CAPABILITY_MATRIX.json`): the five responsibilities
listed in decision 9 are Techtree's to enforce, because Fabric does not —
harness presence and version, an owned home directory per Codex subject,
treating a started subject as uncancellable and bounding it by timeout,
deriving usage from our own evidence, and handling a check that throws instead
of reporting. Separately, there are controls neither adapter will accept.
Neither declares `tools.definitions` (inline tool definitions),
`mcp.auth.service_account`, or `mcp.tool_filters`. Codex declares none of
`tools.enabled`, `tools.blocked`, `runtime.max_turns`, or
`models.temperature` either, so a Campaign that normalises tool policy or turn
limits cannot run on Codex at all. That is a limit on what v0.2 can compare
across the two subjects, not something a Techtree gate can close.

Codex Relay band (`docs/v0.2/RELAY_CONTRACT.md`,
`docs/v0.2/RELAY_COVERAGE_PROFILES/codex.relay-coverage-profile.json`): the
Codex adapter in the proposed lock accepts a Relay command-line tool only in
the 0.7.2-to-0.7.x range and rejects the current stable 0.8.2. No compatibility
shim was added; it is decision 12.

## 5. Ticket-to-work-package reconciliation

Every open v0.2 ticket maps to exactly one work package. Rows marked
**proposed** are the lane's reading of a ticket's title and the work-package
definitions in `docs/v0.2/TICKETS.md`; the lane applies those links on the
tickets after you have seen this table. All other rows are long-settled.

| Ticket | What it is | Work package | Status |
| --- | --- | --- | --- |
| `techtree-31k.1` | WP0 epic: authority, conformance, and the upstream lock | WP0 | recorded, closing with this packet |
| `techtree-31k.1.8` | Freeze the proposed lock and prepare this packet | WP0 | recorded, closing with this packet |
| `techtree-31k.2` | Protocol version and v0.1 evidence | WP1 | recorded |
| `techtree-31k.3` | Fabric-Hermes parity | WP2 | recorded |
| `techtree-31k.4` | Bounded Relay evidence | WP3 | recorded |
| `techtree-31k.6` | Publish evidence facets and bundles | WP5 | recorded |
| `techtree-31k.7` | Codex subject and operator | WP6 | recorded |
| `techtree-g34` | Rate limiting and docs listing for the bundle address | WP5 | recorded, child of `techtree-31k.6` |
| `techtree-31k.8` | Multi-file starter fetch and revision context | WP2 | proposed — it changes what a subject is given to work on, which is WP2's subject backend |
| `techtree-31k.9` | Remove duplicate plugin CLI reads | WP1 | proposed — the plugin's reads are rewritten when WP1 migrates consumers to the v2 contract |
| `techtree-31k.10` | Report public task prompts generically | WP1 | proposed — it changes what engine inspection reports, which is WP1's reader and schema work |
| `techtree-31k.11` | Receipt token and elapsed-time usage | WP1 | proposed — it changes receipt contents and regenerates goldens, both WP1 deliverables |
| `techtree-31k.12` | Credential shape versus authentication | WP2 | proposed — WP2 owns the credential canaries and the pre-spend provider checks |
| `techtree-k7t` | v0.2.x hosted-execution epic, which holds WP4 | WP4, v0.2.x | recorded |
| `techtree-31k.5` | Prime Hosted Evaluations | WP4, v0.2.x | recorded, under epic `techtree-k7t` |
| `techtree-2qy` | Republish the conformance environment with hub tags | WP4, v0.2.x | recorded, and it is decision 15 above |
| `techtree-33x` | Techtree Market epic | outside v0.2.0 | v0.2.x, blocked by `techtree-31k` |
| `techtree-8dj` | Techtree Foundry and first Skill Climb epic | outside v0.2.0 | v0.3 |
| `techtree-5t7` | Deferred studies: Prime Agent, prime-rl, uplift, and the rest | outside v0.2.0 | v0.3.x, deferred until Foundry evidence exists |

Two maintenance tickets sit under a different work package than `TICKETS.md`
originally gave them: `techtree-31k.9` moves from WP2 to WP1, and
`techtree-31k.10` moves from WP0 to WP1. Both are consumer-and-reader changes
against the machine contract WP1 replaces, and WP0 ships no production code.
`TICKETS.md` already reflects that proposed mapping, so the two documents
agree; the lane applies the links on the tickets themselves once you have seen
this table.
