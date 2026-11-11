# Wallet Bench funding cap

A model, in [Quint](https://quint-lang.org), of how the Wallet Bench keeps its
funding sends within the run's total, checked by machine. It is a model of the
design, not of the Elixir code: it says the design is right, and the tests in
`platform/test/techtree/wallet_bench/funding_cap_concurrency_test.exs` and
`platform/test/techtree/wallet_bench/funding_settled_test.exs` tie it to the
code.

## What it proves

The bench's funder wallet pays each money attempt one USDC send and one ETH send
on Base, and the run has a total for each. Many attempts can be funded at once,
on more than one machine. Each signs its two sends first, then, inside the
database transaction that keeps them, takes one lock for the whole funder, adds
up every send kept so far and keeps its own only if they still fit
(`Funding.admit/1` in `platform/lib/techtree/wallet_bench/funding.ex`, called from
`platform/lib/techtree/wallet_bench/attempt/changes/sign_funding.ex`). A send
whose outcome was lost is settled later from its receipt on Base or, with none,
from reads pinned to one block (`Funding.settled/1`).

In plain words, for the design as built:

1. **The kept sends never pass the total** (`CapHolds`). However attempts
   interleave, retry or fail, the sends the bench has kept and still counts
   (every one except those that reverted or were replaced) stay within the total
   for each token.
2. **The money that really moved never passes the total** (`MoneyCapHolds`).
   This rests on a send that landed on Base never being marked replaced
   (`LandedNeverReplaced`). `settled/1` reads the receipt first; with none, it
   reads the funder's nonce at Base's finalized block, finds the block where
   the nonce passed the send's by halving, every read pinned to a block, and looks at the
   funder's transaction there at that nonce. Only another hash there makes the
   send replaced; this send's hash means it landed, and its receipt decides.
   The model takes those pinned reads as giving Base's own record, or, from a
   node behind the chain, an older one: it assumes this, it does not prove it.
   The search, the sender and hash checks and the bound on reads are checked by
   the ExUnit tests of `settled/1`, which fail when any of them is broken.

Both are proven for every run length, not just short ones, for three attempts
running at once, a total of two sends of each token and one retry each, with
any read of Base answered by a node behind the others.

The model also shows what breaks each one:

- **Repeatable read breaks 1.** Under repeatable read, a transaction's view of
  the database is fixed at its first statement, the attempt's own update, which
  comes before it waits for the lock. Three attempts that each update before
  any of them commits all see no sends kept, so all three keep theirs: three
  sends against a total of two. Under read committed, the default, the sum is
  read after the lock is taken and sees every send committed before it.
- **The receipt, then the nonce at the latest block, breaks 2.** A send
  landing between the two reads looks like no receipt and a used nonce, is
  marked replaced, and frees room for another attempt: three sends really moved
  against a total of two.
- **The nonce at the latest block, then the receipt, breaks 2 with a lagging
  node.** That order assumes the receipt read sees at least what the nonce read
  saw. The bench reads Base through one address (`base_rpc`, Base's public
  endpoint), which may answer from different nodes. If the nonce read reaches a
  node that has seen the send's block and the receipt read reaches one that has
  not, the send is marked replaced although it moved. This is why `settled/1`
  decides only from a receipt or from reads pinned to one block.

## How it is checked

| Check | Tool | What it covers |
| --- | --- | --- |
| Proof for every run length | `quint verify` (Apalache 0.62.4) with `CodeInductive` | An inductive invariant that holds at the start, is kept by every step, and implies `CapHolds`, `MoneyCapHolds` and `LandedNeverReplaced` |
| Counterexamples | `quint test`, one trace per model | The exact runs above, each replayed step by step and checked to break (or, for the design as built, to keep) the property |
| The proof can fail | the same `quint verify` on `repeatable_read`, `receipt_first` and `nonce_first` | `CodeInductive` is not kept by any of the broken designs, so the proof is not true of everything |
| Random runs | `quint run`, 100,000 runs of 40 steps | The design as built |
| The code | ExUnit, real Postgres | Five attempts keeping their sends at once, on five connections, with room for two |
| `settled/1` | ExUnit and a property test, with a fake Base node | Each outcome, a lagging node's missing receipt, a node without the pinned block, and the search finding the block in at most about log2 of the finalized block number in reads, all pinned |

The file `funding.qnt` holds the parametric model `funding` and four instances:

| Model | Isolation | `settled/1` reads | Base reads |
| --- | --- | --- | --- |
| `code` (the design as built) | read committed | receipt, then pinned to one block | any read may lag |
| `repeatable_read` | repeatable read | receipt, then pinned to one block | any read may lag |
| `receipt_first` | read committed | receipt, then nonce at the latest block | consistent |
| `nonce_first` | read committed | nonce at the latest block, then receipt | the receipt read may lag |

### The model

- **Attempts** move through start, prepared (both sends signed, before the
  transaction), updated (its own row updated: the transaction's first
  statement), locked (holding the funder lock), read (summed the kept sends and
  found room), inserted (its sends written, not yet committed) and committed.
  Any of those steps can fail and roll everything back (a database error, a
  Base error, the lock wait timing out); the retry starts again from signing.
  Before signing, an attempt is refused for good while any send is unknown or
  when the total has no room.
- **Payments**, one per attempt and token, with their committed status: signed,
  confirmed, reverted, unknown or replaced, or no row at all.
- **The lock holder**: one attempt or none.
- **Isolation level**: a model parameter. Under repeatable read each attempt's
  view is fixed when it updates its row.
- **Base**: a committed send may later be included, included and reverted, or
  passed over when its nonce is used by another transaction. A ghost
  "really moved on Base" is true for a send included without reverting.
- **Outcomes**: a receipt makes a signed send confirmed or reverted; a missing
  one makes it unknown; settling reads in two steps with Base free to act in
  between. In `code`, the first is the receipt and the second the pinned reads,
  which see Base's record of the send at its nonce, or, from a node behind the
  chain, an older one where the nonce is unused or the receipt missing.

## Rerun

From the repository root:

```sh
make check-formal   # typecheck, the four traces, random runs; a few seconds, no Java
make formal-proof   # also the proof for every run length; needs Java 17 or later
```

`make check` runs `check-formal`. Both use `npx` to fetch the pinned Quint
(`@informalsystems/quint@0.33.1`, Apache-2.0), which fetches its own Apalache
and Rust evaluator into `~/.quint` the first time. On Sean's Mac, Java is
Temurin 21 from mise:
`mise exec java@temurin-21.0.13+9.0.LTS -- make formal-proof`.

## Results (11 November 2026)

- `code`: `CodeInductive` is inductive and implies `Safe`; no violation
  (Apalache, about 22 seconds), with lagging nodes allowed. `CapHolds`,
  `MoneyCapHolds` and `LandedNeverReplaced` hold for every run length. Random
  runs: no violation. Its traces replay a send landing between the two reads,
  the lagging-node run that breaks `nonce_first` (the send stays unknown, then
  is confirmed), and a replaced send whose room funds a third attempt.
- `repeatable_read`: `CapHolds` broken, in an 18-step run: all three attempts
  sign, all three update their rows, then each in turn locks, reads an empty
  view, inserts and commits. `CodeInductive` fails here too. Apalache's own
  search for this run, without being given it, was stopped at step 14 of 18
  after about 20 minutes, each step slower than the last; the replayed trace
  is what shows it.
- `receipt_first`: `MoneyCapHolds` broken while `CapHolds` still holds: the
  bench's books stay within the total while Base moved three sends.
  `CodeInductive` fails here too.
- `nonce_first`: the same as `receipt_first`, from a lagging node.
- The code: five attempts at once keep exactly two pairs and refuse three
  (read committed). The same test with `SET TRANSACTION ISOLATION LEVEL
  REPEATABLE READ` as each transaction's first statement keeps all five, which
  is the model's counterexample on real Postgres.

## Isolation in Techtree

`Techtree.Repo` (`platform/lib/techtree/repo.ex`) and the connection settings
in `platform/lib/techtree/database_config.ex` and `platform/config/` set no
isolation level, and no transaction asks for one, so every transaction runs at
the database's default. The local test database answers `read committed`, the
Postgres default. The production database's own default was not read for this
model; if it were ever set to repeatable read, the cap would break as above.

## Limits

- This is a model of the design. It does not read the Elixir code; the test and
  a reader keep the two in step.
- The bounds are three attempts, a total of two sends of each token, and one
  retry each. The proof covers every run length within those bounds, not every
  number of attempts.
- Each send moves one unit; real amounts differ but the sum is the same shape.
- Signing, gas, fees, balances and nonce choice are left out: they decide
  whether an attempt is refused before the transaction, not how many sends are
  kept.
- Base never reorganises a finalized block. `settled/1` starts its pinned reads
  at Base's finalized block, so a replaced send rests only on blocks final on
  Ethereum; a send waits unknown until then. A node
  behind the chain refuses a pinned block it does not have, or shows an older
  state; no node answers with a block or a nonce that is not Base's. The tests
  check `settled/1` against a fake node, not Base itself.
- The funder lock is modelled as exclusive. In Postgres it is an advisory lock
  on one number, in a database other sites share; another site taking the same
  number would make attempts wait, never let two through.
