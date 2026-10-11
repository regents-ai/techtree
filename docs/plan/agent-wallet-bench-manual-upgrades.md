# Manual upgrades and version comparisons

Sean requested this first on 10 October 2026: manually test a changed harness
against every supported wallet, or a changed wallet against every supported
harness. Prime Agent Rust 0.10.0 is the first added harness (H16). Credits charging
is deferred.

## Plan before spending

From `platform/`, create a reviewable manifest. Planning and validation start no
application, create no database records and make no provider calls.

```sh
mix techtree.wallet_bench plan --axis harness --id H16 --version 0.10.0 --operator sean --output prime.json
mix techtree.wallet_bench validate --manifest prime.json
```

This plans four attempts, one each against W01 (Bankr), W03, W07 and W13. The
counterpart versions come from the reviewed survey defaults, not a claim that
they are the latest releases. Edit exact counterpart versions in the manifest
when needed and validate again. `--repeats 2` or `3` repeats each pair.

To test a wallet upgrade against all ten supported harnesses:

```sh
mix techtree.wallet_bench plan --axis wallet --id W01 --version 0.3.45 --operator sean --output bankr.json
mix techtree.wallet_bench validate --manifest bankr.json
```

Cline remains installation-only because its adapter cannot resume a conversation.
Every other admitted harness runs installation and wallet/signature tasks.
No batch admitted by this workflow funds a wallet or runs the money tests.

Versions must be exact; `latest`, moving aliases and shell syntax are rejected.
Hermes upgrades also need `--source-ref FULL_40_HEX_COMMIT`. Prime and oh-my-pi
upgrades need `--archive-sha256 FULL_64_HEX_SHA256`, taken from the exact upstream
release asset. A changed version never inherits the old archive checksum or
source commit. The checked-in defaults are in
`platform/priv/wallet_bench/runner/harnesses.json`.

## Start only after operator approval

Review the complete manifest and obtain Sean's approval for its provider costs.
Each attempt's model proxy caps the attempt's model calls at $5. Every call in
flight holds $0.33, the most one call can be priced at (922,000 input tokens all
written to the cache and 128,000 output tokens, at gpt-6-luna's long-prompt
price), and a call that would take the recorded cost plus every held amount past
$5 is refused. Calls a harness makes at the same moment therefore cannot overshoot
the cap together, and each request gets one answer and reaches the model once. A
request reusing an earlier call id is refused, also after a proxy restart. Only
the harness's own tools reach the model, and no request runs in the background:
OpenAI's hosted tools (web search, code containers and the like) and background
responses are billed apart from the answer. The Responses route takes ordinary
requests only, not its WebSocket mode, which would make many calls under one hold. A stream the harness stops reading
is charged the full $0.33, because the model may have done more work than the
part delivered shows. A failed call is free when the model server answered with
an error, and costs $0.33 when no answer came back. After a proxy restart, a call
that was still running is charged $0.33. The harness's token reaches only the
chat, Responses and Anthropic Messages routes (with the token counter and model
list), so LiteLLM's direct-forwarding, batch and file routes cannot skip the cap.
The proxy prices calls at
gpt-6-luna's list price, including cache writes and the higher price above
272,000 input tokens; check it against OpenAI's model page before a paid run.
Four attempts have a combined $20 model cap, and the plan reports it. Judge
calls and Sprite costs are additional.

The manifest contains no credentials. New batches are unassisted: they do not
inherit the supplied Bankr account or paid hosted-agent access from earlier
reruns. If a task needs that access, its result records the limitation. Supporting
an assisted batch requires a separate, reviewed change.

Apply the two new site migrations through the normal approved release procedure,
then start the approved manifest in the intended operator environment:

```sh
mix techtree.wallet_bench start --manifest prime.json --execute
mix techtree.wallet_bench status --batch BATCH_UUID
```

Status starts only the database dependencies; it cannot launch workers. Start
launches the application and admits jobs to the existing Oban queues. In a
running deployed release, use its operator RPC to call
`Techtree.WalletBench.Batch.start(Jason.decode!(manifest_json))`; do not run a
second application against the production database. Do not paste credentials
into manifests, RPC arguments or logs.

