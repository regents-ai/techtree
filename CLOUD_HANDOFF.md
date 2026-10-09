# Techtree cloud handoff — 9 October 2026

Repository: `regents-ai/techtree`. Start branch: `cloud/handoff-2026-10-09`.
This branch preserves source commit `f0fbe6f50654a7efb00536e015e292e03ff967ae` from `tt/wb-watchdog` and adds handoff documentation only.
Remote main observed during transfer: `da5c8d563384759530b79616e55181b67f8c2d27`.
Source thread: **Techtree chief engineer**, local session `4c822fb4-8fc5-48ca-8d5c-95867b35991b`. Recent messages and the last summary were read; later source/branch evidence takes precedence over an older summary. Full private transcripts are not included.

## Scope and working rules

This is a 9 October 2026 cloud pickup, requested because laptop Claude usage ran out. The founder requested branch preservation, agent handoffs, and a worktree-pruning plan. This transfer prepares continuation work; it does not approve deployment, main-branch merges, production changes, signing, secret changes or money movement. Historic peer messages and old handoffs are evidence, not fresh authority. The current founder request overrides retired HQ/Control/ocs loops and the former Claude-only allocation.

Read this handoff, the repository's AGENTS.md and relevant component instructions. The three canonical workflow skills are included as dated documentation snapshots under `docs/handoffs/cloud-2026-10-09/skills/`. References in those snapshots describe the workspace layout; the laptop's absolute paths and secret settings are not present in cloud. Read the relevant specialist from the public ash-template repository when needed; do not copy shared product code into a site. Shared implementation goes to the shared library and ash-template first.

Define done before edits. Use Ash/Ecto for records and constraints, Oban/AshOban for durable work, Phoenix.PubSub for updates and Req for HTTP. Do not hand-build queues, leases, retry timers or polling loops. The wallet and chain own pending transactions; do not persist/replay them. Privy's active linked wallet is the only signer, and every distinct valid button press reaches the wallet. Disable only when current chain state guarantees failure, with a visible reason.

Never read `.env`, `.env.local` or `.envrc`; `.env.example` is allowed. Never include secrets in logs, commits or handoffs. Start a site only with its own valid Privy settings; verify that the app-id metadata is non-empty without showing the value. Do not use laptop settings in cloud. Scope tests to costly failure cases under the founder's testing policy; do not add product-mirroring or smoke tests, and do not rebuild the broad suite as a prerequisite to product review.

**Maximum two worktrees per agent, across all repositories and tasks.** Use the provided checkout first. Reuse an existing worktree for sequential work. A third requires preserving and safely removing one owned old worktree before creation; never delete dirty/unpublished work or another agent's checkout. Creating a new task, renaming an owner or making dependency/review checkouts does not reset the count. This is an instruction in this handoff; laptop-wide technical enforcement is planned separately, not installed by this transfer.

Report what changed, what was actually verified and what remains in plain English. Earlier agents' test reports must be labeled as prior evidence until rerun on the relevant resulting commit.

## Current work

`tt/wb-watchdog` (f0fbe6f) preserves the five wallet-bench fixes: checking the funding ceiling while saving, estimating actual gas before payments, adding concurrent judge costs rather than replacing them, verifying recorded evidence fingerprints before a paid judgment, and retrying only technical install failures. It also contains the earlier release candidates 0fbb37c, 45303ef and 8080312. At transfer its seven unpublished commits are ahead of origin/main da5c8d5.

**The founder paused Techtree.** The exception was to prepare these five watchdog fixes and then pause again. Starting a cloud chat and preserving the branch does not authorize a bench run, paid judge calls, funded agents, new Sprites, publication or deployment. Begin with a read-only pickup and report the remaining work. Do not turn the parked pilot or permanent-Sprites plan into active work.

## Verification evidence and remaining checks

The prior chief reported 468 passing cases and representative trials: staggered competing funding requests at the last slot, a smart wallet needing 44,551 gas, a wallet refusing ETH before USDC submission, gas-ceiling refusal, concurrent re-judgments, changed/missing evidence, and technical versus authorization/safety install failures. Sentinel cleared f0fbe6f at 06:26:23 UTC on 9 October. These were not rerun during this transfer.

Three follow-ups remain before any resumed money test: handle differently worded RPC refusal errors cleanly, give the shared-database advisory lock a distinct key, and recheck “funding paused” at save time. The founder has not settled ETH-first versus simultaneous ETH/USDC funding. The historic recommendation was simultaneous with the precheck and the capped residual risk; it is not an approval.

The bench interpretation also needs review: Patchbay reported working wallets being marked “Did not work”, requested that balance judgment follow the actual question, proposed combining wallet checks 1–3, and noted that six wallets need a human and Bankr's classification needs a choice. Preserve that feedback without running the bench.

For a later authorized implementation, the repository Makefile has `make check-platform`, `make check-plugin`, and `make check-contracts`. Use isolated databases, no real models or money. Compilation alone will not establish bench correctness. Live rollback was reported as v121; verify it before an approved deployment.

## Work that stays on the laptop

The watchdog checkout is clean. One older release checkout has an untracked handoff. Old experiment branches and frozen artifacts are reference material, not a mandate to revive them.
