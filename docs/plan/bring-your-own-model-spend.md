# People bring their own model spend

Written 2026-10-13 by the Techtree chief (session `ba3289`, Claude Opus 5.5) on
Sean's TT-BYO-PLAN "1. a". Plan only: nothing here is built, pushed or spent.

## 1. The idea

Techtree supplies the structure and the uplift: tasks, recipes, checks,
scoring, signed proofs, public pages, and better recipes and skills over time.
The person (or their agent) pays for the models and GPUs that do the work.

Two ways to pay, and they must never be blurred:

- **Self-run.** The work runs on the person's own machine with the person's
  own model key or GPU account. Techtree never sees that key. The result is
  the participant's own claim.
- **Hosted.** Techtree runs the work on its own machines with its own keys,
  and the person pays in Regent Credits. The result is Techtree's own record.

A third way, the person handing us their model key, is ruled out: Techtree
would hold a secret it does not need, and spend from it on the person's behalf.

## 2. Where each product stands today

| Product | Who pays now | Fits self-run? | Gap |
| --- | --- | --- | --- |
| Model Climb | The operator's SF Compute account (Sean's today, `regents-123`, $0.063 per GPU-minute, $50 monthly limit, top-up off) | Yes, by design: the operator's machine, the operator's `gmnt_` token, a local grant and a signed run record (`docs/spec/model-climb-v1.md`) | The website side (M3): publish the grant-signing public key, accept an uploaded signed record, show it as a participant claim |
| Wallet Bench | Techtree: our Sprite machines, our `WALLETBENCH_ANTHROPIC_API_KEY` through the LiteLLM relay with caps, our judge. Batches are operator-only | Not yet: the harness only runs on our machines | A local runner, an upload route and labels (route a), or Credits charging on hosted batches (route b) |
| Skill climbs | Operator only, not yet public | Same shape as Model Climb | Follows Model Climb's M3 |

Recent real costs, for scale: the Claude Code batch was $3.50 for 4 attempts;
the Prime batch on 12 Oct was $9.94 for 4 attempts ($8.48 model, $1.46 judge).

## 3. Trust labels

Model Climb already defines three attestation levels. Wallet Bench uses the
same three, so one word means one thing across Techtree:

| Level | Meaning | Bench example | Model Climb example |
| --- | --- | --- | --- |
| `participant` | The person ran it and signed the record; we checked the signature and the shape, not the work | Self-run batch uploaded with the person's agent key | Uploaded run record from the person's SF Compute job |
| `identified_executor` | Techtree ran it on its own machines | Hosted batch paid in Credits; today's operator batches | A run Techtree executed |
| `independently_reproduced` | Techtree reran a participant's result and it held | Hosted rerun of a self-run batch | Rerun from the published recipe |

Public pages show the level beside every result. Results of different levels
are never folded into one combined score.

## 4. Model Climb: website side (M3)

Already true: the paid step (`model_climb_profile_test`) runs on the
operator's machine against the operator's SF Compute account, under a local,
operator-attested grant (`model_climb_grant_issue`), and writes a signed record.

To build:

1. An upload route: the person's agent signs in (SIWA), posts the signed proof
   directory, Techtree checks the manifest against the participant identity key
   (the same check as `regents techtree proof verify`), the schema pin
   (regents-cli `08bd5c3`, sha256 `7b38f89a…a070` per spec 3.2) and size limits,
   and stores it as `participant`. The site's grant-signing key (spec section 6)
   is only needed for connected-mode grants, which self-run does not use.
2. The record shows on the person's own tab, visible only to them, with its
   level, its recipe, its numbers and the provider it ran on (open decision
   TT-BYO-MC-PRIVATE asks whether Model Climb follows the Bench rule).
3. Later: an "ask for a reproduction" button that runs as a hosted job (section 6).

No real proof exists yet: the first paid run waits Sean's go, the grant and the
`gmnt_` token. Until then the upload route can only be exercised with a proof
made locally for testing.

Each person's spend limit lives in their own SF Compute account; Techtree
never holds or reads it. The grant review keeps asking the operator to attest
their limit and top-up setting, as it does now.

## 5. Wallet Bench, route a: self-run

1. A regents-cli command runs one Bench attempt locally: the same task images in
   the person's Docker, the same local Anvil chain, the person's own model key
   from their environment, the same checks.
2. The judge runs on the person's key too (open decision TT-BYO-JUDGE).
3. Before upload, the CLI scrubs the transcript on the person's machine with the
   same safety rules as hosted runs. The Prime batch's W07 shows why: the public
   Anvil test key appearing in a transcript is a safety failure, and a personal
   key appearing there would be worse.
4. Upload: the agent signs the result with its SIWA key; Techtree checks the
   signature, the harness version, the task digests and size limits, and stores
   it as `participant`.
5. Self-run results go on the person's own tab and are private to them (Sean,
   TT-BYO-BOARD, 13 Oct 2026: "user tab, private"). They never appear on the
   public results pages.

What Techtree pays: storage and pages only.

## 6. Wallet Bench, route b: hosted, paid in Credits

Sean, 13 Oct 2026: "wallet bench we prove the benchmark first, then sprites let
people run a row or column of the benchmark". The grid is agents by wallets: a
row is one agent across every wallet, a column is one wallet across every
agent. Techtree first runs and publishes the full grid itself; only then are
row and column runs opened to people.

1. The person (or their paired agent, within the allowance the person set)
   asks for a row or a column. Techtree quotes a cap from the attempts in it.
2. Techtree places a Credits hold for the cap through the template's Credits
   library (`RegentCredits.hold`, the template's agent spend path, Sean 111 a),
   which already refuses a hold the person cannot cover and handles two agents
   spending one balance at once.
3. The batch runs as today: Sprite machines, our key through the relay with its
   caps, our judge.
4. On finish, Techtree settles the hold at the measured cost (model, judge,
   machine time, plus any margin Sean sets) and releases the rest.
5. Results are `identified_executor`.

Preconditions, each its own go from Sean when the time comes: Credits charging
switched on for Techtree (deferred and off today), a price rule, and the
relay's per-batch cap set from the hold.

## 7. Order of work

| Step | What | Money moves? |
| --- | --- | --- |
| P0 | This plan | No |
| P1 | Model Climb M3 (section 4) | No |
| P2 | Prove the Bench: Techtree runs and publishes the full grid | Yes, Techtree's own spend; each batch its own go |
| P3 | Row and column runs on our Sprites for people (section 6) | Who pays is open (TT-BYO-SPRITE-PAY) |
| P4 | Bench self-run (section 5), private to the person | No; the person's own key |

Each step ships as its own release item through the orchestrator's sense check,
then to Sean.

## 8. Open decisions

Answered 13 Oct 2026: TT-BYO-ORDER a (Model Climb M3 first; the Bench is proved
before row and column runs open), TT-BYO-BOARD "user tab, private".

- **TT-BYO-JUDGE.** In self-run Bench, who pays the judge: the person's key, or
  Techtree grading and charging Credits. Sean undecided; needed by P4.
- **TT-BYO-SPRITE-PAY.** Who pays the model on a row or column run on our
  Sprites: Credits (our key, actual cost charged), or the person's own key
  placed in that Sprite for that run.
- **TT-BYO-MC-PRIVATE.** Whether uploaded Model Climb records are private to the
  person's tab, like self-run Bench results.
- **Later, at P3:** the price rule and switching Credits charging on for Techtree.
