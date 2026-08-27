# Product-claim-to-evidence matrix — Climb v0.1

Ticket: techtree-python-y8s (decision 0023 item 3.2).
Execution contract: `docs/release/contracts/wp11-claims.md`.
Binding copy boundaries: decision 0013 §1, decision 0035.  Scope statement: decision 0023 §4.
Lineage authority: `release/certified-scientific-fingerprint.json`, regenerated 2026-08-27 from the artifacts.
Attachment to the Gate-2 packet; runs before WP11h.

Refreshed 2026-08-27 against the lineage this release actually ships. The previous edition anchored on Campaign `ad393bc0…`, ReleaseCore `c037f457…`, engine `874cbae0…` and the five run identifiers of the 2026-08-20 quiet window. That lineage has been superseded by the engine move to released Verifiers v0.3.1, re-certified under the Campaign it produced, and exercised end to end by the WP11f onboarding acceptance. Every citation below was re-read from an artifact during this refresh: every test name was located by search before it was written down, and every digest was recomputed from the file it names.

## The lineage this matrix anchors on

| Coordinate | Value | Read from |
|---|---|---|
| Campaign | `sha256:ebf029abb266ca74c2def50eb23030511bab0e929c6bf4a68691f9b5afd554b1` | `src/techtree/resources/catalog/campaigns/hello-world-climb.json`, hashed in this refresh |
| Climb | `sha256:a3a5e9c5f9b40d4f08fad54852377e201fd0d6dd4acfa4c565a0edfac324a236` | `src/techtree/resources/catalog/climbs/hello-world-climb.json`, hashed in this refresh |
| Catalog | `sha256:10a7fcc5de1951c14509947c0512a4eeb247a703cdf01cc3f268580979a7d12c` | `release/release-core.json` `catalog_digest` |
| ReleaseCore | `sha256:bef3b9d4c987209c0fb580ed5eb349c096dca328efd7b0867f5a04d7bb763db4` | `release/release-core.json`, hashed in this refresh; byte-identical in three repositories |
| Engine | `sha256:29b1bbb8327d8f1a9ade03ff4504695ad3783ae34aaaa559e5c6bf9fc95e879b` | `release/release-core.json` `engine_digest` — Verifiers 0.3.1 at commit `b2e4e8157783b2c0dffc7821044c87f29f1c3ccf` |
| Taskset lock | `sha256:8bed6f7c7f8b1a703020db9fa0fe08b29e68df6abd0e8f06ffa229722c7d87e0` | `proof/taskset-lock.json` of each of the six runs below, hashed in this refresh |
| Skill improver | `sha256:d5a381bed8ae5ddd5bbd6035775154dc47d2cb11b1da14f11d30ed47ff371678` | `../techtree-plugin/skills/skill-improver/SKILL.md`, hashed in this refresh |

**The engine move, and the one thing that had to survive it.** The embedded Verifiers engine moved from the pre-release development revision `7e1c47d2…` (0.3.1.dev21) to the released one `b2e4e815…` (0.3.1), at commit `8ee03a1ad64fc05eb800014a8b5502a559c184ff`. That changed the engine bundle digest, the taskset package source digest, and — because the package digest and the validation receipt are named inside the Campaign — the Campaign, Climb and catalog digests with them. The fingerprint's `engine_move` block records the method: the two Campaign documents were flattened to JSON pointers and compared field by field, and exactly **two** fields differ, `/taskset/ref/package/digest` and `/taskset/validation_receipt_digest`, both of them names of the moved engine. All **36 committed task hashes are byte-identical and in the same order**, the membership digest is the same value `sha256:56f697fb182cc316…`, and recomputing that digest from the hashes reproduces it. The budget contract, the execution contract, the subject model and sampling, the runtime image digests, the mutation contract and the scoring contract are unchanged.

**Superseded, and named here only so nothing cites them by accident.**

- The engine-move predecessor: Campaign `ad393bc0…`, Climb `ac76d787…`, catalog `ae300ef6…`, ReleaseCore `c037f457…`, engine `874cbae0…`, taskset lock `2edd60bc…`, taskset package `14d9646d…`, validation receipt `080895d5…`, validation evidence `9c4959d3…`, and its uplift derivation `5105b91c…`. Its runs — `run_06b2377d…`, `run_8fdfdcf6…`, `run_ad759a00…`, `run_ede1fd20…` and the kill injection `run_ba3998e2…` — still exist under `certification-evidence/recert-0029-quiet-2026-08-20/` and are cited below **only** where this lineage has no counterpart, and always labelled as superseded-lineage evidence.
- Two lineages before that: Campaigns `b9e3f00c…` / `5aef3fb7…`, ReleaseCores `90cd8ad6…` / `80807821…`, and the five first-certification runs `run_d9409450…`, `run_a6c608b9…`, `run_6ff833ca…`, `run_9f2a5025…`, `run_e29f1781…`. Nothing below cites any of them.
- The Gate-1 rehearsal Skill v2 (`b143866e…`) and the 2026-08-20 frozen v2 (`2081ae90…` / SKILL.md `0beea6ec…`). The guided revision this release ships evidence for produced a different Skill again: `5e2e2f58…` / SKILL.md `4d94de88…`.

**What the Gate-1 approval does and does not cover — and where it no longer holds.** The founder's Gate-1 approval (`release/founder-approvals/gate1-founder-skills.md`, against packet digest `sha256:b3ea3ba1…`, recomputed here from `release/founder-skill-approval-draft.md`) approved two Skill files. One of them is still exactly what this wheel ships and one is not.

- **Starter Skill — unchanged.** Tree `sha256:596d1368ac157975…`, file `sha256:2aff27070177d9f3…`, both recomputed in this refresh and both equal to the Gate-1 record.
- **Skill improver — changed since Gate 1.** Gate 1 approved `sha256:e6bc16c4d6740a0c…`. This release ships `sha256:d5a381bed8ae5ddd…`, recomputed here from `../techtree-plugin/skills/skill-improver/SKILL.md`. The difference is one line, read from the plugin's own history in this refresh: the sentence describing what the improvement context omits lost the word `secrets`, going from "hidden task fields, grader source, secrets, and private paths" to "hidden task fields, grader source, and private paths". Decision 0036 deleted all secret-shaped-string detection from the project, so the Skill could no longer claim the context excludes secrets. The fingerprint records the same fact under `cross_check`, with `skill_improver_matches_gate1: false`. **The previous edition of this document stated that both Skill digests are unchanged in this lineage. That is no longer true, and the sentence has been replaced rather than kept.**

Neither the Gate-1 packet nor Addendum 1 (`sha256:568f3a53…`, recomputed here) names the lineage above; both predate the 0029 budget contract and the engine move. Decision 0025 §4 settles the disposition: the packet bytes are never edited, and the current lineage travels in the Gate-2 packet.

## How to read this

One row per public product claim. Each row names the modules that implement it, tests that exist in the trees today, the live evidence from this lineage, and the limitation that must travel with the claim in public copy.

**Where live evidence lives, and a change since the last edition.** Run trees are not committed to this repository — `runs/` is empty by design and raw subject traces stay on the participant's machine because they carry the taskset's expected answers (spec §6.19). The previous edition could point at a durable archive under `certification-evidence/` for every run it cited. **This lineage has no such archive.** The three certification executions and the founder walkthrough live in the founder's own live Techtree home at `~/Library/Application Support/techtree/runs/`; the two WP11f onboarding runs live under the WP11f journey home in a scratchpad. Both locations were read directly in this refresh — run directories, signed reports, proof bundles, episode receipts, resolved engine configurations, supervision records and journals. Wherever a row cites a run it cites the run's own bytes. That the bytes are not archived is a gap, and it is in the register.

**Wording.** The matrix records exact measured scores because it is a certification record. Public copy states the calibrated 20-27/36 band and never an exact score; says "no Techtree account is required", never "no account required"; says participant-attested and not independently reproduced, never independently verified; always qualifies privacy statements with the fact that model calls go to the selected provider; and, per **decision 0035**, any surface that says what this release *is* carries the proof-of-concept frame — a proof of concept for a stack of three independent parts (Prime Intellect's Verifiers, Nous Research's Hermes, Techtree), never a benchmark, an evaluation suite, a measured capability or a validated uplift.

**Model scope (decision 0033).** v0.1 ships exactly this lineage: qwen/qwen3.7-flash served by Prime, with no re-certification. The 20-27/36 band is calibrated on that model and does not transfer to any other.

**Secret handling (decision 0036).** Techtree ships no secret-shaped-string detection of any kind. The text scrubber and the Skill scanner's secret patterns are deleted, not disabled. What remains, and is not secret detection, is the environment allowlist, control-character stripping, memory-address normalisation, and Skill refusals based on shape (size, file count, symlinks, hidden paths, non-text bytes). Every row that cited secret redaction as evidence has been corrected, and the rows that carried a claim about it now carry a gap instead.

## What this refresh verified

Executed here, 2026-08-27, in `techtree-python`:

- `make check` — passed end to end. Its last line is `generated-check: generated artifacts match the working tree`, and its test leg reports **3019 passed, 1 skipped, 295 deselected**. The one skip is `tests/unit/test_skill_scanner.py::test_the_case_collision_rule_holds_on_a_case_folding_filesystem`, which skips on this machine's case-folding filesystem.
- `uv run pytest tests/unit` — **2554 passed, 1 skipped**.
- `uv run pytest tests/contract` — **465 passed**.
- `uv run pytest -m "integration and not real_model"` — **293 passed, 3022 deselected**.
- `make test-plugin` (`tests/plugin`) — **857 passed**. The seven suites this matrix cites by name (`test_approvals`, `test_guards`, `test_bootstrap`, `test_release`, `test_one_generation_request`, `test_plugin_doctor`, `test_one_turn_revision`) — **187 passed**.
- `uv run techtree proof verify <run>/proof` on **all six** runs of this lineage — each reports **339 checks, all passed, verified**: files and key present, 84/84 stored file digests, 18/18 linkage and control, 225/225 signatures, aggregate recomputation passed, 2/2 publication, 8/8 proof-grade conditions. Each carries the one standing warning, "No independent reproduction: nobody else has run this comparison, and no platform witnessed it."
- An immutability sweep over the six run trees: **1,271 files**. Exactly **two** were modified more than a second after their own run's last journal event, and both are `improvement/context.json` — the improvement context, which is written when the participant later asks for a guided revision and is not part of any proof bundle. Across all six `proof/` directories, **504 files, none modified after the run's last journal event.**
- A limits sweep read from the trace files themselves, across all six runs: **432 episodes, every one stopping with `agent_completed`**, 0 errored, 1,753 model calls, the busiest single episode using **23** of the 44 compiled turns, and **0** model calls at or over the 4,096-token sampling ceiling.

Citation resolution: **287 test citations (280 distinct) and 103 implementation path references (74 distinct)** were resolved mechanically against the trees before being written down; every one resolved. Nine citations in the previous edition did not resolve; all nine are dealt with under "Corrections".

Not executed here:

- The four `techtree-ash` citations (`../techtree-ash/test/techtree_web/router_test.exs`, `../techtree-ash/test/techtree_web/endpoint_test.exs`). The Ash test setup needs a PostgreSQL database that is not available to this worker, so those four test names were verified by reading the files, not by running them. Note the path: the previous edition wrote them as `techtree-ash/…`, which resolves only from the workspace root; they are written `../techtree-ash/…` here, matching the convention already used for the plugin.
- The five cited preflight tests. They are marked `preflight`, excluded from the default selection, and need a pinned Verifiers install and registry access; all five names were verified to exist by reading the files.
- No `real_model` test is cited anywhere in this matrix, and none was run. **No run of any kind was started for this refresh and no money was spent.**

## Canonical certification runs — this lineage

Three certification executions of the shipping Campaign, listed in `release/certified-scientific-fingerprint.json` under `recertification_runs`, each a controlled baseline-versus-starter-Skill comparison over the same 36 committed tasks. They ran in the founder's own Techtree home through the real detached launcher and the real child-local supervisors. Every figure below was read from the run's own stored bytes in this refresh.

| Run | ID | Score | W/L/T | Report (file digest) | Bundle (payload digest) | Cost (USD, worked out) |
|---|---|---|---|---|---|---|
| certification #1 | `run_c4758ddb5bba4023aa3530b47f4582e9` | 0/36 -> 23/36 | 23/0/13 | `sha256:b8094b55...` | `sha256:b4389136...` | 0.1149 |
| certification #2 | `run_55159aeb30c44982b8143f61b078a4db` | 0/36 -> 23/36 | 23/0/13 | `sha256:2736aa17...` | `sha256:bf772673...` | 0.1446 |
| certification #3 | `run_8f89ae9dea6541b187c74d86d119d8a6` | 0/36 -> 24/36 | 24/0/12 | `sha256:8a9eb2ac...` | `sha256:cb496b91...` | 0.1143 |

Signed execution records, one per comparison, payload digests read from `proof/comparison-execution.json`: `sha256:afcbed2c...`, `sha256:7651023e...`, `sha256:4e8a89d4...`. The fingerprint's `execution_record_digest` field for each run is the file digest of that run's `execution/real-execution-result.json` (`sha256:efb59ff5...`, `sha256:f7ff6940...`, `sha256:dc9b9cba...`); both are recorded so neither is mistaken for the other.

All three: `controlled_with_warnings`, evidence complete, score valid, execution completed, decision accepted, proof grade P1, `executor_kind` verifiers, manifest comparison `controlled: true` with zero violations and exactly one allowed difference, proof verifies offline, `publication_eligible: false`. Across the three: **216 episodes, every one `agent_completed`, 0 errored, 0 reaching any enforced limit, 0 calls at or over the 4,096 sampling ceiling**, and the longest variant took 614.5 s against the 3,600-second supervisor deadline — a 5.9x margin.

**A fourth run of the same Campaign, which is not a certification.** `run_b3e25a431d3b43128deb31e99a0b6c68` is the founder's own walkthrough through Hermes, completed 2026-08-27T05:23:53Z: 0/36 -> 23/36, 23/0/13, report `sha256:6b830389...`, bundle payload `sha256:d0345d17...`, proof verifies 339/339, worked-out cost USD 0.1028. Its run request records policy acknowledgement by `host_agent_confirmation` and its approval actor is `human_via_hermes` rather than the CLI's explicit review. The fingerprint holds it outside `recertification_runs` under `founder_walkthrough_run` so it cannot be counted as one, and this document does the same. It is cited below only as evidence about the host-agent approval surface and about the shipping lineage running end to end, never as a certification execution.

**Two further runs of this lineage, from the WP11f onboarding acceptance.** Recorded in `release/acceptance/onboarding-e2e.json`, performed 2026-08-27 08:10Z–09:05Z from a fresh home on the founder's Mac by an acceptance worker acting as operator. Both proofs verify 339/339 and both were read directly in this refresh.

| Run | ID | Comparison | Score | W/L/T | Report (file digest) | Bundle (payload digest) | Cost (USD, worked out) |
|---|---|---|---|---|---|---|---|
| first comparison | `run_618a27f7fde4465ebe02a6bf33b71f7c` | no Skill vs starter Skill | 0.000 -> 0.639 | 23/0/13 | `sha256:bfa53e08...` | `sha256:4c7f46a2...` | 0.1168 |
| second comparison | `run_4584be6d8e1248ce9495a51ce2059fee` | Skill v1 vs guided Skill v2 | 0.639 -> 0.667 | 1/0/35 | `sha256:067dd5e5...` | `sha256:f4250b61...` | 0.0580 |

The second comparison runs derived Campaign `sha256:0f3cb0141feb0ee6…`. This refresh flattened it against the shipped Campaign field by field: it differs in exactly two places, the baseline arm's mounted Skill (now `596d1368…`, 1,496 bytes, where the shipped Campaign has none) and `/mutation_contract/kind` (`skill_replacement` where the shipped Campaign says `skill_insertion`). Budgets, execution contract, taskset, membership, subject model, sampling and runtime are byte-identical.

**A note on run identity, so nothing is over-counted.** A filesystem search recorded in the fingerprint found exactly four stored runs whose `proof/campaign.json` is the shipped Campaign: the three certification executions and the walkthrough. The WP11f first comparison is a fifth, in a scratchpad home the fingerprint's search did not cover, and the WP11f second comparison is a sixth on the derived Campaign. **An earlier record in this project said five runs scoring 23, 23, 24, 23, 23. That count was wrong; it is not carried forward, and no fifth certification run is claimed anywhere below.**

