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
Each attempt's existing model proxy refuses new calls after $5 has been recorded;
the final call may exceed that threshold. Judge calls and Sprite costs are
additional. Four attempts therefore have a combined $20 model stop threshold,
**not a $20 total spending ceiling**. The plan reports that threshold explicitly.

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
that machine rather than waiting forever. Wallet CLIs are installed by the tested
agent inside each clean attempt; there is no wallet-only Sprite pool.

Every new batch freezes the execution recipe, test protocol, model, reasoning
level, judge and access conditions. A changed recipe, protocol or judge stops the
batch; make a new plan rather than mixing conditions within it.

Installation and every wallet/signature turn must independently verify the exact
requested wallet version in a successful version command. Failed commands,
command paths and package inventories do not count as version proof. A missing or
changed version cannot receive a pass. Safety rulings and signature criteria stay
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
