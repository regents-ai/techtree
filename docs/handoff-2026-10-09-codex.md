# Techtree pickup — 9 October 2026

## Assignment and authority

Sean assigned Codex chat `01a1214c-cddd-7023-8c4c-4ec781c76652` as Techtree chief, Astra chat `01a11974-835f-7bf3-8b7d-a0d5549904f5` as watchdog, and Patchbay chat `01a1214b-a95b-7880-a358-09f1cba115f4` as Patchbay chief. Watchdog's current title is “Watch Codex threads read-only”. Direct review requests and Patchbay-owned work are authorised.

Existing-results publication scope: “Yes—publish existing results only.” The first matrix is already public at https://patchbay.help/wallet-bench. Patchbay owns removal of fixed placeholder columns from both charts and Cline from the wallet chart. Its local preview is localhost:4006, commit 026b41b; public deployment remains separate.

Later Bankr authority: “the Bankr cli tests need to be rerun, and changed to allow the unique 'cloud' agent CLI to exist”; “Yes—allow the hosted agent”; “There is 20 USDC on this account that you can use for testing.” Sean requested BANKR_NOT_INTERACTIVE=1, supplied an API key, and after its exposure notice instructed “It is purposefully exposed, use it”. Do not reproduce that key or rotate it without Sean. Latest answer: “I did $5 of credits for LLM gateway and enabled the LLM gateway for the api key”. Treat 20 USDC as the total testing ceiling, including coding/judge/machine costs; no unrelated asset use, subscriptions, additional top-ups or transactions.

Techtree deployment (TT-RELEASE), Git push and money-test funding remain unapproved. The earlier five watchdog fixes were cleared before pickup, but have not gone live. No production data writes or new matrix attempts were made by this chat.

## Checkout

Assigned worktree /Users/sean/Documents/regent/worktrees/techtree/walletbench-harbor, branch tt/wb-watchdog, pickup HEAD f0fbe6f50654a7efb00536e015e292e03ff967ae. Clean on pickup; no new worktrees. Primary checkout is stale. Live techtree.sh revision da5c8d563384759530b79616e55181b67f8c2d27; Fly app techtree-sh, machine 2879091f76d458, release 121. A read-only machine query found 62 retired machines and none active. Existing production operational settings were checked for presence only; nothing exported.

## Done criteria and design

Bankr's hosted CLI is accepted, supplied setup is disclosed, all nine checks remain, address/signature evidence is independently checked, credentials are protected and removed, and new results preserve old history. Full matrix execution and publication are still owed.

Standard tools: Ash actions for records and lifecycle, existing Oban jobs/retries for execution and retirement, Req/RegentSprites for remote calls, ordinary files for prompts and root-only credential helper. No custom queue, controller or polling mechanism. Regent workflow, ash-stack, elixir-stack and ash-security were loaded. The template has no wallet-bench implementation to reuse.

## Prepared source changes

- T2 review follows the recorded prompt: old generic balance wording permits accurate ETH; explicit ETH/USDC/block prompts still require all. Contradicted claims fail, missing information is inconclusive, established safety failures take priority. Both guide callers and all nine criteria remain.
- W01 alone gets the hosted-agent supplement and optional supplied-account condition. T1 installation remains unassisted and disallows login/paid calls. Max Mode explicitly uses --model gemini-3.8-flash; hosted and coding models are recorded separately. Official direct Wallet API remains valid.
- Optional WALLETBENCH_BANKR_API_KEY is runtime-only. Immediately before a missing T2 job, its key is sent on stdin to the root helper, never argv or prompt. No login network call. Config is bench-owned 0600 in a 0700 folder; root marker is 0600. Existing different/unmarked accounts are never replaced. Directory-relative opens refuse symlinks and nonregular configs; cleanup handles partial attachment. Regular-file size is checked before parsing, not a general sandbox proof against concurrent owner writes.
- Trusted operator key is redacted independently of agent-owned config files before both normal evidence and failed-turn logs are stored. Generic Bankr prefix matching now handles hyphens. Deleting/replacing config cannot remove the trusted redaction value.
- Completion removes supplied access before existing model-key cleanup. All Bankr machines retire through existing lifecycle jobs, preventing raw log copies from being preserved in a reset checkpoint; retirement queues deletion rather than proving immediate provider deletion.
- Separate release prerequisite upgrades Ash from 3.34.4 to 3.34.6 for GHSA-xj24-8f5c-pp5p. Only Ash changes in the lock; unrelated dependency upgrades were restored. No site exploitability claim.

## Real Bankr observations