**How the cost figures were arrived at.** Every one of the six runs' own signed `ComparisonExecutionRecord` reports `cost_usd: null` with provenance `unavailable` for **both** variants — "no cost figure was reported for this variant, and this build pins no price to compute one from". The dollar figures above were computed in this refresh from each run's own recorded token counts at the rate card in `release/price-profile.json` (qwen/qwen3.7-flash, USD 0.03 / 0.13 per Mtok, recorded 2026-08-20), charging every input token at the uncached rate. On the cached-input-free basis the same six runs are 0.0725, 0.0889, 0.0798, 0.0708, 0.0876 and 0.0489. The product itself never states either figure as a provider-billed amount.

**Programme spend, and what cannot be sourced.** The WP11f journey's own record accounts for its three paid legs against a USD 1.50 authorisation: first comparison 0.1168, one guided-revision host completion 0.0441 (the single provider-reported cost anywhere in this lineage), second comparison 0.0580, total **USD 0.2189**, no leg over the 0.30 ceiling, no paid outcome retried, every leg estimated before it ran. **No ledger was found for the three certification executions or the walkthrough.** The previous edition could cite `certification-evidence/recert-0025/NOTES.md` for a programme total of USD 4.2487 against a 15.00 cap; that ledger belongs to the superseded quiet window and is not carried forward. What this refresh can state from the runs' own bytes is that the four founder-home runs cost **USD 0.4766** on the uncached basis (0.3120 cached-free). The absence of a ledger for them is a gap and is in the register.

## Coordinates re-verified by this refresh

Recomputed from the working tree with `shasum -a 256`, or hashed out of a proof bundle where the row says so; every value equals `release/certified-scientific-fingerprint.json`.

| Object | Digest | Source |
|---|---|---|
| campaign | `sha256:ebf029abb266ca74...` | src/techtree/resources/catalog/campaigns/hello-world-climb.json |
| climb | `sha256:a3a5e9c5f9b40d4f...` | src/techtree/resources/catalog/climbs/hello-world-climb.json |
| data policy | `sha256:6c532a43d595286a...` | src/techtree/resources/catalog/data-policies/hello-world-climb.json |
| validation receipt | `sha256:4944bd71caa1a295...` | src/techtree/resources/catalog/taskset-validations/hello-world-climb.json, and independently hashed out of `proof/taskset-validation-receipt.json` of all six runs |
| validation evidence | `sha256:991be5e42acbd48c...` | src/techtree/resources/catalog/validation-evidence/hello-world-climb.json |
| taskset lock | `sha256:8bed6f7c7f8b1a70...` | hashed out of `proof/taskset-lock.json` of all six runs, not out of the repository |
| taskset membership | `sha256:56f697fb182cc316...` | the same lock, and the shipped Campaign's `taskset.membership.membership_digest`; unchanged across the engine move |
| taskset package | `sha256:f42a0d5e968478af...` | the same lock, `resolved_package_digest` (embedded procedure-transfer-v1 0.1.0) |
| engine | `sha256:29b1bbb8327d8f1a...` | release/release-core.json `engine_digest`; also in every `proof/taskset-lock.json` and every `proof/taskset-validation-receipt.json` |
| catalog | `sha256:10a7fcc5de1951c1...` | release/release-core.json `catalog_digest` |
| starter skill file | `sha256:2aff27070177d9f3...` | release/skills/hello-world-starter-v1/SKILL.md |
| starter skill tree | `sha256:596d1368ac157975...` | release/release-core.json `starter_skill_digest` (the pin, decision 0008) |
| skill improver file | `sha256:d5a381bed8ae5ddd...` | ../techtree-plugin/skills/skill-improver/SKILL.md — **not** the digest Gate 1 approved |
| release core | `sha256:bef3b9d4c987209c...` | byte-identical in techtree-python/release/release-core.json, src/techtree/resources/release/release-core.json and ../techtree-plugin/release-core.json; all three recomputed here |
| certified fingerprint | `sha256:38b2f2ef481182af...` | release/certified-scientific-fingerprint.json |
| gate1 packet | `sha256:b3ea3ba12af27af8...` | release/founder-skill-approval-draft.md |
| gate1 addendum 1 | `sha256:568f3a5371543d54...` | release/founder-skill-approval-addendum-1.md |
| candidate wheel | `sha256:e486b3eaa4774555...` | dist/techtree-0.1.0-py3-none-any.whl, per release/plugin-release-candidate.json and release/fresh-install-report.json |

**One coordinate the previous edition got wrong.** It listed the engine digest as appearing "in every episode receipt". It does not. This refresh read all 432 episode receipts of this lineage: an `EpisodeReceipt` carries `campaign_spec_digest`, `data_policy_digest`, `experiment_manifest_digest`, `episode_digest`, `task_hash`, `subject_runtime`, `named_traces` and its artifacts, and **no engine digest at all**. The engine digest is committed in the taskset lock, the validation receipt and the signed execution record.

Subject coordinates, read from the shipped Campaign and confirmed in the resolved engine configuration of every variant of every run: qwen/qwen3.7-flash, provider prime, credential env PRIME_API_KEY, revision null, sampling temperature 0 and max_tokens 4096, harness hermes-agent 0.19.0, runtime docker on `python@sha256:90744cff…` with per-platform manifest digests for linux/amd64 (`78b39ef1…`) and linux/arm64 (`20eadabc…`), network policy restricted (`allow = []`, `block = ["*"]`), cpu 2.0, memory 4.0 GB. Enforced budgets, compiled into both variants: max_turns 44, max_input_tokens 900,000, max_output_tokens 16,000, max_total_tokens 916,000 (derived), rollout timeout 600 s, maximum_usd 2.50.

**A path that changed with the engine.** The previous edition cited the resolved engine configuration as `verifiers/<variant>/run/config.toml`. Verifiers 0.3.1 writes it as JSON at `verifiers/<variant>/run/configs/resolved/eval.json`, and no `config.toml` exists in any run tree of this lineage. Every citation below uses the real path.

## Required rows (contract §Required rows)

### claim-01 — Campaign immutable

**Public wording.** The Climb the two subjects run is fixed before either of them starts, and cannot be changed afterwards without the change being visible.

**Implementation**

- `src/techtree/models/base.py` — ProtocolModel (frozen=True, strict=True, extra='forbid'); ObjectEnvelope
- `src/techtree/canonical.py` — canonical_json_bytes / digest_object / verify_object_digest
- `src/techtree/models/campaign.py` — CampaignSpec and its committed sub-objects
- `src/techtree/catalog/repository.py`, `src/techtree/catalog/service.py` — digest-addressed object reads

**Automated test**

- `tests/unit/test_canonical.py::test_protocol_models_are_frozen`
- `tests/unit/test_canonical.py::test_one_field_mutation_changes_the_digest`
- `tests/unit/test_canonical.py::test_key_insertion_order_does_not_change_the_digest`
- `tests/unit/test_campaign_models.py::test_one_field_change_changes_the_campaign_digest`
- `tests/unit/test_campaign_models.py::test_reparsing_the_same_document_gives_the_same_digest`
- `tests/unit/test_campaign_models.py::test_execution_artifacts_anchor_on_the_campaign_digest`
- `tests/unit/test_manifest_builder.py::test_building_does_not_mutate_the_campaign`
- `tests/unit/test_local_bundle_verify.py::test_an_edited_campaign_breaks_the_proof`
- `tests/contract/test_catalog_object_graph.py::test_a_file_that_drifted_from_its_digest_fails_verification`

**Live evidence**

- Campaign hello-world-climb `sha256:ebf029abb266ca74…` — recomputed in this refresh from src/techtree/resources/catalog/campaigns/hello-world-climb.json and equal to the fingerprint's `campaign_spec_digest`.
- Five of the six runs anchor on it directly: it is the value of `campaign_spec_digest` in each run's own `report/uplift.json`, and `proof/campaign.json` of each of those runs hashes to it exactly. The sixth, the guided-revision comparison, anchors on derived Campaign `sha256:0f3cb0141feb0ee6…`, which this refresh flattened against the shipped one and found to differ in exactly two fields.
- All 432 signed episode receipts of the six runs carry the Campaign digest their run ran under, and each proof bundle commits to the Campaign document it ran.
- The engine move is itself immutability evidence rather than an exception to it: two fields of the Campaign changed and the digest changed with them, which is the guarantee working. The membership digest `sha256:56f697fb182cc316…` did not change, and recomputing it from the 36 committed task hashes reproduces it.
- Immutability, measured in this refresh rather than asserted: across the six run trees, 1,271 files. Every one of the 504 files inside the six `proof/` directories is unmodified since its run's last journal event. Two files elsewhere were written later — `improvement/context.json` in the walkthrough (+2,199 s) and in the WP11f first comparison (+144 s) — because the improvement context is built when the participant afterwards asks for a guided revision. Neither is part of any proof bundle.

**Limitation.** 'Campaign' is an internal protocol concept; a participant never names one. Immutability is enforced by recomputing digests over frozen canonical bytes — there is no external registry, notary or timestamping authority, so the guarantee is 'this object is not the object it claims to be if a byte moved', not 'this object existed before that moment'. The Campaign has now been regenerated three times under founder rulings and one engine pin (decisions 0025, 0029, and the move to released Verifiers 0.3.1); immutability is a property of each version's bytes, not a claim that the shipped Campaign has never changed.

### claim-02 — Same tasks on both sides

**Public wording.** Both subjects are scored on exactly the same tasks, in the same order.

**Implementation**

- `src/techtree/models/validation.py` — TasksetLock
- `src/techtree/models/campaign.py` — TaskMembershipCommitment, CampaignTaskset, TaskSelection
- `src/techtree/tasksets/membership.py` — membership_digest, assert_unique_task_hashes, compare_membership
- `src/techtree/tasksets/resolver.py`, `src/techtree/tasksets/service.py` — lock derivation from the engine inspection
- `src/techtree/receipts/set.py` — the per-variant receipt set commits to the locked membership

**Automated test**

- `tests/unit/test_taskset_membership_logic.py::test_the_membership_digest_is_the_digest_of_the_named_ordered_object`
- `tests/unit/test_taskset_membership_logic.py::test_the_membership_digest_depends_on_order`
- `tests/unit/test_taskset_membership_logic.py::test_a_repeated_task_is_refused_with_both_positions`
- `tests/unit/test_taskset_membership_logic.py::test_identical_memberships_pass_as_the_commitment_check`
- `tests/unit/test_taskset_membership_logic.py::test_a_shorter_membership_reports_both_counts_and_the_missing_task`
- `tests/integration/test_taskset_membership.py::test_the_locked_membership_satisfies_a_campaign_commitment`
- `tests/integration/test_taskset_membership.py::test_no_task_is_locked_twice`
- `tests/integration/test_taskset_membership.py::test_the_reference_taskset_locks_to_its_whole_frozen_dataset`
- `tests/unit/test_receipt_set.py::test_the_set_commits_to_the_membership_the_lock_commits_to`
- `tests/unit/test_observed_comparison.py::test_a_lock_over_other_tasks_is_invalid`
- `tests/contract/test_protocol_golden_files.py::test_the_lock_and_the_campaign_commit_to_the_same_tasks`

**Live evidence**

- Membership digest `sha256:56f697fb182cc316…` — read in this refresh from the shipped Campaign's `taskset.membership.membership_digest` and, independently, from `proof/taskset-lock.json` of all six runs, where it appears alongside `task_count: 36` and resolved package `sha256:f42a0d5e968478af…`.
- Taskset lock `sha256:8bed6f7c7f8b1a70…`, hashed from the copy inside each of the six proof bundles; the same value in all six, and equal to the fingerprint's `taskset_lock_digest`.
- The engine move is the strongest membership evidence this lineage has. The fingerprint's `engine_move` block records that all 36 committed task hashes are byte-identical and in the same order across the change, that the membership digest is the same value, and that recomputing that digest from the hashes reproduces it — `taskset_membership_unchanged: true`, `taskset_membership_task_count: 36`. It was derived from three independent sources: the packaged catalog inside the wheel, `git show` of the same files at the parent of the engine-move commit, and the campaign.json stored in a proof directory of a run executed under the superseded Campaign.
- Every one of the six comparisons reports exactly 36 `task_deltas`, and each carries 36 baseline plus 36 candidate signed receipts — 432 receipts in total, counted in this refresh, all `evidence_status: complete` and `score_status: valid`.
- The guided-revision comparison reports 1 win / 0 losses / 35 ties over exactly those 36 tasks.

**Limitation.** Fixed membership: v0.1 ships one 36-task selection taken from the head of the frozen dataset order (`num_tasks` 36, `num_rollouts` 1, `shuffle` false). There is no sampling, no task selection, no held-out split and no rotation. What is proved is that both arms saw identical tasks — not that those tasks are representative of anything.

### claim-03 — Taskset validated before it is used

**Public wording.** The tasks are checked before any paid run: every task's own answer scores, and a known-wrong answer does not.

**Implementation**

- `src/techtree/models/validation.py` — ValidationReceipt, TasksetLock, validation evidence models
- `src/techtree/tasksets/provider.py` — the run-layer validation gate
- `src/techtree/tasksets/verifiers_cli.py`, `src/techtree/tasksets/service.py` — the pinned validator invocation
- `src/techtree/runs/validation.py` — refusal path before any episode runs

**Automated test**

- `tests/integration/test_taskset_validation.py::test_every_task_passes_gold_and_setup`
- `tests/integration/test_taskset_validation.py::test_the_taskset_rejects_a_known_wrong_answer`
- `tests/integration/test_taskset_validation.py::test_the_receipt_reports_every_required_check_as_passed`
- `tests/integration/test_taskset_validation.py::test_nothing_errored_timed_out_or_went_missing`
- `tests/integration/test_taskset_validation.py::test_a_tampered_membership_makes_the_receipt_invalid`
- `tests/integration/test_taskset_validation.py::test_the_method_names_the_pinned_validator`
- `tests/integration/test_taskset_validation.py::test_validation_failure_blocks_the_fake_phases`
- `tests/unit/test_validation_provider.py::test_a_receipt_that_reports_invalid_stops_the_run`
- `tests/unit/test_validation_provider.py::test_a_receipt_the_campaign_does_not_commit_to_is_refused`
- `tests/unit/test_validation_provider.py::test_evidence_that_is_not_what_the_receipt_names_is_refused`
- `tests/unit/test_fake_executor.py::test_a_refused_validation_stops_before_any_episode`

**Live evidence**

- Validation receipt `sha256:4944bd71caa1a295…` — hashed in this refresh from `proof/taskset-validation-receipt.json` of all six runs, identical in every one, and equal to the shipped `src/techtree/resources/catalog/taskset-validations/hello-world-climb.json`. The published receipt is the one that travelled inside every certified proof.
- Its six checks, read from those bytes, all `passed`: `upstream_gold` (all 36), `upstream_setup` (all 36), `membership_repeatability` (two independent inspections agreed on all 36 hashes in order), `task_hash_uniqueness` (all 36 distinct), `committed_membership_match` (all 36 match in order), `expected_task_count` (36, as the selection asks for). Status `valid`, method `verifiers_validate`, mode `all`, runtime `subprocess`.
- The validator revision recorded in the receipt is `b2e4e8157783b2c0dffc7821044c87f29f1c3ccf` — the released Verifiers 0.3.1, not the pre-release development revision `7e1c47d2…` the previous edition cited. The receipt's `engine_digest` is `sha256:29b1bbb8327d8f1a…`, this release's engine.
- Validation evidence `sha256:991be5e42acbd48c…`, named by that receipt as `normalized_evidence` (6,889 bytes, application/json) and equal to the shipped copy; the receipt's own `upstream_summary` records total 36, recorded 36, valid 36, invalid 0, error 0, timeout 0, missing 0, valid_rate 1.
- `make check` re-derived the fixture catalog from the pinned engine in a throwaway tree during this refresh and printed `hello-world-climb@1: 36 tasks, validation valid, receipt sha256:4944bd71…` — the same receipt, regenerated rather than read.

**Limitation.** Mechanical only, and narrower than the sentence suggests. The receipt's own checks establish that every task's gold answer scores and its setup resolves; the known-wrong-answer control is an automated test over the taskset (`test_the_taskset_rejects_a_known_wrong_answer`), not one of the six checks the shipped receipt carries. Neither says anything about whether a task is well-posed, unambiguous, non-trivial, or free of leakage into the subject model's training data.

### claim-04 — Neutral baseline

**Public wording.** The baseline subject carries no Skill at all — it is the same machine with nothing added.

**Implementation**

- `src/techtree/manifests/builder.py` — baseline/candidate manifest construction and its postconditions
- `src/techtree/manifests/compare.py` — assert_controlled_comparison, _skill_count_violations
- `src/techtree/verifiers/compiler.py` — what each variant actually mounts
- `src/techtree/receipts/observed.py` — _mounted_skill_digests, read back from the resolved engine config