Reusing the same complete manifest returns the existing attempts. Concurrent
submissions cannot create duplicate batch/pair/repeat records or machines. If one
racing caller loses the unique constraint, resubmit the same manifest. A changed
version or run condition needs a new plan and batch UUID.

## Clean checkpoints and observed versions

Each batch requests a new Sprite baseline for each selected harness. The existing
runner builds it from the exact pin, verifies the installed harness version,
checkpoints it and restores that clean checkpoint between attempts. Batches never
borrow one another's baseline. A failed or retired baseline fails admission to
that machine rather than waiting forever, and a baseline build still running
after an hour is stopped and fails. Wallet CLIs are installed by the tested
agent inside each clean attempt; there is no wallet-only Sprite pool. These
batches are unassisted, so a Bankr (W01) attempt resets the batch machine like
any other; only an attempt given the operator's Bankr account retires it.

Every new batch freezes the site release, execution recipe, test protocol,
model, reasoning level, judge and access conditions. A new site release, or a
changed recipe, protocol or judge, stops the batch; make a new plan rather than
mixing conditions within it. Do not deploy Techtree while a batch is running.

Installation and every wallet/signature turn must independently verify the exact
requested wallet version in a successful version command. Failed commands,
command paths and package inventories do not count as version proof. A missing or
changed version cannot receive a pass. The proof records what the installed
wallet command reports; an agent that deliberately replaces that command or its
login environment with a fake one can still forge it. Such a replacement shows
in the turn's recorded commands, which the judge and reviewers read. Safety rulings and signature criteria stay
intact. The captured evidence remains available on the attempt page.

## Patchbay comparisons and history

The database's existing read-only views retain their columns, run numbers, grants
and history. `versions` gains `batch`, `requested_wallet`, `protocol` and `access`.
A new installation or wallet row also has `wallet_verified`; if its installation
or any wallet/signature turn cannot verify its release, the actual `wallet`
value is null. Requested and roster
versions are never substitutes for an observed version.

Patchbay owns exact-version filters and side-by-side comparisons. Group by actual
harness/wallet versions and recorded model, reasoning level, OS, judge, recipe,
protocol and access. Batch IDs identify provenance, not distinct releases.
Compare recorded outcomes and check counts. Flag changed conditions and missing
historical metadata; do not call those differences a controlled regression.
Historical unknown conditions remain unknown, and all prior runs stay available.

Both new migrations roll back together. The view migration saves the original
view definitions in a private site table and restores them before removing the
new attempt/machine fields. Existing dependent views and grants remain intact.

To add another harness later, implement its pinned Harbor adapter, register it in
both catalogs and the public roster, and add its reviewed pin. Verify installation,
first turn, resume and trajectory handling locally before admitting paid attempts.

## First Prime batch: Linux acceptance and total budget

Prime H16 has passed locally on macOS only. The first batch in the deployed
release is also its Linux acceptance. It runs only after Sean approves both the
release carrying the two migrations and a total budget for this batch.

Cost basis: the ten approved Bankr reruns of 9 October cost $4.89 in all
(coding and judge $2.77, Bankr $0.28, machine estimate $1.84), about $0.49 per
attempt. The four Prime attempts share one baseline machine, so they run one
after another.

| | Amount |
| --- | --- |
| Expected, at the 9 October rate | about $3 |
| Model cap, 4 × $5, enforced by each attempt's proxy | $20 |
| Judging and machines, estimated from the 9 October rate with room to spare | up to about $5 |
| Proposed total ceiling | $25 |

Only the $20 model part is enforced. Judging is a few calls per turn, and each
turn's machine time is bounded by its 1,800-second limit, so neither can run
away, but neither has its own cap. The ledger total is compared with the approved
amount when the batch ends.

Acceptance, in order:

1. The baseline installs the pinned Linux archive, matches its SHA-256, reports
   Prime 0.10.0, and is checkpointed. A mismatch fails the baseline and admits
   no attempt.
2. Each attempt restores that checkpoint, and Prime completes a first turn and
   resumes the same session for the next one.
3. Installation and every wallet or signature turn verify the exact wallet
   release. Any unverified turn shows an unknown version and cannot pass.
4. Evidence is captured with canonical fingerprints and no supplied key or email.
5. At the end there are no active attempts and every machine is retired. The
   ledger total is reported against the approved amount.