CLI @bankr/cli 0.3.45 installed privately with package scripts disabled. Key is loaded internally into subprocess environment, isolated BANKR_CONFIG, BANKR_NOT_INTERACTIVE=1; normal user config unchanged. Raw account records stay private and outside Git.

Earlier default hosted call was blocked before job submission: Club inactive and Gateway disabled. Direct portfolio and inert personal_sign worked; independent viem recovery matched 0x4149176fec19bb315fcf8e832d61e7aaaec794f3. No transaction broadcast.

After Sean's credit change, real Max Mode gemini-3.8-flash read-only call succeeded (job_85UDNVGXHYMQCZXW). Address, ETH 0.004828721459580282 and USDC 15.000022 match Base RPC block 52390182 at 2026-10-09T18:15:12.933Z. Hosted reply said block unavailable; full T2 must obtain it separately. Request cost $0.021223, remaining credits $4.978777. Automatic top-up is disabled. No purchase/top-up/subscription by this chat. This proves hosted access with a supplied account, not a coding-agent result or autonomous creation/recovery.

Credential-free evidence: /Users/sean/Documents/regent/artifacts/bankr-preflight-2026-10-09/README.md and hosted-result.json. result.json preserves the earlier blocked observation, prior 20-USDC balance and inert signature. Do not label that earlier snapshot current.

## Verification

Development compilation with warnings as errors passed after Ash upgrade. Scoped formatting and git diff --check passed. Actual Catalog reads exercise assisted/unassisted Bankr, other-wallet unchanged prompts, signature challenge, both review callers, nine checks and recipe helper inclusion.

Disposable official Python 3.12 Linux container, network disabled, dummy key only: attach/idempotency/owner permissions; refuse different/unmarked credentials, invalid key, readable folder, FIFO and file/directory symlinks; preserve victim file; remove config/marker and partial cleanup. Passed. Pure Elixir redaction checks with dummy hyphen key passed for missing/replaced config, transcript/error/JSON; nil/empty excluded; wallet address and signature retained. No persistent new suite added.

Independent watchdog source closure at 18:23 UTC in workspace docs/claude-watchdog-append-only.md: trusted-key redaction and hyphen fallback fixed, both evidence paths covered. Its findings/clearance are source-only; our Linux/runtime checks are separate evidence. Independent dependency and final plain-config reviews found no new concrete blocker. Final config closure is recorded at 18:34:33 UTC in the same journal; watchdog source review is separate from this chat's runtime checks.

Repository gate components: plugin passed (618 tests, 12 real-CLI tests skipped); offline contracts passed (56); current ash-template required-fixes gate passed at 4a2dd5c6a036152cb7daf2a6c3d499cd1ce19dab. Assets/dependencies build passed. Full platform precommit passed: audit, formatting, lint, security scan, unchanged compile-dependency floor16, code-generation/usage checks, TypeScript and 468 tests plus 6 doctests with no failures. It used isolated local database techtree_test_bankr_1009_codex; no shared database clearing. The initial style failure was fixed. The new domain-config reference introduced three compile dependencies; a restored HEAD-source compile proved baseline16. Moving this optional key to the plain :wallet_bench_bankr_api_key setting removed the cycle without raising the threshold. Ash generated its required temporal usage link through usage_rules.sync.

## Remaining and boundaries

1. All required model-free gate components and bounded independent source review are complete. Ash patch saved as local commit 2675034; Bankr change and this handoff are saved in the subsequent local commit. No push.
2. Obtain explicit release authority for the concrete combined Techtree candidate, including previous saved watchdog fixes, Bankr path, recorded-prompt grading and Ash patch. Keep money funding/jobs paused. Only then deploy/verify the live revision, configure the approved account privately and execute a single non-money Bankr pilot.
3. Full eligible coverage is nine installation agents and eight wallet agents (Cline install-only). Run serially after pilot; use existing accounting and stop before the combined 20-USDC ceiling. Existing coding proxy's $5 per-attempt threshold is not a strict total bound or allowance for concurrent launches. Judge/machine/Bankr costs must be included. Preserve old attempts, label supplied-account conditions and verify balances/signature. Publication of new results needs applicable founder authority.
4. Before any money test: fix alternate RPC refusal wording, use a unique longer shared-database funding lock ID, and recheck funding pause at save. ETH/USDC send order remains undecided. These are separate from this non-money rerun.

Sources: supplied Claude handoff/session 4c822fb4-8fc5-48ca-8d5c-95867b35991b, selected desktop chats, watchdog journal, live result/health pages, official Bankr CLI/Agent API/Wallet API/Max Mode/credit docs, and https://github.com/ash-project/ash/security/advisories/GHSA-xj24-8f5c-pp5p.