**Automated test**

- `tests/unit/test_manifest_builder.py::test_the_baseline_preserves_the_campaign_and_carries_no_skill`
- `tests/unit/test_manifest_builder.py::test_the_candidate_preserves_the_campaign_and_carries_exactly_one_skill`
- `tests/unit/test_manifest_builder.py::test_a_campaign_whose_subject_already_carries_a_skill_is_refused`
- `tests/unit/test_verifiers_compiler.py::test_the_baseline_mounts_no_skill_and_the_candidate_mounts_exactly_one`
- `tests/unit/test_manifest_compare.py::test_a_baseline_that_already_carries_a_skill_is_rejected`
- `tests/unit/test_observed_comparison.py::test_a_baseline_that_mounted_a_skill_is_invalid`
- `tests/unit/test_observed_comparison.py::test_an_insertion_whose_baseline_declares_a_skill_is_invalid`
- `tests/unit/test_observed_comparison.py::test_a_recorded_skill_insertion_is_controlled`
- `tests/unit/test_campaign_models.py::test_the_development_campaign_is_a_skill_insertion`

**Live evidence**

- All five insertion comparisons of this lineage scored the baseline **0/36**: run_c4758ddb…, run_55159aeb…, run_8f89ae9d…, the walkthrough run_b3e25a43… and the WP11f first comparison run_618a27f7…, each read from its own report's `primary_result.baseline_mean: 0`.
- The manifest comparison of each of those five records exactly one difference, at pointer `/agents/subject/harness/skills/0`, with `baseline: null` — the baseline mounts nothing. The candidate side names `sha256:596d1368…` (1,496 bytes, media type application/vnd.techtree.instruction-skill.v1) in all five.
- The resolved engine configuration the baseline actually ran under (`verifiers/baseline/run/configs/resolved/eval.json`) carries `env.subject.harness.skills: []`, and the candidate's carries exactly one path, the staged tree `sha256-596d1368…`. Read in this refresh from the runs' own bytes.
- The shipped Campaign's `mutation_contract` is `skill_insertion`, minimum 1 / maximum 1 skill, allowed difference `/agents/subject/harness/skills`. The one comparison that is not an insertion, the guided-revision run, carries a derived Campaign whose contract says `skill_replacement` and whose baseline arm therefore does mount a Skill — by construction, and recorded as such.

**Limitation.** Toy task. The baseline floor of 0/36 is on one synthetic 36-task BranchCode taskset built for this demo. A zero floor shows the Skill is doing the work in this Climb; it does not show that the measurement generalises to real tasks. Under decision 0035 the whole lineage is a proof of concept for the Verifiers/Hermes/Techtree stack, not a measurement of capability.

### claim-05 — Clean subjects

**Public wording.** Each subject runs in a pinned container, with the same image, harness and sampling on both sides.

**Implementation**

- `src/techtree/verifiers/config.py` — runtime and network-policy compilation; digest-pinned image recognition
- `src/techtree/verifiers/compiler.py` — the per-variant execution plan handed to the engine
- `src/techtree/verifiers/image.py`, `src/techtree/verifiers/child.py` — image resolution and child-process execution
- `src/techtree/receipts/observed.py` — ObservedSubjectConfiguration, built from what the engine resolved and ran
- `src/techtree/models/episode_receipt.py` — the runtime block that records resolved_image_digest and platform

**Automated test**

- `tests/unit/test_verifiers_config.py::test_a_runtime_other_than_docker_cannot_be_named`
- `tests/unit/test_verifiers_config.py::test_a_digest_pinned_image_is_recognised_and_a_tagged_one_is_not`
- `tests/unit/test_verifiers_config.py::test_a_campaign_network_policy_compiles_to_the_normalized_egress_pair`
- `tests/unit/test_verifiers_compiler.py::test_a_restricted_campaign_runtime_compiles_to_framework_only_egress`
- `tests/unit/test_observed_configuration.py::test_an_image_the_daemon_was_not_asked_about_is_refused`
- `tests/unit/test_observed_configuration.py::test_rollouts_that_ran_different_images_are_refused`
- `tests/unit/test_observed_configuration.py::test_a_platform_the_campaign_pins_no_manifest_for_is_refused`
- `tests/unit/test_episode_receipt_builder.py::test_a_receipt_names_the_container_the_subject_ran_in`
- `tests/unit/test_manifest_compare.py::test_a_changed_runtime_image_is_rejected`
- `tests/preflight/test_subject_image_pin.py::test_every_pinned_platform_digest_is_the_one_the_index_lists`
- `tests/preflight/test_subject_image_pin.py::test_the_pin_names_an_oci_image_index`

**Live evidence**

- All 432 signed episode receipts of the six comparisons record the same `subject_runtime.resolved_image_digest`, `sha256:90744cff8f32887f…`, and `kind: docker` — counted in this refresh from the receipts themselves.
- The resolved configuration both variants ran under (`verifiers/<variant>/run/configs/resolved/eval.json`) carries the same pinned image, `cpu 2.0`, `memory 4.0`, egress `allow: []` / `block: ["*"]`, `sampling.temperature 0.0` and `sampling.max_tokens 4096`, and the same compiled ceilings on both sides (max_turns 44, max_input_tokens 900,000, max_output_tokens 16,000, max_total_tokens 916,000, rollout timeout 600 s).
- The per-platform manifest digests are carried in the signed experiment documents rather than only declared: `proof/baseline-experiment.json` and `proof/candidate-experiment.json` of each run record `image_platform_digests` for linux/amd64 (`sha256:78b39ef1…`) and linux/arm64 (`sha256:20eadabc…`) alongside the index digest and `network_policy: restricted`.
- Supervision records written by the child-local supervisor for every variant (`verifiers/<variant>/supervision.json`, mode 0600) record `reason: completed`, `escalated_to_sigkill: false`, a 3,600-second deadline and a 20-second grace. The worst variant of any run of this lineage took 672.2 s.
- Measured from the trace files in this refresh: 432 episodes, every one `stop_condition: agent_completed`, none errored, the busiest single episode using 23 of the 44 compiled turns, and no model call at or over the 4,096-token sampling ceiling.

**Limitation.** Local executor. The containers run on the participant's own Docker daemon; Techtree records what that daemon reported and verifies the two sides agree, but nothing attests that the daemon, the image or the host were unmodified. Raw subject traces stay on the participant's machine and are deliberately not committed (spec §6.19) because they carry the taskset's expected answers.

**Gaps (findings, not fixed here)**

- The `platform` field is `null` in all 432 receipts of this lineage. What those receipts establish is that every episode on both sides resolved the same image **index** digest; the per-platform manifest digests are a declared pin, carried in the signed experiment documents and checked by a preflight test, not something the receipts recorded. No public copy may say the two variants resolved to the same platform-specific digest.
- No trace-level artifact from any run of this lineage is committed to this repository. The traces exist — `verifiers/<variant>/run/traces.jsonl`, whose digests are committed inside each signed execution record and episode receipt — but they live only in the founder's own Techtree home and the WP11f scratchpad. The only committed trace-level evidence is the sanitized fixture at `tests/fixtures/receipts/recorded/`, which came from run_6ce5e56a7dd341bca8bc6de1d6a60027 under a **doubly superseded** Campaign. It is a conformance asset for the receipt pipeline, not evidence about the shipped lineage.

### claim-06 — Only the Skill changed

**Public wording.** Techtree proves that the Skill was the only difference between the two sides.

**Implementation**

- `src/techtree/manifests/compare.py` — compare_manifests, assert_controlled_comparison, pointer/variant/skill-count violations
- `src/techtree/receipts/compare.py` — the observed tool-surface comparison, the single named SKILL_INDEX_TOOL exception, MODEL_REVISION_UNDISCOVERABLE and weaker_claim_warnings
- `src/techtree/receipts/observed.py` — observed_from_episodes, _require_no_drift, _require_config_agrees_with_traces
- `src/techtree/models/uplift_report.py` — ComparisonStatus (controlled / controlled_with_warnings / invalid)

**Automated test**

- `tests/unit/test_observed_comparison.py::test_an_unauthorized_observed_difference_is_invalid`
- `tests/unit/test_observed_comparison.py::test_a_subject_sampled_differently_than_declared_is_invalid`
- `tests/unit/test_observed_comparison.py::test_an_undeclared_sampling_parameter_is_invalid`
- `tests/unit/test_observed_comparison.py::test_an_extra_tool_is_not_permitted`
- `tests/unit/test_observed_comparison.py::test_a_differing_parameter_schema_is_not_permitted`
- `tests/unit/test_observed_comparison.py::test_a_differing_description_on_another_tool_is_not_permitted`
- `tests/unit/test_observed_comparison.py::test_a_second_differing_description_is_not_permitted`
- `tests/unit/test_observed_comparison.py::test_only_the_skill_index_tool_may_describe_itself_differently`
- `tests/unit/test_observed_comparison.py::test_a_different_reward_weight_is_invalid`
- `tests/unit/test_observed_comparison.py::test_a_declared_skill_the_subject_never_read_is_invalid`
- `tests/unit/test_observed_comparison.py::test_a_recorded_skill_insertion_is_controlled`
- `tests/unit/test_observed_comparison.py::test_a_skill_replacement_is_controlled`
- `tests/unit/test_observed_comparison.py::test_the_one_honest_warning_is_the_only_one`
- `tests/unit/test_observed_configuration.py::test_inserting_a_skill_changes_exactly_one_tool_description`
- `tests/unit/test_manifest_compare.py::test_a_changed_campaign_digest_is_rejected`
- `tests/unit/test_manifest_compare.py::test_the_insertion_contract_still_refuses_a_replacement_shaped_pair`

**Live evidence**

- UpliftReport file digests, one per comparison, hashed in this refresh: `sha256:b8094b55…`, `sha256:2736aa17…`, `sha256:8a9eb2ac…` (certification), `sha256:6b830389…` (walkthrough), `sha256:bfa53e08…` and `sha256:067dd5e5…` (WP11f).
- Each report's `manifest_comparison` records `controlled: true`, `violations: []`, `allowed_differences: ["/agents/subject/harness/skills"]`, and its own baseline and candidate configuration digests. The five insertion comparisons carry exactly one entry in `differences` — the mounted Skill. The guided-revision comparison carries exactly two, both on the same skill slot: the digest (`596d1368…` to `5e2e2f58…`) and the size (1,496 to 1,897 bytes). Nothing else differed in any of the six.
- All six are graded `controlled_with_warnings`, score valid, evidence complete, execution completed, accepted, P1.
- The warning is `model_revision_discoverable` (`src/techtree/receipts/compare.py`, `MODEL_REVISION_UNDISCOVERABLE`). `weaker_claim_warnings` raises it exactly when the Campaign's `subject.model.revision` is null, which this Campaign's is — read from the shipped Campaign in this refresh. The provider publishes no revision for qwen/qwen3.7-flash, so both variants are known to have used the same model identifier and not the same model build.

**Limitation.** Known derived description delta, plus one accepted warning. Mounting a Skill necessarily changes one tool description, because the harness renders the index of visible Skills into its own `skill_manage` tool description; that one difference is permitted by name in src/techtree/receipts/compare.py (SKILL_INDEX_TOOL) and a second differing description is refused. Separately, the provider exposes no immutable revision for the selected model alias, so every release comparison is controlled_with_warnings rather than controlled (decision 0007 R5). The comparison is over what the engine recorded, not over independent observation of the containers.

**Gaps (findings, not fixed here)**

- The warning's identity is not readable from any artifact of this lineage. What each run stores is the status `controlled_with_warnings`; the string `model_revision_discoverable` appears in no report, receipt, journal or execution record of the six runs. It is established here from the code that raises it plus the shipped Campaign's `revision: null`. The previous edition sourced the warning's name from a worker ledger; that ledger belongs to the superseded quiet window and no ledger exists for these runs.

### claim-07 — Per-task receipts

**Public wording.** Every task produces its own receipt, and the set of receipts cannot be edited without the edit showing.

**Implementation**

- `src/techtree/receipts/episode.py` — the per-episode receipt builder
- `src/techtree/models/episode_receipt.py` — EpisodeReceipt and its evidence status
- `src/techtree/receipts/set.py` — the receipt-set manifest and its commitment
- `src/techtree/runs/artifacts.py` — how receipts are written to and read back from the run tree

**Automated test**

- `tests/unit/test_episode_receipt_builder.py::test_every_committed_task_gets_exactly_one_receipt`
- `tests/unit/test_episode_receipt_builder.py::test_receipts_follow_membership_order_not_completion_order`
- `tests/unit/test_episode_receipt_builder.py::test_rebuilding_from_the_same_evidence_produces_the_same_receipts`
- `tests/unit/test_episode_receipt_builder.py::test_recorded_evidence_carries_no_secret`
- `tests/unit/test_receipt_set.py::test_editing_one_receipts_reward_breaks_the_set`
- `tests/unit/test_receipt_set.py::test_resealing_an_edited_receipt_still_breaks_the_set`
- `tests/unit/test_receipt_set.py::test_reordering_the_manifest_breaks_the_set`
- `tests/unit/test_receipt_set.py::test_a_receipt_from_another_run_cannot_join_the_set`
- `tests/unit/test_receipt_set.py::test_a_receipt_for_the_other_variant_cannot_join_the_set`
- `tests/unit/test_receipt_set.py::test_the_written_set_is_owner_readable_only`
- `tests/integration/test_receipts_from_recorded_evidence.py::test_receipts_are_built_from_a_run_directory_without_executing_anything`
- `tests/integration/test_receipts_from_recorded_evidence.py::test_both_recorded_variants_produce_independent_receipt_sets`
- `tests/integration/test_receipts_from_recorded_evidence.py::test_the_manifest_does_not_disturb_the_runs_own_receipt_directory`
- `tests/integration/test_fake_run.py::test_one_receipt_per_campaign_task_and_variant`

**Live evidence**

- Proof bundle payload digests, one per comparison: `sha256:b4389136…`, `sha256:bf772673…`, `sha256:cb496b91…`, `sha256:d0345d17…`, `sha256:4c7f46a2…`, `sha256:f4250b61…`. Each bundle carries 72 signed episode receipts, 36 per variant — counted in this refresh, **432 in total**, every one carrying its own payload digest and Ed25519 signature.
- Every one of the 432 reports `evidence_status: complete` and `score_status: valid`, and names its own task hash, trace digest, reward and the four artifact digests its episode produced (resolved config, raw traces, engine log, normalized episodes).
- `uv run techtree proof verify` on each of the six bundles reports 339 checks all passed, of which 84 are stored file digests and 225 are signatures.
- The name of `test_recorded_evidence_carries_no_secret` is older than what it now does: since decision 0036 nothing in this project inspects a string for credential shape, and that test fixes the *field set* the engine's normalizer may emit — a change that began carrying prompts, messages, task data or an endpoint into the projection would fail there. It is cited as a field-allowlist test, not as secret detection.

**Limitation.** Internal evidence. A receipt attests to what the local executor and Verifiers recorded for that episode. It is integrity evidence about the recorded bytes, not independent observation of the subject, and the subject's raw transcript is not part of it.

### claim-08 — Signed report

**Public wording.** The result is a locally signed Uplift receipt whose integrity a third party can check offline. The execution is participant-attested and has not been independently reproduced.

**Implementation**

- `src/techtree/crypto.py` — Ed25519 sign/verify over the ASCII digest string; no key storage
- `src/techtree/identity/service.py`, `src/techtree/identity/store.py`, `src/techtree/identity/models.py` — the local executor identity
- `src/techtree/models/base.py` — ObjectEnvelope (payload + digest + signature)
- `src/techtree/receipts/uplift.py` — build_uplift_report, proof_grade_for
- `src/techtree/receipts/bundle.py` — the signed bundle and its P1 conditions

**Automated test**

