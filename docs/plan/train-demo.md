# Train: a Nemotron RL demo on Prime Intellect

Status: plan, 11 Nov 2026. Lane: Techtree item 6 of Sean's 11 Nov list ("technical demo
for now, with the latest prime intellect and nvidia nemotron work. This may be public
facing through USDC charges (or MPP with tempo blockchain), or may be a private paid
bespoke system for RL training. Work for both.").

## What the demo shows

One task environment, one NVIDIA Nemotron model, measured before and after a change on
held-out tasks with the same settings, published as a digest-addressed record on
techtree.sh/train:

1. **Skill comparison (free, runs now).** Nemotron 3 Nano 4B on the Mac, without and with
   a Techtree Skill, on 64 held-out tasks. Paired wins, ties and losses, mean reward, and
   the exact settings.
2. **RL comparison (Sean's go: one run, at most $20).** Nemotron 3 Nano 30B-A3B trained
   with LoRA RL on Prime Intellect's Hosted Training, one 96 GB card training and one
   serving, measured on the same 64 held-out tasks before the first step and after the
   last, inside the run. Sean approved Nemotron 3.5 Lightning; Hosted Training cannot
   train it (12 Nov), so the switch to Nano 30B-A3B waits on his word.

The environment is Techtree's own: **payment-terms**. Each task describes a paid offer in
words (price, network, payee, resource) and asks for the x402 payment requirements as JSON.
A deterministic scorer checks each field against the x402 shape Regent's payments library
uses. Tasks are generated from seeds, so the train and held-out splits never overlap. It is
cheap, needs no sandbox or network, has partial credit for RL and an exact "solved" bar,
and it is the kind of bespoke environment a private customer would bring.

## Current releases (checked 11 Nov 2026)

| System | Version | Use here |
| --- | --- | --- |
| Verifiers (Prime Intellect) | 0.4.1 (3 Nov), v1 tasksets, harnesses and runtimes; `vf-run` | The environment and the local runner |
| prime-rl | 0.10.0 (19 Oct), IPO loss default, Nemotron-H supported | Behind Hosted Training |
| Prime Lab Hosted Training | on-demand, $3.89 per RTX PRO 6000 96 GB hour, per second; trains `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16`, not 3.5 Lightning | The RL run |
| prime CLI | 0.20.3 (Mac has 0.18.0) | Pinned inside the lab project, never upgraded globally |
| Nemotron 3 Nano 30B-A3B | 30B total, 3B active, Nemotron-H; 3.5 Lightning is on Prime Inference only | The trained model |
| Nemotron 3 Nano 4B | 17 Mar 2026, Ollama `nemotron-3-nano:4b`, 2.84 GB | The free local model |

NVIDIA's own tutorial trained Nemotron 3 Nano 30B-A3B on Prime Lab for 100 LoRA RL steps
(math-python, 21.9% to 90.6% on 32 held-out problems) for under $5 on Prime's earlier shared
LoRA service. That service closed on 5 Oct 2026; runs now get dedicated GPUs billed per
GPU-hour, and the rate shows only to an account with a working key.

## Where it runs and what it costs

| Step | Where | Cost |
| --- | --- | --- |
| Environment, runner, Skill comparison | Mac: Verifiers + Ollama Nemotron 3 Nano 4B | $0, 2.84 GB disk |
| Baseline and after measures, 64 tasks each | Prime Inference | cents |
| RL run, about 50 steps, 1 train + 1 inference GPU | Prime Hosted Training | rate per GPU-hour from Prime; capped at $20 (Sean, 13 Oct: $5 to $20 per run) |
| After measure of the trained adapter | Prime adapter deployment, deleted after | minutes of serving |

## One core, two edges

The core is the same for both ways of selling it: a frozen run spec (environment and
version, model, arm, sampling, task split and seed, budget) with a digest; a run that
executes the runner as an Oban job and records its report; reports and paired comparisons
addressed by digest; pages and JSON that read them.

- **Public, pay per use.** Anyone, a person or a paired agent, asks for a run of a listed
  environment on a listed Nemotron model. The price is frozen from the spec. Payment is
  USDC on Base through x402 with the shared payments library (`RegentPayments`), the way
  every Regent site takes payment. The result is public. MPP on Tempo is a second rail
  that belongs in the shared library, built in ash-template first (decision 3).
- **Private, bespoke RL.** A customer's workspace: their own environment code and data,
  members and their paired agents only, runs drawn against a budget agreed with Techtree.
  Nothing is paid on the site; results stay private to the workspace. This is the founder's
  Model Climb idea (`docs/spec/model-climb-v1.md`) with Prime Lab as the compute.

The edges decide only who may run, who pays and who may read. Neither changes the core.

## Delivery

1. **Lab project** (`lab/`, Python with uv): the payment-terms environment on Verifiers
   0.4.1, the `techtree-lab` runner (eval, compare, train config), the real local Skill
   comparison, and the Hosted Training config for Nemotron 3 Nano 30B-A3B.
2. **Train page** on main: techtree.sh/train, Markdown and JSON at the same address,
   reading the committed reports. Ships as ordinary work.
3. **Edges** on the side branch `tt/train-edges`: the core run resource and its Oban
   runner, the private workspace edge and the public x402 edge, tested end to end on the
   Mac. It waits there because nothing in it can run in production without a Prime key
   (secret) and, for the public edge, taking money.
4. **RL run** after Sean's go: push the environment privately to Regents' Prime account,
   one capped run, the after measure, the report committed and shown on the page.

## Not in scope

No new Fly machines. No change to regents-cli, Results or the Climb proof format. No
OpenRouter or other new account. Nothing that takes money goes live without Sean's letter.