- `tests/unit/test_crypto.py::test_sign_and_verify_round_trip`
- `tests/unit/test_crypto.py::test_corrupt_signature_fails`
- `tests/unit/test_crypto.py::test_wrong_key_fails`
- `tests/unit/test_crypto.py::test_swapping_the_key_id_does_not_make_a_signature_valid`
- `tests/unit/test_crypto.py::test_signing_is_deterministic`
- `tests/unit/test_crypto.py::test_the_signed_message_is_the_ascii_digest_string`
- `tests/unit/test_crypto.py::test_no_module_outside_the_identity_layer_touches_private_key_material`
- `tests/unit/test_local_bundle_verify.py::test_a_removed_signature_breaks_the_proof`
- `tests/unit/test_local_bundle_verify.py::test_a_foreign_public_key_breaks_the_proof`
- `tests/unit/test_local_bundle_verify.py::test_a_bundle_whose_report_claims_p1_without_a_signature_fails`
- `tests/unit/test_local_bundle_verify.py::test_unsigned_receipts_withhold_the_grade`
- `tests/integration/test_local_sign_and_verify.py::test_every_receipt_travels_signed`
- `tests/integration/test_local_sign_and_verify.py::test_a_signed_run_reaches_p1_and_states_a_verdict`
- `tests/integration/test_local_sign_and_verify.py::test_the_private_key_is_nowhere_in_the_run_directory`
- `tests/unit/test_uplift_aggregation.py::test_a_signed_report_carries_the_verdict_and_p1`

**Live evidence**

- Each bundle carries the executor public key it was signed with and a `root_report_digest` equal to that run's own `report/uplift.json` file digest — checked in this refresh for all six (`b8094b55…`, `2736aa17…`, `8a9eb2ac…`, `6b830389…`, `bfa53e08…`, `067dd5e5…`), and each bundle payload commits to 83 artifacts.
- Two executor key ids across the six runs, not six: `sha256:df8995a3fc631843…` signed all four runs in the founder's own Techtree home (the three certification executions and the walkthrough), and `sha256:4522470900 3efd4e…` signed both WP11f runs from that journey's fresh home. A key belongs to a home, not to a run. **The previous edition said three distinct keys and that each home generated its own; the second half is right and the count is not, because these four runs shared one home.**
- All six report `proof_grade: P1`, and the verifier's own output states what P1 means: "integrity-bound, participant-attested local execution", alongside the standing warning that nobody else has run the comparison and no platform witnessed it.
- All 432 episode receipts, all six execution records and all six reports travel inside their bundles as signed envelopes; `techtree proof verify` checked 225 signatures in each bundle and every one passed.

**Limitation.** Participant-attested. The signing key is generated and held on the participant's own machine. A valid signature proves the bytes were not altered after the run; it never proves the run happened as described, and the execution has not been independently reproduced.

### claim-09 — Cost and timing are recorded honestly

**Public wording.** Every result carries what the comparison cost and how long it took, with where each figure came from.

**Implementation**

- `src/techtree/receipts/execution.py` — ComparisonExecutionRecord and the cost-provenance seam
- `src/techtree/verifiers/outputs.py` — normalized traces the token counts are summed from
- `src/techtree/presentation/build.py` — every cost figure reaches the payload with its own caveat

**Automated test**

- `tests/unit/test_comparison_execution_record.py::test_a_cost_figure_cannot_be_carried_without_a_provenance`
- `tests/unit/test_comparison_execution_record.py::test_the_weakest_provenance_is_the_one_that_claims_least`
- `tests/unit/test_comparison_execution_record.py::test_a_total_never_claims_more_than_its_weakest_half`
- `tests/unit/test_comparison_execution_record.py::test_a_run_with_no_price_feed_reports_an_unavailable_cost`
- `tests/unit/test_comparison_execution_record.py::test_a_variant_whose_traces_report_no_usage_says_unavailable`
- `tests/unit/test_comparison_execution_record.py::test_tokens_are_summed_from_the_normalized_traces`
- `tests/unit/test_comparison_execution_record.py::test_the_timings_are_the_ones_the_children_recorded`
- `tests/unit/test_comparison_execution_record.py::test_two_builds_of_one_execution_are_byte_identical`
- `tests/unit/test_comparison_execution_record.py::test_every_provenance_is_reachable_through_the_cost_seam`
- `tests/unit/test_local_bundle_verify.py::test_the_execution_record_travels_signed_and_committed_to`
- `tests/unit/test_local_bundle_verify.py::test_an_edited_execution_record_is_caught_by_its_digest`
- `tests/integration/test_local_sign_and_verify.py::test_a_real_runs_record_reports_no_cost_and_says_why`
- `tests/unit/test_presentation_build.py::test_every_cost_provenance_reaches_the_payload_with_its_own_caveat`
- `tests/contract/test_release_copy.py::test_a_worked_out_cost_never_reads_as_one_the_provider_billed`
- `tests/contract/test_release_copy.py::test_a_worked_out_cost_says_what_it_was_worked_out_from`
- `tests/contract/test_release_copy.py::test_a_cost_that_cannot_be_worked_out_names_what_is_missing`
- `tests/contract/test_release_copy.py::test_no_copy_promises_a_price_or_a_spending_cut_off`
- `tests/contract/test_release_copy.py::test_no_copy_promises_a_run_is_over_by_a_certain_time`

**Live evidence**

- Every comparison carries a signed ComparisonExecutionRecord inside its bundle (payload digests `sha256:afcbed2c…`, `sha256:7651023e…`, `sha256:4e8a89d4…`, `sha256:308ebdbd…`, `sha256:586fa0ab…`, `sha256:79e38387…`), and each one reports, for **both** variants, `cost_usd: null` with provenance `unavailable` and the detail "no cost figure was reported for this variant, and this build pins no price to compute one from". The product's own record claims nothing it was not told.
- What each record does carry, measured: per-variant `usage` with provenance `normalized_traces` (36 traces with usage out of 36, both sides, all six runs), model-call counts, elapsed seconds, start and finish instants, launch skew, overlap, argv digest, resolved-config digest, raw-trace digest, normalized-episodes digest and experiment-manifest digest. Example, certification #1: baseline 235 model calls / 525.58 s, candidate 75 model calls / 279.01 s, launch skew 1.61 ms, schedule `parallel_variants`, max_concurrent 2 per variant.
- The dollar figures in this document are worked out, not billed: recorded tokens at the rate card in `release/price-profile.json`. Recomputed here for all six runs, they reproduce the fingerprint's and the WP11f record's figures to the last digit.
- The one provider-reported cost anywhere in this lineage is the guided-revision host completion: USD 0.0441, read from the response's own usage block (see scope-02).

**Limitation.** Provider revision unavailable, and cost is not a billed figure. Cost and timing are attributed to a model alias, not to a pinned immutable provider revision, because the provider does not expose one (accepted v0.1 warning, decision 0007 R5). For the certified subject runs the product reports cost as unavailable and says why; every dollar figure in this document is derived from recorded tokens and a rate card recorded on 2026-08-20, and is only as current as that record. No public surface may state a price, a running total or a spending cut-off.

**Gaps (findings, not fixed here)**

- No spend ledger exists for the three certification executions or the walkthrough. The previous edition cited `certification-evidence/recert-0025/NOTES.md` for a programme total against a founder-raised cap; that ledger belongs to the superseded quiet window and there is no counterpart for these runs. What can be stated from the runs' own bytes is the worked-out figure per run. The WP11f legs are fully accounted for in `release/acceptance/onboarding-e2e.json` against a USD 1.50 authorisation.

### claim-10 — Data policy is committed and enforced

**Public wording.** One data policy is committed with the Climb and is acknowledged before anything runs. Techtree does not upload the participant's Episodes, Traces, receipts, proof bundles or Skill proposals. Model inference is still sent to the selected model provider under that provider's policies.

**Implementation**

- `src/techtree/models/data_policy.py` — DataPolicy, DataOwner, RawEpisodePolicy, DerivedArtifactPolicy, CandidateSkillPolicy, RevocationPolicy
- `src/techtree/models/campaign.py` — the campaign's required data_policy_digest
- `src/techtree/manifests/builder.py` — the policy digest is copied into both variants
- `src/techtree/runs/service.py` — the acknowledgement recorded at approval time

**Automated test**

- `tests/unit/test_data_policy.py::test_public_report_against_a_private_policy_is_rejected`
- `tests/unit/test_data_policy.py::test_published_trace_projection_against_a_private_policy_is_rejected`
- `tests/unit/test_data_policy.py::test_private_candidate_skill_against_a_requiring_policy_is_rejected`
- `tests/unit/test_data_policy.py::test_policy_cannot_permit_a_use_it_makes_impossible`
- `tests/unit/test_data_policy.py::test_acknowledgement_records_who_accepted_and_how`
- `tests/unit/test_data_policy.py::test_acknowledgement_rejects_an_invented_method`
- `tests/unit/test_data_policy.py::test_participant_owned_policy_rejects_an_account_reference`
- `tests/unit/test_campaign_models.py::test_campaign_requires_a_data_policy_digest`
- `tests/unit/test_campaign_models.py::test_a_campaign_pointing_at_another_data_policy_is_rejected`
- `tests/unit/test_manifest_builder.py::test_the_data_policy_digest_is_the_campaigns`
- `tests/contract/test_json_schemas.py::test_the_campaign_schema_requires_a_data_policy_digest`
- `tests/contract/test_protocol_golden_files.py::test_the_campaign_points_at_the_committed_data_policy`
- `tests/contract/test_release_copy.py::test_a_claim_that_nothing_is_sent_is_qualified_where_it_is_made`

**Live evidence**

- Data policy `sha256:6c532a43d595286a…` — recomputed in this refresh from src/techtree/resources/catalog/data-policies/hello-world-climb.json; the shipped Campaign commits to it, and it appears in every one of the six reports, every one of the six bundles, every `proof/data-policy.json` and all 432 episode receipts. The engine move did not touch it.
- The guided-revision comparison, which runs a derived Campaign, carries the same policy digest — the rights the source run was carried out under still govern the derived one, and its own draft record says so in plain words: "The data rights stated for this run are the ones the run it was prepared from was carried out under."
- Acknowledgement, read from each run's `request.json` in this refresh: the three certification executions record `policy_acknowledgement.method: explicit_cli_review`; the walkthrough and both WP11f runs record `host_agent_confirmation`. Every one names the same data_policy_digest and its own acknowledgement instant.
- The policy summary the participant had to accept is carried verbatim in the prepare record: "You own the candidate skill and everything this run produces… Uploading raw episodes to a server is prohibited. Training on raw episodes is prohibited…"
- `push: false` in the input configuration Techtree writes (`verifiers/<variant>/input.json`) and in the configuration the engine resolved (`verifiers/<variant>/run/configs/resolved/eval.json`) for every variant of every run — read in this refresh from the runs' own bytes.

**Limitation.** Fixed v0.1 policy. Exactly one participant-owned policy ships; it cannot be edited, negotiated or revoked through the product. push=false prevents the additional Verifiers-platform upload — it does not make inference local, and model calls still go to the selected provider under that provider's policies.

### claim-11 — Offline verification

**Public wording.** A third party can verify the integrity of the participant-attested proof bundle offline, without trusting a Techtree-hosted execution claim.

**Implementation**

- `src/techtree/receipts/verify.py` — LocalProofVerifier, verify_local_bundle, verify_report_envelope
- `src/techtree/receipts/bundle.py` — build_local_bundle, write_local_bundle, the P1 conditions
- `src/techtree/cli/commands/proof.py` — the `techtree proof verify` command (VERIFY_COMMAND = 'proof verify')

**Automated test**

- `tests/unit/test_local_bundle_verify.py::test_a_complete_proof_verifies_offline`
- `tests/unit/test_local_bundle_verify.py::test_an_edited_receipt_breaks_the_proof`
- `tests/unit/test_local_bundle_verify.py::test_an_edited_receipt_with_a_repaired_manifest_still_breaks_the_proof`
- `tests/unit/test_local_bundle_verify.py::test_an_edited_report_breaks_the_proof`
- `tests/unit/test_local_bundle_verify.py::test_an_edited_campaign_breaks_the_proof`
- `tests/unit/test_local_bundle_verify.py::test_an_edited_execution_record_is_caught_by_its_digest`
- `tests/unit/test_local_bundle_verify.py::test_a_missing_receipt_breaks_the_proof`
- `tests/unit/test_local_bundle_verify.py::test_an_execution_record_resigned_for_another_run_is_refused`
- `tests/unit/test_local_bundle_verify.py::test_verification_recomputes_the_aggregate_from_the_receipts`
- `tests/unit/test_local_bundle_verify.py::test_verification_reports_every_check_it_ran`
- `tests/unit/test_local_bundle_verify.py::test_a_verified_proof_still_says_what_it_does_not_prove`
- `tests/unit/test_local_bundle_verify.py::test_the_explanation_never_claims_independent_reproduction`
- `tests/integration/test_local_sign_and_verify.py::test_the_bundle_verifies_after_being_copied_somewhere_else`
- `tests/integration/test_local_sign_and_verify.py::test_the_bundle_verifies_from_the_bytes_the_run_wrote`
- `tests/integration/test_local_sign_and_verify.py::test_every_section_3_4_condition_is_established_by_the_stored_bytes`
- `tests/contract/test_release_copy.py::test_no_copy_claims_somebody_else_verified_the_run`
- `tests/contract/test_release_copy.py::test_the_honest_attestation_wording_is_still_allowed`

**Live evidence**

- This refresh ran `uv run techtree proof verify <run-dir>/proof` against all six bundles of this lineage, from the stored bytes, and each returned **verified, 339 checks, every one passed**: files and key present; 84/84 stored file digests; 18/18 linkage and control; 225/225 signatures; aggregate recomputation passed; 2/2 publication; 8/8 proof-grade conditions.
- The rendered result of each verification says, in the product's own words, "This proof verifies: 339 checks, all from the stored bytes, with nothing fetched", and carries the standing warning "No independent reproduction: nobody else has run this comparison, and no platform witnessed it."
- Bundle payload digests verified against: `sha256:b4389136…`, `sha256:bf772673…`, `sha256:cb496b91…`, `sha256:d0345d17…`, `sha256:4c7f46a2…`, `sha256:f4250b61…`.
- The WP11f journey verified both of its own bundles independently through the installed plugin (`plugin-proof-verify-1.json`, `plugin-proof-verify-2.json`) and recorded 339 checks, 0 failures, offline, on each.

**Limitation.** No honest-compute proof. Verification establishes internal consistency, signature validity and that nothing was altered after the run. It cannot establish that the computation was performed honestly, and the execution has not been independently reproduced.

**Gaps (findings, not fixed here)**

- The claim says a third party can verify offline, and the mechanism supports that. No third party has: every verification on record was run by this project's own workers, on the machine that holds the bundle, and no bundle of this lineage has been handed to anyone. The website publishes no bundle and nothing is uploaded, so there is at present no path by which a third party could obtain one. **Public copy that says another participant can verify or reproduce a result overstates this row and is named under Stop conditions.**

### claim-12 — Explicit approval before anything is spent

**Public wording.** Nothing runs and nothing is sent until a person explicitly approves it, on a named surface.

**Implementation**

- `src/techtree/runs/service.py` — the acceptance-surface table, _require_agreeing_approval, one run one approval
- `src/techtree/cli/commands/run.py`, `src/techtree/cli/commands/uplift.py` — the CLI review-and-approve surface
- `../techtree-plugin/approvals.py` — the host-agent approval surface
- `../techtree-plugin/tools/run.py`, `../techtree-plugin/services/proposal.py` — tools declared as human-confirmed

**Automated test**

- `tests/plugin/unit/test_approvals.py::test_the_plugin_issues_no_approval_of_its_own`
- `tests/plugin/unit/test_approvals.py::test_a_forged_confirmation_field_is_simply_ignored`
- `tests/plugin/unit/test_approvals.py::test_no_confirmation_indicator_is_invented`
- `tests/plugin/unit/test_approvals.py::test_a_documented_indicator_that_says_no_stops_the_call`
- `tests/plugin/unit/test_approvals.py::test_the_run_records_the_surface_the_person_actually_answered_on`
- `tests/plugin/unit/test_approvals.py::test_the_disclosure_says_every_thing_it_has_to_say`
- `tests/plugin/unit/test_approvals.py::test_the_disclosure_never_promises_a_result`
- `tests/plugin/integration/test_one_turn_revision.py::test_the_plugin_mints_no_approval_of_its_own`
- `tests/plugin/integration/test_one_turn_revision.py::test_a_proposal_prepares_a_comparison_and_starts_nothing`
- `tests/plugin/integration/test_one_turn_revision.py::test_the_tool_declares_itself_as_one_a_human_must_confirm`
- `tests/integration/test_run_start_idempotency.py::test_declaring_a_surface_without_approving_starts_nothing`
- `tests/integration/test_run_start_idempotency.py::test_a_person_approves_by_answering_yes`
- `tests/integration/test_replacement_run_prepare.py::test_the_cli_refuses_to_start_a_replacement_without_approval`
- `tests/unit/test_run_service.py::test_a_second_start_does_not_record_a_second_approval`
- `tests/unit/test_run_service.py::test_the_run_records_who_approved_it`
- `tests/integration/test_cli_flow.py::test_start_records_the_approval_and_who_gave_it`

**Live evidence**

- Each of the six comparisons records exactly **one** `run.approved` audit event in its own journal — counted in this refresh across all six `events.jsonl` files, always at sequence 1, immediately after `run.created` and before `worker.started` — naming the actor, the instant and the draft digest that was approved.
- **Both surfaces are now exercised on the shipped lineage.** The three certification executions record actor `operator_via_flag` and method `explicit_cli_review`. The founder walkthrough `run_b3e25a43…` and both WP11f runs record actor `human_via_hermes` and method `host_agent_confirmation` — a person answering on the host-agent surface, on the Campaign this release ships. This closes the gap the previous edition carried.
- The WP11f journey exercised the refusal path as well as the approval path: declining the pre-spend review exited 8 with code `policy_acceptance_required` and started nothing; replaying an already-approved draft returned the same run identifier and started nothing new; and the second comparison took its own separate approval rather than inheriting the first.
- The paid-run warning the approver had to pass is carried in each start surface: "This run evaluates the agent for real and spends model tokens on inference with prime. If that provider charges for tokens, what you pay is whatever it charges; a model you run yourself sends no bill."
- The WP11e-era P0 that told every user at the moment of approval that the run used a development fake executor is gone: the WP11f journey recorded `fake_executor: false` on the start surface and no such claim anywhere (`release/acceptance/onboarding-e2e.json`, ticket techtree-python-ce9, state fixed).

**Limitation.** Surface attestation. The run records which surface the answer was given on and which actor gave it, as attested by that surface. Nothing cryptographically binds a human being to the approval, and Techtree cannot tell an operator typing 'yes' from anything else that reaches that surface. In the three certification runs the approver was the certification operator using the CLI flag; the host-agent approvals were given by the founder and by an acceptance worker acting as operator, not by a first-time participant.

**Gaps (findings, not fixed here)**

- The host-agent surface does not hand back the field that makes an approval checkable. Finding wp11f-6 in `release/acceptance/onboarding-e2e.json`: the approval record the plugin returns carries `draft_digest: null`, because the plugin reads it from `data.draft_digest` on the start envelope and the CLI does not put one there. Read directly in this refresh: `evidence/plugin-climb-start-1.json` and `evidence/plugin-uplift-start.json` both show `approval.draft_digest: null`, while the run's own journal for the same runs carries `sha256:74c57bf0…` and `sha256:9593d5a6…`. The run record is intact; the record the host agent shows the person is not.

### claim-13 — An incomplete comparison fails closed

**Public wording.** If any part of the comparison did not complete, there is no result — the run fails and says why.

**Implementation**

- `src/techtree/runs/real.py` — RealVerifiersExecutor and its completion requirements
- `src/techtree/worker/execute.py`, `src/techtree/runs/executor.py` — the run-level execution path
- `src/techtree/receipts/uplift.py` — _require_reportable, aggregate_primary_result, build_uplift_report
- `src/techtree/receipts/set.py`, `src/techtree/receipts/episode.py` — episode-count and membership checks
- `src/techtree/verifiers/child.py` — the child-local supervisor, its deadline and its grace invariants

**Automated test**

- `tests/unit/test_episode_receipt_builder.py::test_a_missing_task_is_an_episode_count_mismatch`
- `tests/unit/test_receipt_set.py::test_a_set_missing_a_committed_task_is_refused`
- `tests/unit/test_receipt_set.py::test_a_short_set_is_an_episode_count_mismatch`
- `tests/unit/test_uplift_aggregation.py::test_a_missing_receipt_is_refused`
- `tests/unit/test_uplift_aggregation.py::test_one_errored_rollout_makes_the_whole_score_invalid`
- `tests/unit/test_uplift_aggregation.py::test_an_invalid_score_produces_no_report`
- `tests/unit/test_uplift_aggregation.py::test_an_uncontrolled_comparison_produces_no_report`
- `tests/unit/test_uplift_aggregation.py::test_an_empty_comparison_is_refused`
- `tests/integration/test_executor_selection.py::test_evidence_without_a_report_fails_the_run_and_names_the_evidence`
- `tests/unit/test_run_service.py::test_a_report_that_is_not_what_the_journal_named_is_refused`

**Live evidence**

- The supervisor invariants this row rests on are live in every run of this lineage: `verifiers/<variant>/supervision.json`, mode 0600, records the 3,600-second deadline, a 20-second supervisor grace, `reason: completed` and `escalated_to_sigkill: false` for all twelve variants of the six runs.
- Every run of this lineage completed. Read in this refresh from the trace files: 432 of 432 episodes stopped with `agent_completed`, none errored, and every one of the six reports carries `evidence: complete`, `score: valid`, `execution: completed`.
- The fail-closed behaviour itself is evidenced by the **superseded** lineage and is named as such. `run_ba3998e2a0d94126bc7426d0c6b32aab`, the deliberate worker-SIGKILL injection, is recorded in `release/orphan-bound-analysis.json` and still on disk under `certification-evidence/recert-0029-quiet-2026-08-20/inject-home/`: no report directory and no proof directory, both supervision records saying `parent_lost`, all four recorded subject container ids gone 0.545 s after the kill with none surviving, the whole tree down 1.081 s after the kill, `escalated_to_sigkill: false`, and a residual recorded provider cost of USD 0.0007.

**Limitation.** No Uplift receipt. A failed run yields no report and no proof bundle. The participant gets an honest failure and a preserved run record, but the provider spend already incurred is not recovered. A SIGKILLed worker additionally cannot record its own terminal state, so such a run stays at the phase it had reached rather than being marked failed.

**Gaps (findings, not fixed here)**

- **This row has no live evidence from the lineage this release ships.** Every run of this lineage succeeded. The kill injection and the two deadline failures the previous edition cited (`run_ba3998e2…`, `run_4fae4473…`, `run_37647dbe…`) all ran under the superseded Campaign `ad393bc0…`, and the fingerprint records that the injection was deliberately not repeated: what the orphan bound is computed from — the four enforced limits, the task count, the per-call sampling cap and the recorded prices — is byte-identical between the two Campaigns, and the teardown behaviour it evidenced lives in the CLI rather than in the engine that moved. That reasoning is sound and is the founder's ruling, but it is an argument that the old evidence still applies, not new evidence. The WP11f journey did not kill a worker either (`release/acceptance/onboarding-e2e.json`, ticket techtree-python-730, state "not retested").

## Scope rows (decision 0023 §4)

### scope-01 — Skill-bundle v1-vs-v2 comparison is supported when both bundles are supplied explicitly

**Public wording.** Explicit Skill-bundle v1-vs-v2 comparisons are supported when both bundles are supplied.

**Implementation**

- `src/techtree/skills/scanner.py` — whole-tree enumeration and per-file digests
- `src/techtree/skills/archive.py` — the deterministic, uncompressed Skill archive and its verification
- `src/techtree/skills/service.py` — preparing a Skill from a directory tree
- `src/techtree/uplift/derive.py` — deriving the replacement campaign and both replacement manifests
- `src/techtree/manifests/builder.py`, `src/techtree/verifiers/compiler.py` — per-file mounting of both bundles

**Automated test**

- `tests/integration/test_multi_file_skill.py::test_the_draft_holds_the_whole_tree`
- `tests/integration/test_multi_file_skill.py::test_the_run_stages_the_whole_tree`
- `tests/integration/test_multi_file_skill.py::test_the_mount_the_subject_reads_holds_the_whole_tree`
- `tests/integration/test_multi_file_skill.py::test_moving_a_file_out_of_its_directory_changes_the_skill`
- `tests/integration/test_multi_file_skill.py::test_the_scanner_reports_both_nested_files`
- `tests/unit/test_manifest_builder.py::test_a_replacement_campaign_builds_both_variants`
- `tests/unit/test_manifest_builder.py::test_a_skill_whose_root_digest_does_not_describe_its_files_is_refused`
- `tests/unit/test_manifest_builder.py::test_a_replacement_by_the_same_content_is_refused_at_construction`
- `tests/unit/test_skill_replacement_derivation.py::test_the_mutation_becomes_a_replacement_of_exactly_one_skill`
- `tests/unit/test_skill_replacement_derivation.py::test_the_baseline_carries_the_skill_that_was_evaluated`
- `tests/unit/test_observed_comparison.py::test_a_skill_replacement_is_controlled`
- `tests/unit/test_skill_archive.py::test_the_same_skill_produces_the_same_bytes_twice`
- `tests/unit/test_skill_archive.py::test_a_changed_member_digest_does_not_verify`

**Live evidence**

- `run_4584be6d8e1248ce9495a51ce2059fee` — the replacement comparison of this lineage, on derived Campaign `sha256:0f3cb0141feb0ee6…`, report `sha256:067dd5e5…`, bundle payload `sha256:f4250b61…`, 0.639 -> 0.667 (23/36 -> 24/36), 1 win / 0 losses / 35 ties, worked-out cost USD 0.0580, proof verifies 339/339.
- Parent Skill v1 tree `sha256:596d1368…` (SKILL.md `sha256:2aff2707…`, 1,496 bytes, 40 lines) versus candidate Skill v2 root `sha256:5e2e2f58…` (SKILL.md `sha256:4d94de88…`, 1,897 bytes, 49 lines, name `revision`, `parent_skill_digest sha256:596d1368…`, `source_kind: manual`, archive `sha256:edad1b7d…`, `included_files: ["SKILL.md"]`) — read in this refresh from the run's own `inputs/draft.json`, `inputs/skill/artifact.json` and the staged files themselves, and re-hashed from those files.
- The report's manifest comparison records exactly two entries, both on the same skill slot: the digest and the size. Nothing else differed, `controlled: true`, `violations: []`.
- The derivation is recorded rather than assumed: an uplift comparison cannot run the shipped Campaign verbatim because its baseline arm carries no Skill. This refresh flattened the derived Campaign against the shipped one and found it differs at exactly two pointers — `/agents/subject/harness/skills/0` (the baseline arm now mounts v1) and `/mutation_contract/kind` (`skill_replacement`). Budgets, execution contract, taskset, membership, model, sampling and runtime are byte-identical.
- Both bundles were supplied explicitly and staged separately: the run tree carries `inputs/baseline-skill/` and `inputs/skill/` as independent artifacts, each with its own `bundle.tar`, `artifact.json` and extracted files.

**Limitation.** The certified replacement run compared two single-file bundles. No paid run of any lineage has compared a multi-file bundle pair; full-tree hashing, per-file mounting, root-digest comparison and the exactly-one-component-changed check are covered by automated tests only. Also note this is the explicitly-supplied path, which is separate from what the guided improver can produce (see scope-02) — although in this lineage the same run serves as evidence for both, because the bundle that was supplied was the one the guided improver produced.

**Gaps (findings, not fixed here)**

- No live-evidence artifact exists for a multi-file bundle pair. Coverage for that case is `tests/integration/test_multi_file_skill.py` alone.

### scope-02 — Guided revision is single-SKILL.md in v0.1; the flow is certified and no measured uplift is claimed

**Public wording.** The guided Hello World revision revises the single SKILL.md. The flow is certified end to end: proposed, scanned, diffed, explicitly approved, evaluated and reported honestly. No copy states or implies that guided revision produced measured uplift. Guided revision ships as experimental (decision 0028).

**Implementation**

- `src/techtree/uplift/source.py` — VerifiedSourceSkill verifies every file of the tree but exposes only entrypoint_text to the host
- `src/techtree/skills/starter.py` — _stage_document stages a single SKILL.md
- `src/techtree/uplift/context.py`, `src/techtree/uplift/service.py` — the improvement context handed to the host model
- `../techtree-plugin/services/proposal.py`, `../techtree-plugin/llm.py` — exactly one host completion, no retry
- `../techtree-plugin/guards.py`, `../techtree-plugin/diff.py` — the structure, copied-case and narrative guards, and the diff shown before approval

**Automated test**

- `tests/unit/test_verified_source_skill.py::test_the_entrypoint_text_comes_back_with_what_it_was_verified_against`
- `tests/unit/test_verified_source_skill.py::test_the_entrypoint_is_the_entry_file_and_not_the_first_one`
- `tests/unit/test_verified_source_skill.py::test_an_edited_sibling_file_is_refused_too`
- `tests/unit/test_verified_source_skill.py::test_a_missing_entrypoint_is_refused`
- `tests/unit/test_improvement_context.py::test_the_context_pins_the_run_the_campaign_and_the_skill`
- `tests/unit/test_improvement_context.py::test_a_context_cannot_be_built_from_another_campaigns_report`
- `tests/plugin/contract/test_improvement_context.py::test_no_subject_reply_survived_into_the_context`
- `tests/plugin/contract/test_improvement_context.py::test_no_hidden_answer_or_grader_material_is_present`
- `tests/plugin/contract/test_improvement_context.py::test_no_credential_or_private_path_is_present`
- `tests/plugin/contract/test_improvement_context.py::test_one_planted_answer_would_be_caught`
- `tests/plugin/contract/test_one_generation_request.py::test_the_guided_proposal_makes_exactly_one_request`
- `tests/plugin/contract/test_one_generation_request.py::test_a_second_ask_is_refused_before_it_reaches_the_provider`
- `tests/plugin/contract/test_one_generation_request.py::test_an_unusable_answer_is_not_repaired_by_a_second_request`
- `tests/plugin/contract/test_one_generation_request.py::test_a_transport_failure_is_counted_and_not_retried`
- `tests/plugin/contract/test_improver_skill_contract.py::test_the_bundled_skill_satisfies_the_contract`
- `tests/plugin/contract/test_improver_skill_contract.py::test_the_bundled_skill_agrees_with_the_safety_envelope`
- `tests/plugin/contract/test_improver_skill_contract.py::test_the_bundled_skill_teaches_no_guard_trigger_phrase`
- `tests/plugin/integration/test_one_turn_revision.py::test_a_second_proposal_is_refused`
- `tests/plugin/integration/test_one_turn_revision.py::test_an_unusable_proposal_still_uses_the_turn`
- `tests/plugin/integration/test_one_turn_revision.py::test_the_diff_is_shown_with_the_policy_and_the_estimate`
- `tests/plugin/integration/test_one_turn_revision.py::test_the_second_run_starts_once_the_diff_and_policy_were_shown`
- `tests/plugin/unit/test_guards.py::test_a_whole_revised_skill_passes`
- `tests/plugin/unit/test_guards.py::test_a_patch_is_not_a_revision`
- `tests/plugin/unit/test_guards.py::test_a_revised_skill_quoting_one_member_is_refused`
- `tests/plugin/unit/test_guards.py::test_prose_listing_three_distinct_members_is_refused`
- `tests/contract/test_release_copy.py::test_no_copy_claims_an_exact_score`
- `tests/contract/test_release_copy.py::test_the_band_wording_is_still_allowed`

**Live evidence**

- **The guided revision completed end to end for the first time in this programme**, on 2026-08-27, through the real plugin path (`techtree_uplift_propose` on the installed plugin at commit `df5ead2b…`). One host completion on the frozen profile: model z-ai/glm-5.2, temperature 0, `max_completion_tokens` 32,768, strict `json_schema` structured output, **one** outbound generation request, zero repairs, zero retries, zero guards fired. Provider response id `a319c0b7b9bceb36-SJC`, finish reason `stop`, 5,112 prompt / 7,921 completion tokens, **provider-reported cost USD 0.0441**. Request digest `sha256:87bf0fd0…`, response digest `sha256:5b7f5b19…`.
- It produced Skill v2: SKILL.md `sha256:4d94de88…`, 1,897 bytes, 49 lines, tree root `sha256:5e2e2f58…`, parent `sha256:596d1368…`, one included file. The deterministic diff shown before approval is `sha256:151d921d…` — 14 lines added, 5 removed, 19 changed, `truncated: false` — and the change is procedural: reduce each position-weighted product modulo 97 incrementally and keep the running total reduced, rather than summing everything and reducing once at the end. The model stated its own confidence as `medium` and listed three expected tradeoffs, none of them a promised benefit.
- The proposal prepared a comparison and started nothing: `started: false`, `next_action.requires_user_confirmation: true`, with the reason "Nothing has run. Show the difference above, the data policy, and the declared maximum, and start only if the user agrees to this exact comparison." The second comparison then took its own separate approval.
- Evaluated under this lineage exactly once, in `run_4584be6d…`: 0.639 -> 0.667, 1 win / 0 losses / 35 ties.
- The improvement context handed to the host, read in this refresh from `improvement/context.json` of the source run: it pins `source_run_id`, `source_report_digest`, `campaign_spec_digest`, `data_policy_digest`, `parent_skill_digest` and `parent_skill_entrypoint_digest`; it carries 20 examples with public prompt, outcome category, reward and public metrics; and `subject_reply` is `null` in every one of them. Its `prohibited_material` list is hidden expected answers, hidden grader material, sealed task content, subject final replies, private environment values, unredacted local filesystem paths.
- One earlier host attempt was refused at the provider edge (HTTP 403, Cloudflare 1010) before any token was generated: `attempt_spent: false`, `tokens_generated: 0`, `cost_usd: 0.0`. The record names it a defect in the acceptance harness's own HTTP client, not in the product, and it was corrected by using the client stack this release pins.
- Deferred multi-file items stand (decision 0022 §2): `skills/starter.py` `_stage_document` fetches only a single SKILL.md, and `uplift/source.py` exposes only `entrypoint_text` to the host. The draft's `included_files` is `["SKILL.md"]`.

**Limitation.** **The flow is certified; the improvement is not, and this lineage strengthens the no-measured-uplift rule rather than weakening it.** The one measured change is +1 task, and that sits inside the run-to-run spread of the *unchanged* starter Skill measured under this very Campaign: six executions of an identical arm scored 23, 23, 24, 23, 23 and 23 of 36 — the three certification candidates, the walkthrough candidate, the WP11f first-comparison candidate, and the WP11f second-comparison baseline. Spread 23-24. A +1 cannot be distinguished from that. Disclosed for completeness: a different Skill v2 under the superseded lineage measured +1 once and 0.0 once. No measured-uplift claim is made or permitted, and none of these numbers may appear in public copy. The 0013 §4 demo target (>=32/36, >=6 task uplift) was not met; 0013 already designates that a calibrated aim rather than a guarantee. Release copy states the calibrated 20-27/36 band, never an exact score. Per decision 0028 the feature ships labelled experimental, with no published reliability rate. In v0.1 the improver can only edit the entrypoint, so auxiliary files are always inherited byte-identical from the parent Skill; no copy may claim the guided improver revises multi-file bundles.

**Gaps (findings, not fixed here)**

- The proposal the participant received was missing the fields that make it auditable. Finding wp11f-5: unless the caller passes `channel: "terminal"`, every plugin answer comes back in the bounded chat form, Hermes documents no field the plugin can read (`DOCUMENTED_CHANNEL_KEYS` is empty), and the operator Skill never mentions the argument. Read directly in this refresh from `evidence/plugin-uplift-propose.json`: `request_accounting: null` and `scanner: null` on the live proposal. The one-request accounting and the scanner verdict exist — they are in the journey's own host-call record — but they were not in the answer the agent and the person actually saw.
- The guided introduction does not survive a restart. Finding wp11f-4: the demo session lives only in the memory of the Hermes process that created it, the first comparison takes about eleven minutes, and the pinned guide instructs a restart during onboarding. The run survives and recovers by identifier exactly as the contract requires, but `techtree_uplift_propose` then refuses with `demo_session_not_found` and carries no repair, and the second half of the introduction becomes unreachable. Reproduced live.

## Extension rows — public copy claims beyond the 13

The contract says to extend if public copy claims more, and its stop condition is any public claim with no implementation row. The authoritative v0.1 description (spec §18, adopted by decision 0013 §1) makes four claims the thirteen required rows do not cover on their own. They are added here so the stop condition does not fire on the product statement. Two website claims that go beyond even these are named under Stop conditions rather than given rows, because they are overclaims to withdraw rather than features to evidence.

### ext-01 — One pinned plugin installs and verifies Techtree

**Public wording.** A person installs one pinned Hermes plugin; with explicit approval it installs and verifies Techtree. No Techtree account is required.

**Implementation**

- `../techtree-plugin/bootstrap.py` — the single-use install plan and its refusals
- `../techtree-plugin/release.py`, `../techtree-plugin/release-core.json` — the embedded ReleaseCore
- `src/techtree/release/bootstrap.py`, `src/techtree/release/checks.py`, `src/techtree/release/document.py`
- `src/techtree/cli/commands/setup.py`, `src/techtree/doctor/checks.py`

**Automated test**

- `tests/plugin/unit/test_bootstrap.py::test_a_missing_cli_produces_one_exact_plan`
- `tests/plugin/unit/test_bootstrap.py::test_the_plan_names_only_the_release_version`
- `tests/plugin/unit/test_bootstrap.py::test_the_plan_installs_on_a_python_this_release_supports`
- `tests/plugin/unit/test_bootstrap.py::test_no_tool_argument_can_loosen_what_is_installed`
- `tests/plugin/unit/test_bootstrap.py::test_a_plan_is_single_use`
- `tests/plugin/unit/test_bootstrap.py::test_installation_goes_through_the_hosts_own_terminal_approval`
- `tests/plugin/unit/test_bootstrap.py::test_an_installed_release_that_matches_verifies`
- `tests/plugin/unit/test_bootstrap.py::test_an_installed_release_that_differs_is_rejected`
- `tests/plugin/unit/test_release.py::test_a_rewritten_release_file_is_refused`
- `tests/plugin/contract/test_plugin_doctor.py::test_this_build_passes_its_own_doctor`
- `tests/plugin/contract/test_plugin_doctor.py::test_the_runtime_imports_only_the_standard_library`
- `tests/plugin/contract/test_readme_release_truth.py::test_installation_is_routed_through_the_exact_pinned_guide`
- `tests/unit/test_release_bootstrap.py::test_a_wrapper_that_names_this_release_verifies`
- `tests/unit/test_release_bootstrap.py::test_a_wrapper_naming_another_starter_skill_fails_alone`
- `tests/unit/test_release_bootstrap.py::test_an_install_command_that_does_not_pin_the_version_fails_alone`
- `tests/unit/test_release_bootstrap.py::test_an_install_command_that_does_not_pin_the_interpreter_fails_alone`
- `tests/unit/test_release_checks.py::test_a_recut_campaign_fails_only_the_harness_check`
- `tests/contract/test_release_artifacts.py::test_the_committed_artifacts_are_the_ones_this_tree_produces`
- `tests/contract/test_release_artifacts.py::test_this_build_carries_the_release_it_is_published_as`
- `tests/contract/test_release_artifacts.py::test_both_founder_skill_digests_are_bound_under_their_own_semantics`
- `tests/contract/test_release_copy.py::test_no_copy_says_no_account_is_required`
- `tests/contract/test_release_copy.py::test_the_techtree_scoped_account_claim_is_still_allowed`
- `tests/contract/test_supported_python_agrees.py::test_the_doctor_reports_the_range_the_package_declares`

**Live evidence**

- ReleaseCore `sha256:bef3b9d4c987209c0fb580ed5eb349c096dca328efd7b0867f5a04d7bb763db4` — recomputed in this refresh and byte-identical in techtree-python/release/release-core.json, src/techtree/resources/release/release-core.json and ../techtree-plugin/release-core.json. Every field is concrete.
- **The whole install path was walked end to end from a fresh home on 2026-08-27** (`release/acceptance/onboarding-e2e.json`, contract wp11f): fresh HOME, HERMES_HOME, UV_TOOL_DIR, UV_TOOL_BIN_DIR, XDG_DATA_HOME and XDG_STATE_HOME under a scratchpad, uv 0.12.5, Docker 29.7.2, Hermes host 0.20.5, CPython 3.12.13 pinned by the plugin's own `--python 3.12`.
- Nothing installed without a person answering for it: the plugin install was gated on "Install anyway? Only continue if you trust the source. [y/N]" and "Enable 'techtree' now? [y/N]", a non-interactive install was BLOCKED with exit 1 and nothing installed, `--force` was never used, and a replayed install plan was refused with "that installation plan was not offered by this session".
- The installed plugin is the pinned one: commit `df5ead2b38316a8def7837ae0bedfe8c1d5c64a4`, detached head, worktree clean, install metadata pinned, enabled in config, and its ReleaseCore byte-identical to the installed CLI's. The plan argv is exactly `uv tool install --python 3.12 techtree==0.1.0`, `requires_confirmation: true`, single-use, expiring in fifteen minutes and looked up by opaque identifier so the command that ran is the command that was offered.
- Verification after install, from that home: `techtree release verify` 12 checks, ok, 9 passed / 3 skipped; `techtree doctor` for the Climb with Hermes on PATH 14 checks, 14 passed; `techtree doctor` for evaluation 11 checks, 9 passed / 1 warned / 1 skipped. The `hermes_plugin` check ran and passed for the first time in a Techtree acceptance.
- `release/fresh-install-report.json` — verdict PASS on the published install command with the interpreter pinned, from a throwaway home, on the candidate wheel `techtree-0.1.0-py3-none-any.whl` `sha256:e486b3ea…` built from commit `5d793b69…`.
- `release/wheel-inspection.json` — verdict PASS; the packaged lineage inside the wheel is Campaign `ebf029ab…`, Climb `a3a5e9c5…`, catalog `10a7fcc5…`, engine `29b1bbb8…`, ReleaseCore `bef3b9d4…`, improver `d5a381be…`, with the enforced budgets 44 / 900,000 / 16,000 / USD 2.50, and the build-provenance stamp naming commit `5d793b69…`.
- `release/plugin-release-candidate.json` — plugin commit `df5ead2b…`, worktree clean, plugin doctor passed (10 checks, all ok), carrying ReleaseCore `sha256:bef3b9d4…` and naming the same wheel digest.

**Limitation.** Not yet installed from published coordinates. `github.com/regents-ai/techtree-hermes` answers 404 and nothing is published to an index; `techtree.sh/start` is live but declares itself a placeholder and publishes a 40-zero commit and a version called `0.0.0-placeholder`. Decision 0028 §8 keeps repositories, tags and install coordinates private until the founder's Gate-2 phrase, and the public-coordinate repeat is WP11-postpublish. A Prime or provider account, an API credential and network access are still needed for inference, installation and image retrieval — only a Techtree account is not. One recorded install observation stands: left to choose for itself, uv built the tool environment on Python 3.14.7, which the package's own metadata (`Requires-Python: <3.14,>=3.12`) excludes; the published command pins the interpreter (decision 0034) and the CLI's health check refuses an unsupported interpreter rather than passing silently.

**Gaps (findings, not fixed here)**

- **The one document a Hermes agent is told to load before it touches any techtree_ tool says this build cannot do the journey.** Finding wp11f-1, priority P0, marked `blocks_gate_2: true`. The operator Skill's "What this build cannot do yet" section states unconditionally that Hello World stops before preparing a comparison because the starter Skill has not been chosen for this release, and that proposing a revision stops for the same reason; its troubleshooting reference says the release coordinates have not been chosen, that it will not install Techtree, that it cannot prepare the guided introduction, and that there is nothing to fix locally. All of that is false of this candidate: both founder Skills are pinned by digest, the CLI installed, the introduction prepared, and both comparisons ran. An agent following its instructions faithfully tells the user the journey is impossible. The copy contract missed it because nothing encodes "a claim about what this build cannot do must match whether the release has chosen its founder Skills".
- **The guide and the plugin README both promise the wrong install-time scan result.** Finding wp11f-2. Both tell the user in advance that Hermes' scan comes back at caution with "five findings in three families" and enumerate all five. The scan reports six, in four families; Hermes' own decision line, read from the journey's captured terminal, says `Blocked (community source + caution verdict, 6 findings)`. The sixth is a HIGH privilege-escalation finding on `skills/operator/references/questions.md` — the very document that explains the five. Verified in this refresh at `../techtree-ash/lib/techtree_web/install_components.ex:251`, `../techtree-plugin/README.md:130`, `../techtree-ash/lib/techtree_web/live/docs_live.ex:663` and `../techtree-plugin/skills/operator/references/questions.md:148`.
- The published install command on the website still omits the interpreter pin. Finding wp11f-7: `techtree.sh/start` publishes `uv tool install techtree==0.0.0-placeholder` with no `--python`, while the same page's prose promises "the installer provides its own Python 3.12, whatever this machine has" (`../techtree-ash/lib/techtree_web/install_components.ex:159`). Only the plugin's generated plan actually names it. Recorded in the WP11e ticket register as techtree-python-vom, state "fixed in the plugin, still wrong on the website".
- `dist/` carries no `.sha256` sidecar beside the wheel, so a participant has nothing local to check a download against; the digest lives only in `release/plugin-release-candidate.json` and `release/fresh-install-report.json` (finding wp11f-11).
- The published plugin install command ends in `--enable`, which pre-answers one of the two questions a user would otherwise be asked. The install-anyway approval still fires, so no stop condition is met (finding wp11f-12).
- The engine-verified state can never be reached. Finding wp11f-3: `techtree setup` and `techtree engine verify` both report the engine installed and verified, but a Climb's compatibility status is derived by a class that can only ever answer `not_installed` or `installed_unverified` (`src/techtree/catalog/service.py`). So `climb list`, `climb show`, `climb inspect` and `demo prepare` warn "The evaluation engine is installed but has not been checked since" forever and offer "Check that the installed evaluation engine is intact" (`src/techtree/cli/commands/climb.py:793`) as a next step the user can never clear, on the main onboarding surface. An agent following next steps never arrives at Hello World.

### ext-02 — The result is shown deterministically and the explanation is guarded

**Public wording.** The result is shown through deterministic Rich or compact output and a guarded founder-supplied explanation Skill. It states the band, never an exact score, and it always states its own limits.

**Implementation**

- `src/techtree/presentation/build.py` — the payload built from the verified report; the proof grade is read, never hardcoded
- `src/techtree/presentation/rich.py`, `src/techtree/presentation/compact.py` — the two renderings
- `src/techtree/presentation/sanitize.py` — the payload-shape and free-text rules (no credential-shape inspection since decision 0036)
- `../techtree-plugin/narrative.py`, `../techtree-plugin/guards.py`, `../techtree-plugin/services/presentation.py`

**Automated test**

- `tests/unit/test_presentation_build.py::test_the_same_report_builds_the_same_bytes`
- `tests/unit/test_presentation_build.py::test_every_result_states_its_standing_limits`
- `tests/unit/test_presentation_build.py::test_the_payload_copies_the_verdict_rather_than_deciding_one`
- `tests/unit/test_presentation_build.py::test_a_verified_proof_says_it_was_checked_offline`
- `tests/unit/test_presentation_build.py::test_an_unchecked_proof_is_not_a_verified_one`
- `tests/unit/test_presentation_build.py::test_a_controlled_comparison_with_warnings_says_so_plainly`
- `tests/unit/test_presentation_build.py::test_both_channels_say_what_the_receipt_is_worth_and_how_to_check_it`
- `tests/unit/test_presentation_render.py::test_the_same_payload_renders_the_same_bytes`
- `tests/unit/test_presentation_render.py::test_the_compact_rendering_keeps_every_qualification`
- `tests/unit/test_presentation_render.py::test_a_result_whose_proof_failed_says_so_before_the_numbers`
- `tests/unit/test_presentation_sanitize.py::test_a_payload_carrying_an_escape_sequence_is_refused`
- `tests/unit/test_presentation_sanitize.py::test_a_payload_naming_a_private_path_is_refused`
- `tests/unit/test_presentation_sanitize.py::test_an_error_summary_drops_the_traceback`
- `tests/unit/test_errors.py::test_a_memory_address_is_stabilized`
- `tests/plugin/unit/test_guards.py::test_a_narrative_may_not_restate_a_canonical_value`
- `tests/plugin/unit/test_guards.py::test_a_narrative_embedding_a_digest_is_refused`
- `tests/plugin/unit/test_guards.py::test_a_narrative_may_not_claim_what_is_not_true_of_a_local_run`
- `tests/plugin/unit/test_guards.py::test_saying_it_was_not_reproduced_is_fine`
- `tests/plugin/unit/test_guards.py::test_escape_codes_are_refused`
- `tests/contract/test_release_copy.py::test_no_copy_claims_somebody_else_verified_the_run`
- `tests/contract/test_release_copy.py::test_no_copy_calls_the_subject_the_readers_own_model`
- `tests/contract/test_release_copy.py::test_no_copy_frames_the_result_as_a_benchmark_that_was_passed`
- `tests/contract/test_release_copy.py::test_the_result_says_what_it_does_not_establish_in_the_lines_that_lead`
- `tests/contract/test_release_copy.py::test_a_surface_that_says_what_this_release_is_carries_the_frame`
- `tests/contract/test_release_copy.py::test_the_frame_guard_catches_what_it_is_for`

**Live evidence**

- The proof grade travels in the report and is read from it: all six reports of this lineage carry `proof_grade: P1`, and the verification this refresh ran renders the grade's meaning from the verified report — "P1 means integrity-bound, participant-attested local execution" — together with the standing no-independent-reproduction warning, rather than from any label attached to a comparison.
- Each report also carries `publication_eligible: false` and `statuses.publication: not_requested`, and each verification reports the publication checks 2/2 passed: "Not published: publication was never requested, nothing was uploaded, and this report is not publication eligible."
- The copy guards are executable and were run in this refresh as part of `tests/contract` (465 passed), including the band, exact-score, account, attestation, own-model, benchmark, price, clock, publication-terms and — new since decision 0035 — the proof-of-concept frame rules.
- The narrative guards did not fire on the one live guided revision of this lineage, and the two WP11e guard defects that had blocked earlier attempts (techtree-python-5f6, techtree-python-0mx) did not fire either (`release/acceptance/onboarding-e2e.json`, `guards_fired: 0`).

**Limitation.** The explanation Skill is guarded, not verified. The guards refuse numbers, digests, commands, escape codes and any claim untrue of a local run; they cannot establish that the remaining prose is a good explanation, and since decision 0036 they no longer refuse anything for looking like a credential. The deterministic guard surface has been narrowed since the first certification, so the guarantee is the current rule set, not the widest one that ever existed. The subject model is a pinned model the Campaign chooses (qwen/qwen3.7-flash), not the reader's own model, and it is distinct from the host operator model that writes the narrative.

**Gaps (findings, not fixed here)**

- The presentation layer no longer refuses a payload for carrying credential-shaped text, and the test that asserted it did is gone. `src/techtree/presentation/sanitize.py` now says so in its own words: "Nothing here inspects a string for credential-shaped text. Decision 0036 removed that from the whole project." What remains is the payload's shape (no field exists for a hidden answer, grader source or a subject reply), plus escape-sequence, control-character, private-path and traceback rules. The previous edition cited `test_a_payload_carrying_a_credential_is_refused`; that test no longer exists and is not replaced.
- The copy contract catches forbidden phrases, not false predictions. Every guard in `tests/contract/test_release_copy.py` scans for wording that must not appear or must appear; none compares a claim about machine behaviour against the machine. That is why the five-versus-six scan count (wp11f-2), the unreachable engine-verified state (wp11f-3) and the "nothing is lost when it ends" reassurance (wp11f-4) all passed the guards while being wrong.

### ext-03 — The proposed Skill v2 is shown and scanned before approval

**Public wording.** Techtree shows the proposed Skill v2 and scans it before the participant is asked to approve it.

**Implementation**

- `src/techtree/skills/scanner.py` — whole-tree enumeration, media types, per-file digests, shape refusals
- `src/techtree/skills/policy.py` — the frozen v0.1 instruction-Skill policy (suffixes, file count, file and total size, entrypoint, symlinks, hidden files)
- `../techtree-plugin/diff.py` — the deterministic diff shown to the participant
- `../techtree-plugin/services/proposal.py` — scan, snapshot, diff, then approval

**Automated test**

- `tests/unit/test_skill_scanner.py::test_default_policy_matches_the_v01_instruction_skill_rules`
- `tests/unit/test_skill_scanner.py::test_policy_is_frozen`
- `tests/unit/test_skill_scanner.py::test_scanned_files_carry_size_media_type_and_content_digest`
- `tests/unit/test_skill_scanner.py::test_scanning_the_same_content_twice_gives_the_same_answer`
- `tests/unit/test_skill_scanner.py::test_binary_content_under_a_text_suffix_is_refused`
- `tests/unit/test_skill_scanner.py::test_external_symlink_is_refused`
- `tests/unit/test_skill_scanner.py::test_symlinked_directory_is_refused`
- `tests/unit/test_skill_scanner.py::test_dot_env_is_refused_as_hidden`
- `tests/unit/test_skill_scanner.py::test_oversized_file_is_refused`
- `tests/unit/test_skill_scanner.py::test_too_many_files_is_refused`
- `tests/unit/test_skill_scanner.py::test_paths_differing_only_by_case_are_refused`
- `tests/unit/test_skill_scanner.py::test_missing_entrypoint_is_refused`
- `tests/plugin/integration/test_one_turn_revision.py::test_the_diff_is_shown_with_the_policy_and_the_estimate`
- `tests/plugin/integration/test_one_turn_revision.py::test_the_plugin_keeps_no_copy_of_the_proposed_skill`
- `tests/plugin/integration/test_one_turn_revision.py::test_the_approved_call_does_exactly_what_was_described`

**Live evidence**

- **The scan-and-diff evidence is now on the shipped lineage, not on a superseded one.** The proposal that produced the Skill this lineage evaluated was made on 2026-08-27 through the installed plugin and diffed before approval: `evidence/plugin-uplift-propose.json` carries the full unified diff and its digest `sha256:151d921d…` (14 added, 5 removed, 19 changed, `truncated: false`), the baseline skill digest `sha256:596d1368…`, the candidate `sha256:5e2e2f58…`, the data policy digest, the campaign maximum USD 2.50, the estimated 72 episodes, and `started: false`.
- The Skill passed Techtree's own scanner and the plugin's guards: `guards_fired: 0`, and the WP11e scanner defect that had blocked an ordinary sentence about tokens (techtree-python-0mx) did not fire. The draft Techtree then created records the scanned tree: `included_files: ["SKILL.md"]`, one file of 1,897 bytes, media type text/markdown, digest `sha256:4d94de88…`, archive `sha256:edad1b7d…`.
- The next action offered was `start_second_comparison`, `requires_user_confirmation: true`, with the reason naming the diff, the policy and the declared maximum — the proposal prepared a comparison and started nothing.
- The superseded-lineage proposal the previous edition cited (`release/acceptance/terminal-e2e.json`, host call `a2e008cb1b5e138a-SJC`, on ReleaseCore `90cd8ad6…`, engine `874cbae0…`) is not carried. It is named here only so nothing cites it.

**Limitation.** Mechanical scan only, and narrower than it was. The scanner checks structure, media types, per-file and total size, file count, entrypoint presence, hidden and symlinked paths, case-colliding paths and non-text bytes. **It no longer checks for credential shapes**: decision 0036 deleted the secret rule table outright, and with it the whole findings mechanism, so a Skill can no longer be refused for containing text that looks like a key. It never judged meaning and still does not. The copied-task-material check is not the scanner's — it is the plugin's copied-case guard in `../techtree-plugin/guards.py`, and the previous edition attributed it to the scanner. Decision 0023 §5 rules out an LLM-based semantic Skill scanner in v0.1.

**Gaps (findings, not fixed here)**

- **The scanner's verdict was not in the answer the person saw.** `evidence/plugin-uplift-propose.json` carries `scanner: null`, for the same reason as the missing request accounting: the plugin returned the bounded chat-shaped form because no caller passed `channel: "terminal"` (finding wp11f-5). The scan happened — Techtree's own scanner runs inside `uplift propose` and the draft it produced is in the run tree — but the claim as publicly worded is that Techtree *shows* the scan, and on this live path it did not.
- The public claim that a proposed Skill is checked for credentials no longer holds anywhere, and one shipped surface still implies it. The founder-frozen improver Skill (`../techtree-plugin/skills/skill-improver/SKILL.md`) still lists "No secret-like values." among the requirements on `revised_skill_markdown`, in a list whose other entries (non-empty, no NUL characters, within the size limit) are all enforced. Nothing enforces that one. The CLI's own improvement context has already adopted the honest wording — "The revision must not contain credentials, keys, tokens, or absolute local paths. Nothing checks for them, so writing one in puts it in the record" — read in this refresh from a live run's `improvement/context.json`.

### ext-04 — Nothing is uploaded to the website

**Public wording.** Techtree does not upload the participant's Episodes, Traces, receipts, proof bundles or Skill proposals. Model inference is still sent to the selected model provider under that provider's policies.

**Implementation**

- `src/techtree/verifiers/config.py`, `src/techtree/verifiers/child.py` — push disabled at both the file and command-line layers (PUSH_DISABLED_FLAG)
- `src/techtree/verifiers/verify.py` — the push check over the resolved configuration
- `src/techtree/presentation/sanitize.py`, `src/techtree/errors.py` — what may appear in a rendering, and the bounded error projection
- `../techtree-ash/lib/techtree_web/method_surface.ex` — the website's read-only method surface

**Automated test**

- `tests/unit/test_verifiers_verify.py::test_a_resolved_config_that_would_upload_fails_the_push_check`
- `tests/unit/test_verifiers_verify.py::test_the_upload_is_also_disabled_on_the_command_line`
- `tests/unit/test_verifiers_child.py::test_the_upload_is_disabled_on_the_command_line`
- `tests/preflight/test_verifiers_eval_contract.py::test_the_upload_path_is_never_reached_when_push_is_off`
- `tests/preflight/test_verifiers_eval_contract.py::test_the_upload_probe_sees_the_path_when_push_is_on`
- `tests/preflight/test_verifiers_eval_contract.py::test_the_command_line_flag_overrides_an_upload_in_the_file`
- `tests/contract/test_release_copy.py::test_a_claim_that_nothing_is_sent_is_qualified_where_it_is_made`
- `tests/contract/test_release_copy.py::test_no_copy_claims_the_work_is_local`
- `../techtree-ash/test/techtree_web/router_test.exs::"every route is a read"`
- `../techtree-ash/test/techtree_web/router_test.exs::"no submission, artifact, proof, run, or login route exists"`
- `../techtree-ash/test/techtree_web/router_test.exs::"a published address answers a mutating method with 405, not 404"`
- `../techtree-ash/test/techtree_web/endpoint_test.exs::"a file in a multipart body is never read into a parameter"`
- `tests/plugin/contract/test_plugin_doctor.py::test_the_runtime_cannot_open_a_connection`
- `tests/plugin/contract/test_plugin_doctor.py::test_no_relay_dependency_exists`

**Live evidence**

- The three-method no-upload proof the release requires was executed under contract wp11g: the static route audit, the instrumented application-level method log (`release/network-method-log.json`) and the end-to-end destination capture (`release/destination-capture.json`), all recorded 2026-08-23 and summarised in `release/security-review.json`.
- The product made **one** request to techtree.sh across its whole non-paid command surface, and its method was GET — a read of a content-addressed object. Zero unexpected destinations were observed across all three legs; every non-loopback peer seen belongs to the expected list. The instrument was proved alive by a deliberate loopback GET that it recorded.
- In the runs themselves: `push: false` in the input configuration Techtree writes (`verifiers/<variant>/input.json`) and in the configuration the engine resolved and ran under (`verifiers/<variant>/run/configs/resolved/eval.json`), for every variant of all six runs — read in this refresh from the runs' own bytes.
- `--no-push` and `--no-serve` are on the argv the child is given, in `src/techtree/verifiers/child.py`, and the pre-run validation carries the same flags: the dry-run `command.log` of every variant records the full argv verbatim, including `--no-push`. A flag on argv overrides whatever the file says, so the two layers agree by construction.
- The proof bundles themselves record the negative: `publication_eligible: false`, `statuses.publication: not_requested`, and the verifier's publication checks passing 2/2 on all six.
- The WP11f journey found no upload on the whole install-and-run path: nothing was published, nothing entered anywhere, and the prepare surface of the guided revision says so in the participant's own warning text — "This comparison is local. No Climb wraps it, nothing is entered anywhere, nothing is published, and nothing is uploaded. Model inference still goes to the model provider you configured, under that provider's policies."

**Limitation.** The claim is about the Techtree website and the Verifiers platform, not about the network. Model inference goes to the selected provider under that provider's policies, and installation and container image retrieval need network access. The destination capture states its own limit: the sampler is a poll rather than a capture, so it supports "this peer was never observed" and not "no byte ever left"; it is the static audit that establishes there is no upload code path to exercise.

**Gaps (findings, not fixed here)**

- The real run's argv is committed by digest only. Each run stores `argv_digest` for both children and the verbatim argv only for the dry-run leg (`verifiers/<variant>/dry-run/command.log`). So `--no-push` on the *evaluation* invocation is established from the code that builds the argv plus `push: false` in the configuration the engine resolved, not from a verbatim record in the run tree. The previous edition read `--no-push` "on the argv of every eval invocation" out of `command.log`; that file covers the dry run.
- The no-upload evidence predates decision 0036 by three days and has not been re-run since. `release/security-review.json` still carries a `secrets_scrubber` section, and `release/security-review.md` still reports "Seven of seven redact" over adversarial secret cases, for a mechanism that no longer exists. `release/public-visibility-review.md` cites `tests/fixtures/skills/invalid-secret/notes.md` and a "secret-detection rule table" in `src/techtree/skills/scanner.py`; this refresh confirmed neither exists. The network findings those documents record are unaffected by 0036, but the documents need a dated supersession note before they travel in a Gate-2 packet.

## Summary table

| # | Claim | Implementation (lead module) | Automated test (lead) | Live evidence (lead) | Limitation (short) | Gap |
|---|---|---|---|---|---|---|
| claim-01 | Campaign immutable | `src/techtree/models/base.py` | `tests/unit/test_canonical.py::test_protocol_models_are_frozen` | Campaign sha256:ebf029ab, in every report and all 432 receipts | 'Campaign' is an internal protocol concept; a participant never names one | no |
| claim-02 | Same tasks on both sides | `src/techtree/models/validation.py` | `tests/unit/test_taskset_membership_logic.py::test_the_membership_digest_is_the_digest_of_the_named_ordered_object` | Membership sha256:56f697fb, unchanged across the engine move, in six proof bundles | Fixed membership: one 36-task selection, no sampling or rotation | no |
| claim-03 | Taskset validated before it is used | `src/techtree/models/validation.py` | `tests/integration/test_taskset_validation.py::test_every_task_passes_gold_and_setup` | Validation receipt sha256:4944bd71, hashed out of six proof bundles, validator b2e4e815 | Mechanical only; the wrong-answer control is a test, not a receipt check | no |
| claim-04 | Neutral baseline | `src/techtree/manifests/builder.py` | `tests/unit/test_manifest_builder.py::test_the_baseline_preserves_the_campaign_and_carries_no_skill` | Baseline 0/36 in all five insertion comparisons of this lineage | Toy task | no |
| claim-05 | Clean subjects | `src/techtree/verifiers/config.py` | `tests/unit/test_verifiers_config.py::test_a_runtime_other_than_docker_cannot_be_named` | 432 receipts, all naming resolved image sha256:90744cff | Local executor | yes |
| claim-06 | Only the Skill changed | `src/techtree/manifests/compare.py` | `tests/unit/test_observed_comparison.py::test_an_unauthorized_observed_difference_is_invalid` | Six reports, controlled true, zero violations, one allowed difference each | Known derived description delta, plus one accepted warning | yes |
| claim-07 | Per-task receipts | `src/techtree/receipts/episode.py` | `tests/unit/test_episode_receipt_builder.py::test_every_committed_task_gets_exactly_one_receipt` | Six bundles, 72 signed receipts each, 432 in all | Internal evidence | no |
| claim-08 | Signed report | `src/techtree/crypto.py` | `tests/unit/test_crypto.py::test_sign_and_verify_round_trip` | Report digests and executor public keys in each bundle; two keys, two homes | Participant-attested | no |
| claim-09 | Cost and timing are recorded honestly | `src/techtree/receipts/execution.py` | `tests/unit/test_comparison_execution_record.py::test_a_cost_figure_cannot_be_carried_without_a_provenance` | Six signed execution records, cost provenance unavailable on both sides of each | Provider revision unavailable; cost is worked out, never billed | yes |
| claim-10 | Data policy is committed and enforced | `src/techtree/models/data_policy.py` | `tests/unit/test_data_policy.py::test_public_report_against_a_private_policy_is_rejected` | Data policy sha256:6c532a43, in every report, bundle and receipt | Fixed v0.1 policy | no |
| claim-11 | Offline verification | `src/techtree/receipts/verify.py` | `tests/unit/test_local_bundle_verify.py::test_a_complete_proof_verifies_offline` | `techtree proof verify` run here on all six bundles: 339/339 passed | No honest-compute proof | yes |
| claim-12 | Explicit approval before anything is spent | `src/techtree/runs/service.py` | `tests/plugin/unit/test_approvals.py::test_the_plugin_issues_no_approval_of_its_own` | Exactly one run.approved event per run; both CLI and host-agent surfaces on this lineage | Surface attestation | yes |
| claim-13 | An incomplete comparison fails closed | `src/techtree/runs/real.py` | `tests/unit/test_episode_receipt_builder.py::test_a_missing_task_is_an_episode_count_mismatch` | Superseded-lineage kill injection run_ba3998e2 only; no failure exists on this lineage | No Uplift receipt | yes |
| scope-01 | Skill-bundle v1-vs-v2 comparison is supported when both bundles are supplied explicitly | `src/techtree/skills/scanner.py` | `tests/integration/test_multi_file_skill.py::test_the_draft_holds_the_whole_tree` | run_4584be6d on derived campaign sha256:0f3cb014, 0.639 -> 0.667 | The certified replacement run compared two single-file bundles | yes |
| scope-02 | Guided revision is single-SKILL.md in v0.1; the flow is certified and no measured uplift is claimed | `src/techtree/uplift/source.py` | `tests/unit/test_verified_source_skill.py::test_the_entrypoint_text_comes_back_with_what_it_was_verified_against` | One host completion, response a319c0b7b9bceb36-SJC, producing SKILL.md sha256:4d94de88 | The flow is certified; the improvement is not | yes |
| ext-01 | One pinned plugin installs and verifies Techtree | `../techtree-plugin/bootstrap.py` | `tests/plugin/unit/test_bootstrap.py::test_a_missing_cli_produces_one_exact_plan` | WP11f installed plugin df5ead2b from a fresh home; release verify and both doctors green | Not yet installed from published coordinates | yes |
| ext-02 | The result is shown deterministically and the explanation is guarded | `src/techtree/presentation/build.py` | `tests/unit/test_presentation_build.py::test_the_same_report_builds_the_same_bytes` | All six reports carry P1 and publication_eligible false; the grade is rendered from the verified report | The explanation Skill is guarded, not verified | yes |
| ext-03 | The proposed Skill v2 is shown and scanned before approval | `src/techtree/skills/scanner.py` | `tests/unit/test_skill_scanner.py::test_default_policy_matches_the_v01_instruction_skill_rules` | Diff sha256:151d921d shown before approval, on this lineage, 0 guards fired | Mechanical scan only, and no longer a credential scan | yes |
| ext-04 | Nothing is uploaded to the website | `src/techtree/verifiers/config.py` | `tests/unit/test_verifiers_verify.py::test_a_resolved_config_that_would_upload_fails_the_push_check` | One techtree.sh request across the whole surface, method GET; push false in every resolved config | The claim is about the website and the Verifiers platform, not the network | yes |

## Gap register

Every entry below is an honest gap: the claim holds, but a specific artifact or a specific named test that the contract asks for does not exist for this lineage. None of these was invented around, and none is fixed by this refresh. Twelve rows carry one; the previous edition's register had five.

1. **claim-05 — Clean subjects.** The `platform` field is null in all 432 receipts of this lineage, so the per-platform manifest digest is a declared pin carried in the signed experiment documents and checked by a preflight test, not something the runs recorded. Separately, no trace-level artifact is committed to this repository: the traces exist in the run trees and their digests are committed inside the signed receipts, but the only committed trace-level bytes are the sanitized fixture from run_6ce5e56a7dd341bca8bc6de1d6a60027, which belongs to a doubly superseded Campaign.
2. **claim-06 — Only the Skill changed.** The name of the one accepted warning, `model_revision_discoverable`, appears in no artifact of this lineage. Each run stores the status `controlled_with_warnings`; the warning's identity is established from the code that raises it plus the shipped Campaign's `revision: null`. The previous edition sourced it from a worker ledger that belongs to the superseded quiet window.
3. **claim-09 — Cost and timing.** No spend ledger exists for the three certification executions or the founder walkthrough. Every dollar figure for them in this document was worked out here from their own recorded token counts at a rate card dated 2026-08-20. The WP11f legs are fully accounted for in `release/acceptance/onboarding-e2e.json`.
4. **claim-11 — Offline verification.** No third party has ever verified a bundle of this lineage, and there is no path by which one could obtain one: nothing is uploaded and the website publishes no bundle. The mechanism supports the claim; no live evidence does. See Stop conditions.
5. **claim-12 — Explicit approval.** The approval record the plugin hands back to the host agent carries `draft_digest: null` (finding wp11f-6), although the run's own journal carries the digest. The single field that makes 'a person approved this exact draft' checkable is missing from the surface the person actually reads.
6. **claim-13 — An incomplete comparison fails closed.** No run of this lineage failed, was killed, or reached a limit. Every artifact this row cites belongs to the superseded Campaign, and the fingerprint records that the kill injection was deliberately not repeated on the argument that every input to the orphan bound is unchanged. That is a ruling, not new evidence.
7. **scope-01 — Skill-bundle v1-vs-v2.** No live-evidence artifact exists for a multi-file bundle pair. Coverage for that case is `tests/integration/test_multi_file_skill.py` alone.
8. **scope-02 — Guided revision.** The live proposal came back without its request accounting, its draft digest or its scanner verdict, because the plugin defaults to the bounded chat-shaped answer and nothing tells an agent to ask for the terminal one (finding wp11f-5). Separately, the guided introduction's session does not survive a restart, and the guide instructs a restart during onboarding (finding wp11f-4).
9. **ext-01 — One pinned plugin installs and verifies Techtree.** Six gaps: the operator Skill tells an agent the journey is impossible (wp11f-1, P0, blocks Gate 2); the guide and plugin README promise five scanner findings where six appear (wp11f-2); the published install command omits the interpreter pin its own prose promises (wp11f-7); no `.sha256` sidecar beside the wheel (wp11f-11); the published command pre-answers the enable prompt (wp11f-12); and the engine-verified state can never be reached, leaving an unclearable next action on the main onboarding surface (wp11f-3). Nothing is published from public coordinates before Gate 2.
10. **ext-02 — Deterministic result and guarded explanation.** The presentation layer no longer refuses a payload for carrying credential-shaped text and the test that asserted it did is gone (decision 0036). More broadly, the copy contract scans for forbidden phrases and never compares a claim about machine behaviour against the machine, which is why three wrong predictions passed every guard.
11. **ext-03 — The proposed Skill v2 is shown and scanned.** The scanner's verdict was not in the answer the person saw (`scanner: null`, finding wp11f-5). And the shipped improver Skill still lists 'No secret-like values.' among requirements that are otherwise enforced; nothing enforces that one since decision 0036.
12. **ext-04 — Nothing is uploaded.** `--no-push` on the *evaluation* argv is established from code plus the resolved configuration, not from a verbatim record in the run tree; only the dry-run leg stores its argv verbatim. And the three-method no-upload proof predates decision 0036 by three days: `release/security-review.json`, `release/security-review.md` and `release/public-visibility-review.md` all still describe a scrubber and a Skill secret-detection table that no longer exist.

## Figures the previous edition stated that this refresh could not source in this lineage

Recorded rather than substituted, as the refresh required.

1. **Everything anchored on Campaign `ad393bc0…`.** The five run identifiers of the 2026-08-20 quiet window (`run_06b2377d…`, `run_8fdfdcf6…`, `run_ad759a00…`, `run_ede1fd20…`, `run_ba3998e2…`), their report digests (`5ad470aa…`, `f002a836…`, `e3855700…`, `74c26dd1…`), bundle digests (`f41e5135…`, `cee88ccf…`, `9827854d…`, `7f540adc…`), execution-record digests and costs (0.1734, 0.1496, 0.1634, 0.0558). Superseded by the engine move. The run trees still exist under `certification-evidence/recert-0029-quiet-2026-08-20/` and are cited only in claim-13, labelled as superseded-lineage evidence.
2. **Coordinates `ac76d787…` (Climb), `ae300ef6…` (catalog), `c037f457…` (ReleaseCore), `874cbae0…` (engine), `2edd60bc…` (taskset lock), `14d9646d…` (taskset package), `080895d5…` (validation receipt), `9c4959d3…` (validation evidence), `5105b91c…` (derived campaign).** All replaced by the values in the coordinates table.
3. **Skill v2 root `2081ae90…`, SKILL.md `0beea6ec…`, 1,966 bytes, 48 lines, name `frozen-v2`.** The 2026-08-20 frozen v2. This lineage's guided revision produced a different Skill: root `5e2e2f58…`, SKILL.md `4d94de88…`, 1,897 bytes, 49 lines, name `revision`.
4. **The 2026-08-20 host call** — request `3347f071…`, response `30e1dc37…`, response id `a2e008cb1b5e138a-SJC`, 5,133 in / 6,501 out, USD 0.0376. Superseded by the 2026-08-27 call recorded in scope-02.
5. **"USD 4.2487 of the 15.00 cap" and the quiet-window total of USD 0.5429.** From `certification-evidence/recert-0025/NOTES.md`, which belongs to the superseded programme. No ledger exists for this lineage's certification executions; see the claim-09 gap.
6. **"288 episodes" and "847 files".** Recounted for this edition against six runs rather than four: 432 episodes and 1,271 files.
7. **"Executor key ids `ce372029…`, `8131c7bf…`, `61a5cf45…`".** Those keys belong to the quiet window's three isolated homes. This lineage has two keys, `df8995a3…` and `45224709…`.
8. **The `verifiers/<variant>/run/config.toml` path.** Verifiers 0.3.1 writes `verifiers/<variant>/run/configs/resolved/eval.json`; no TOML file exists in any run tree of this lineage.
9. **"102 implementation paths and 255 test citations", then "74 and 259".** Recounted for this edition: 280 distinct test citations across 287 references, and 74 distinct implementation paths across 103 references.
10. **Validator revision `7e1c47d24d055aae587ee8259f77a3e8e193513a`.** The pre-release development revision. The shipped validation receipt names `b2e4e8157783b2c0dffc7821044c87f29f1c3ccf`.

## Corrections — things the previous edition got wrong rather than merely stale

1. **The previous edition said both Gate-1 Skill digests are unchanged in this lineage.** The starter Skill's are; the improver's is not. Gate 1 approved `e6bc16c4…` and this release ships `d5a381be…`. The change is one line, removing the word `secrets` from the sentence describing what the improvement context omits, forced by decision 0036. The fingerprint's own `cross_check` records `skill_improver_matches_gate1: false`. The section now says so plainly.
2. **The previous edition said the engine digest appears in every episode receipt.** It does not. All 432 receipts were read in this refresh and an `EpisodeReceipt` carries no engine digest at all. The engine digest is committed in the taskset lock, the validation receipt and the signed execution record.
3. **The previous edition claimed three distinct executor keys, one per home.** The principle is right and the count was for a different set of runs. This lineage has two keys across six runs, because the three certification executions and the walkthrough all ran in one home.
4. **The previous edition cited the resolved engine configuration as `run/config.toml`.** That path does not exist under Verifiers 0.3.1. Every citation now uses `run/configs/resolved/eval.json`, which is what the runs actually wrote.
5. **The previous edition attributed the copied-task-material check to the Skill scanner.** It is the plugin's copied-case guard (`../techtree-plugin/guards.py`), not the scanner. The scanner's policy is now purely shape: suffixes, file count, file and total size, entrypoint, symlinks, hidden files.
6. **Five cited tests no longer exist**, all removed by decision 0036: `test_credential_shapes_are_blocking`, `test_a_blocking_finding_stops_the_scan`, `test_a_finding_carries_no_matched_text`, `test_findings_report_the_relative_path_not_the_participants_directory` (the scanner's whole findings mechanism went with the secret rule table) and `test_a_payload_carrying_a_credential_is_refused`. None is replaced by an equivalent, because no equivalent behaviour remains. The rows that cited them now carry gaps.
7. **Four `techtree-ash` citations were written at a path that resolves only from the workspace root.** They are written `../techtree-ash/…` here, matching the convention already used for the plugin, and all four test names were located in the files during this refresh.
8. **The previous edition said the durable evidence lives at `certification-evidence/`.** True of the superseded lineage, not of this one. There is no evidence archive for the runs this document cites; they live in the founder's live Techtree home and in a WP11f scratchpad. This is stated plainly in "How to read this" and is in the gap register.
9. **The previous edition stated the immutability sweep found not one file modified after its run's last journal event.** Repeating the sweep over six trees finds two: `improvement/context.json` in the walkthrough and in the WP11f first comparison, both written when the participant afterwards asked for a guided revision, neither part of any proof bundle. Every one of the 504 files inside the six proof directories is unmodified. The claim is now stated with that exception rather than without it.

## Stop conditions

- *Any public claim with no implementation row* — **not triggered by the authoritative product statement**, which was walked clause by clause again; the four clauses the thirteen required rows do not cover are `ext-01`…`ext-04`. But see the second condition: two live website claims go beyond every row in this document.
- *Any row whose limitation contradicts public copy* — **TRIGGERED, twice, on the website.**

  1. **`../techtree-ash/lib/techtree_web/live/home_live.ex:71-74`**, the homepage hero lede: Techtree "signs the result so another participant can verify or reproduce it in an identical Environment", and step 03 at line 122, "let another machine reproduce it". claim-08's and claim-11's limitations say the opposite in this document, and the application's own documentation page says the opposite in the same codebase: "A reproduction would require another executor to run the same scientific contract and record a separately attributable result. v0.1 does not provide a public reproduction or attestation-import workflow." Nothing is uploaded, so no other participant holds a bundle. This is the first sentence a visitor reads.
  2. **`../techtree-ash/lib/techtree_web/live/proofs_live.ex:65-67`**: the example result is described as "proving that a Hermes agent can run long-horizon tasks using the Techtree Plugin", and at lines 54-57 the proof is "used to hill-climb Skill improvement". Both are capability and uplift claims over one synthetic 36-task demo whose baseline floor is zero and whose one measured improvement is +1 inside a 23-24 spread. Decision 0035 forbids exactly this register, and scope-02's limitation forbids exactly this inference. The page carries no proof-of-concept frame.

  Neither is repaired here. This document's job is to find them.

- *A third condition this refresh adds, because the evidence demanded it.* Two further public claims are contradicted not by a limitation but by a measured finding, and are recorded under the rows they belong to rather than here: the promised count of install-time scanner findings (ext-01, wp11f-2) and the promise that nothing is lost when a session ends (scope-02, wp11f-4).

## Discrepancies noted, not fixed

1. `release/founder-skill-approval-draft.md` still opens with "Status: FINAL, awaiting the founder's Gate-1 approval phrase", but `release/founder-approvals/gate1-founder-skills.md` records that the approval phrase was received on 2026-08-14 against exactly this packet's digest (`sha256:b3ea3ba1…`, recomputed here from the working-tree bytes). The packet header is stale. Reported, not amended — changing those bytes would change the approved digest.
2. `release/wheel-inspection.json` carries a finding, `certified_fingerprint_names_an_earlier_lineage`, stating that `release/certified-scientific-fingerprint.json` names Campaign `ad393bc0…` while the wheel ships `ebf029ab…`. That finding was written at 00:57 on 2026-08-27; the fingerprint was regenerated at 01:24 and now names `ebf029ab…`. The divergence the finding records no longer exists, and the finding is stale rather than wrong. Reported, not amended.
3. `release/orphan-bound-analysis.json` still names the superseded Campaign `ad393bc0…` in its own `campaign` block. The fingerprint acknowledges this and gives the reason: every input to the bound — the four enforced limits, the task count, the per-call sampling cap and the recorded prices — is byte-identical between the two Campaigns, so the computed bound (USD 2.4152 against the declared 2.50 maximum) is the same number. Recorded, not interpreted.
4. `release/security-review.json`, `release/security-review.md` and `release/public-visibility-review.md` all predate decision 0036 and all describe machinery that no longer exists: a seven-case scrubber corpus reported as "Seven of seven redact", a `secrets_scrubber` section, a `tests/fixtures/skills/invalid-secret/notes.md` fixture and a "secret-detection rule table" in `src/techtree/skills/scanner.py`. This refresh confirmed that the fixture and the rule table are gone. Their network and supply-chain findings are unaffected; their map of current code is not. They need a dated supersession note before they travel in a Gate-2 packet.
5. `release/acceptance/terminal-e2e.json` and `.md` remain in the release directory and describe the WP11e journey on ReleaseCore `90cd8ad6…`, engine `874cbae0…` and improver `e6bc16c4…` — a doubly superseded lineage. `release/acceptance/onboarding-e2e.json` supersedes it for every purpose this matrix uses. Nothing in this edition cites the terminal-e2e record as evidence.
6. The shipped Climb's own prepare-time output describes it as "a development Climb", whose report is "not publication eligible" and whose "result is not comparable evidence", and every run carries `publication_eligible: false`. That is consistent with the proof bundles, with the toy framing and with decision 0035's proof-of-concept frame, but it is a stronger self-description than the rows above discuss, and it is recorded here rather than interpreted.
7. The guided-revision draft records `source_kind: "manual"` even though the revision came from the real guided path (`techtree_uplift_propose` on the installed plugin). The field distinguishes how the bytes reached the CLI, not who wrote them. Recorded so nobody reads it as evidence that the revision was hand-written.

