# Product-claim-to-evidence matrix — Climb v0.1

Ticket: techtree-python-y8s (decision 0023 item 3.2).  
Execution contract: `docs/release/contracts/wp11-claims.md`.  
Binding copy boundaries: decision 0013 §1.  Scope statement: decision 0023 §4.  
Lineage authority: decisions 0025, 0029 and 0033.  
Attachment to the Gate-2 packet; runs before WP11h.

Refreshed 2026-08-26 against the final certified lineage. The previous edition of this document anchored on Campaign `b9e3f00c…` and the five run identifiers of the first certification. That lineage has been superseded twice and re-certified; every citation below was re-read from an artifact during this refresh.

## The lineage this matrix anchors on

Every row cites the lineage recorded in `release/certified-scientific-fingerprint.json`:

| Coordinate | Value | Read from |
|---|---|---|
| Campaign | `sha256:ad393bc0fc36df108c0b93e3a0cc35bc175b34fb00788f3306dbee707d467eb7` | `src/techtree/resources/catalog/campaigns/hello-world-climb.json`, hashed in this refresh |
| Climb | `sha256:ac76d7876dafbdc3bcddf4884dfa75831eff3a1ad461de517d4f04ef29a3e4fa` | `src/techtree/resources/catalog/climbs/hello-world-climb.json`, hashed in this refresh |
| Catalog | `sha256:ae300ef6ba97233f5bef86b8281ed34a02db91114d8d78c79324ce68f721d386` | `release/release-core.json` `catalog_digest` |
| ReleaseCore | `sha256:c037f4578134185cc22717908bce58749bbb5086536fc955881a2b831abd8530` | `release/release-core.json`, hashed in this refresh |

Three independent confirmations that this is the final lineage, all made during this refresh:

1. `release/certified-scientific-fingerprint.json` names these four values under `recertification_pending.current_lineage`, names the previous set under `superseded_lineage`, and carries `runs_attached: true` with the five re-certification run identifiers.
2. Each of the four re-certification comparisons carries the Campaign digest in its **own signed uplift report**: `report/uplift.json` of the three Climb comparisons names `campaign_spec_digest sha256:ad393bc0…`, and all 288 signed episode receipts across the four runs name the same value. The v1-vs-v2 comparison names its derived Campaign `sha256:5105b91c…` (see below).
3. Every coordinate above was recomputed from the working tree with `shasum -a 256` and matched the fingerprint byte for byte; the taskset lock, membership, validation receipt and validation evidence were additionally read out of a proof bundle rather than out of the repository, and matched.

**Superseded, and named here only so nothing cites them by accident.** The first certification ran derived Campaign `b9e3f00c…` (catalog Campaign `5aef3fb7…`, Climb `93c03b3a…`/`61a7dd46…`, catalog `62714b77…`/`468e8ab1…`, ReleaseCore `90cd8ad6…`/`80807821…`) over runs `run_d9409450…`, `run_a6c608b9…`, `run_6ff833ca…`, `run_9f2a5025…` and `run_e29f1781…`. Decision 0029 changed the Campaign's budget contract after that, which produced the lineage above. No row below cites any of those runs or digests as evidence.

**What the Gate-1 approval does and does not cover.** The founder's Gate-1 approval (`release/founder-approvals/gate1-founder-skills.md`, against packet digest `sha256:b3ea3ba1…`, recomputed here from `release/founder-skill-approval-draft.md`) approved the two Skill files, whose digests are unchanged in this lineage: starter tree `596d1368…` / file `2aff2707…`, improver `e6bc16c4…`, all three recomputed in this refresh. The fingerprint's own `cross_check` note states plainly that neither the packet nor Addendum 1 (`sha256:568f3a53…`, recomputed here) names the lineage above, because 0029 changed the budget contract after both. Decision 0025 §4 settles the disposition: the packet bytes are never edited, and the new lineage travels in the Gate-2 packet.

## How to read this

One row per public product claim. Each row names the modules that implement it, tests that exist in the trees today (every test name below was located by search before it was written down), the live evidence from the final-lineage certification programme, and the limitation that must travel with the claim in public copy.

**Where live evidence lives.** Run trees are not committed to this repository — `runs/` is empty by design and raw subject traces stay on the participant's machine because they carry the taskset's expected answers (spec §6.19). The durable evidence lives outside the repositories at `certification-evidence/`, and this refresh read it directly: run directories, signed reports, proof bundles, episode receipts, resolved engine configurations, supervision records and the worker's own ledger. Wherever a row cites a run, it cites the run's own bytes, not a summary of them. Rows where a hole remains carry a Gaps block, and every gap is repeated in the gap register at the end.

**Wording.** The matrix records exact measured scores because it is a certification record. Public copy states the calibrated 20-27/36 band and never an exact score; says "no Techtree account is required", never "no account required"; says participant-attested and not independently reproduced, never independently verified; and always qualifies privacy statements with the fact that model calls go to the selected provider.

**Model scope (decision 0033).** v0.1 ships exactly this lineage: qwen/qwen3.7-flash served by Prime, with no re-certification. The 20-27/36 band is calibrated on that model and does not transfer to any other. Nothing in this document states a band, a score or a cost for any model other than the one the Campaign pins.

## What this refresh verified

Executed here, 2026-08-26, in `techtree-python`:

- `uv run pytest tests/unit` — 2561 passed, 1 skipped (`tests/unit/test_skill_scanner.py::test_the_case_collision_rule_holds_on_a_case_folding_filesystem` skips on this machine's case-folding filesystem).
- `uv run pytest tests/contract` — 454 passed.
- `uv run pytest -m "integration and not real_model"` — 286 passed, 3018 deselected.
- `uv run pytest tests/plugin` — 850 passed. The seven suites this matrix cites by name (`test_approvals`, `test_guards`, `test_bootstrap`, `test_release`, `test_one_generation_request`, `test_plugin_doctor`, `test_one_turn_revision`) — 189 passed.
- `uv run techtree proof verify <run>/proof` on all four re-certification comparisons — each reports **339 checks, all passed, verified**, with the one standing warning "No independent reproduction: nobody else has run this comparison, and no platform witnessed it."
- An immutability sweep over the four run trees: 847 files in total, and **not one** was modified more than a second after its own run's last journal event.

Citation resolution: 74 implementation paths and 259 test citations were resolved mechanically against the trees before being written down. Everything that did not resolve was corrected rather than carried (see "Corrections", below).

Not executed here:

- The four `techtree-ash` citations (`techtree-ash/test/techtree_web/router_test.exs`, `techtree-ash/test/techtree_web/endpoint_test.exs`). The Ash test setup needs a PostgreSQL database that is not available to this worker, so those four test names were verified by reading the files, not by running them.
- The five cited preflight tests. They are marked `preflight`, excluded from the default selection, and need a pinned Verifiers install and registry access; all five names were verified to exist by reading the files.
- No `real_model` test is cited anywhere in this matrix, and none was run — those calls cost money and provision Docker. No paid run of any kind was made for this refresh.

Disclosed: the `techtree-plugin` checkout was being edited by another worker while this refresh ran. The `tests/plugin` figures above are that suite's result at the moment it was run against that checkout.

## Canonical certification runs — final lineage

The four comparisons and the kill injection listed in `release/certified-scientific-fingerprint.json` under `recertification_pending.runs_attached_detail`, executed against Campaign `ad393bc0…` on repository commit `48b7d784ea6e68a625709c828cfc86e0c80dbe5a`, through the real detached launcher and the real child-local supervisors, each in a fresh isolated home, in an exclusive quiet window with zero other containers running. Durable evidence: `certification-evidence/recert-0029-quiet-2026-08-20/`; worker ledger: `certification-evidence/recert-0025/NOTES.md`.

| Run | ID | Score | W/L/T | Report (file) | Bundle (payload) | Cost (USD) |
|---|---|---|---|---|---|---|
| stability #1 | `run_06b2377d55f6455a9dc5a73e6f14e384` | 0/36 -> 24/36 | 24/0/12 | `sha256:5ad470aa...` | `sha256:f41e5135...` | 0.1734 |
| stability #2 | `run_8fdfdcf69811483b8c2e3260c7e2784c` | 0/36 -> 23/36 | 23/0/13 | `sha256:f002a836...` | `sha256:cee88ccf...` | 0.1496 |
| engine reference | `run_ad759a00588540b3b7020a4118599799` | 0/36 -> 36/36 | 36/0/0 | `sha256:e3855700...` | `sha256:9827854d...` | 0.1634 |
| v1 vs frozen v2 | `run_ede1fd20186d43c68386a53501396fb5` | 23/36 -> 24/36 | 1/0/35 | `sha256:74c26dd1...` | `sha256:7f540adc...` | 0.0558 |
| kill injection | `run_ba3998e2a0d94126bc7426d0c6b32aab` | no score — worker SIGKILLed mid-run | — | none written | none written | 0.0007 |

Signed execution records, one per comparison, payload digests read from `proof/comparison-execution.json`: `sha256:f2defd94...`, `sha256:566b0b15...`, `sha256:ae4b0f19...`, `sha256:87b4519c...`. The fingerprint's `execution_record_digest` field for each run is the file digest of that run's `execution/real-execution-result.json` (`sha256:b66f5471...`, `sha256:66872df7...`, `sha256:b2df2382...`, `sha256:9bb4e58c...`); both were recomputed here and both are recorded so neither is mistaken for the other.

All four comparisons: `controlled_with_warnings`, evidence complete, score valid, execution completed, decision accepted, proof grade P1, `executor_kind` verifiers, manifest comparison `controlled: true` with zero violations, proof verifies offline. Across all four: **288 episodes, 0 reaching any enforced limit, 0 calls at or over the 4,096 sampling ceiling, 0 errored calls**, and no variant approached the 3,600-second supervisor deadline (worst 891.0 s, 4.04x margin).

**How the cost figures were arrived at.** Every one of the four runs' own signed `ComparisonExecutionRecord` reports `cost_usd: null` with provenance `unavailable` for **both** variants — "no cost figure was reported for this variant, and this build pins no price to compute one from". The dollar figures above are computed from each run's recorded token counts at the rate card in `release/price-profile.json` (qwen/qwen3.7-flash, USD 0.03 / 0.13 per Mtok, recorded 2026-08-20), charging every input token at the uncached rate. On the cached-input-free basis the same four runs are 0.1089, 0.0979, 0.1103 and 0.0461. The product itself never states either figure as a provider-billed amount.

**Programme spend.** `certification-evidence/recert-0025/NOTES.md` records the quiet window at USD 0.5429 actual against 0.8649 estimated, and the programme at **USD 4.2487 of the 15.00 cap** raised by the founder on 2026-08-20. The dearest single comparison was 0.1734 against the 0.30 per-comparison ceiling. No paid outcome was retried; every run was pre-committed before its score existed.

## Other runs against Campaign `ad393bc0…`, disclosed and not canonical

Recorded here so the canonical set is not mistaken for everything that ran.

| Run | Outcome | Why it is not canonical |
|---|---|---|
| `run_8e2bbbbec18d422ca2ed0711bfb0f29f` | completed, 0/36 -> 24/36, accepted, P1, report `sha256:a1a74910...` | Executed under the superseded 1,800-second variant-deadline constant. The ledger excludes it explicitly: "the previous attempt's run 1 belongs to the superseded constant and is not reused." |
| `run_4fae4473bd1546a0a245fd9c41b898ff` | failed, `variant_execution_failed`, baseline reached the 3,600 s deadline at 3,604.7 s, USD 0.1445 | A pre-committed canonical run that reached a limit. Decision 0029's stop condition fired; the deadline was not raised and nothing was retried. |
| `run_37647dbe3aa84494a791f0f6a460da50` | failed, `variant_execution_failed`, baseline reached the then-1,800 s deadline at 1,803.7 s, USD 0.1685 | Same stop condition, previous attempt. |
| `run_2f264fc8a7c841e49e6cdc763162915a` | failed before dispatch, `worker_executable_not_found`, USD 0.0000 | Nothing ran and nothing was charged. |

## Coordinates re-verified by this refresh

Recomputed from the working tree with `shasum -a 256`; every value equals `release/certified-scientific-fingerprint.json`.

| Object | Digest | Source |
|---|---|---|
| campaign | `sha256:ad393bc0fc36df10...` | src/techtree/resources/catalog/campaigns/hello-world-climb.json |
| climb | `sha256:ac76d7876dafbdc3...` | src/techtree/resources/catalog/climbs/hello-world-climb.json |
| data policy | `sha256:6c532a43d595286a...` | src/techtree/resources/catalog/data-policies/hello-world-climb.json |
| validation receipt | `sha256:080895d53a967d63...` | src/techtree/resources/catalog/taskset-validations/hello-world-climb.json |
| validation evidence | `sha256:9c4959d3b9217ab8...` | src/techtree/resources/catalog/validation-evidence/hello-world-climb.json |
| taskset lock | `sha256:2edd60bcdf67b01c...` | read out of `proof/taskset-lock.json` of run_06b2377d…, not out of the repository |
| taskset membership | `sha256:56f697fb182cc316...` | the same lock, and the shipped Campaign's `taskset.membership.membership_digest` |
| taskset package | `sha256:14d9646d79fbcc1a...` | the same lock, `resolved_package_digest` (embedded procedure-transfer-v1 0.1.0) |
| engine | `sha256:874cbae03d393582...` | release/release-core.json `engine_digest`; also in every episode receipt |
| catalog | `sha256:ae300ef6ba97233f...` | release/release-core.json `catalog_digest` |
| starter skill file | `sha256:2aff27070177d9f3...` | release/skills/hello-world-starter-v1/SKILL.md |
| starter skill tree | `sha256:596d1368ac157975...` | release/release-core.json `starter_skill_digest` (the pin, decision 0008) |
| skill improver file | `sha256:e6bc16c4d6740a0c...` | ../techtree-plugin/skills/skill-improver/SKILL.md |
| release core | `sha256:c037f45781341855...` | byte-identical in techtree-python/release/release-core.json, src/techtree/resources/release/release-core.json and techtree-plugin/release-core.json; all three recomputed here |
| certified fingerprint | `sha256:629972418258cb56...` | release/certified-scientific-fingerprint.json |
| gate1 packet | `sha256:b3ea3ba12af27af8...` | release/founder-skill-approval-draft.md |
| gate1 addendum 1 | `sha256:568f3a5371543d54...` | release/founder-skill-approval-addendum-1.md |

Subject coordinates, read from the shipped Campaign and confirmed in the resolved engine configuration of run_06b2377d…: qwen/qwen3.7-flash, provider prime, credential env PRIME_API_KEY, revision null, sampling temperature 0 and max_tokens 4096, harness hermes-agent 0.19.0, runtime docker on `python@sha256:90744cff…` with per-platform manifest digests for linux/amd64 and linux/arm64, network policy restricted. Enforced budgets, compiled into both variants: max_turns 44, max_input_tokens 900,000, max_output_tokens 16,000, max_total_tokens 916,000 (derived), rollout timeout 600 s, maximum_usd 2.50.

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

- Campaign hello-world-climb `sha256:ad393bc0fc36df10…` — recomputed in this refresh from src/techtree/resources/catalog/campaigns/hello-world-climb.json and equal to the fingerprint's `campaign_spec_digest`.
- The three Climb comparisons anchor on it directly (`campaign_spec_digest` in each run's own report/uplift.json); the v1-vs-v2 comparison anchors on derived Campaign `sha256:5105b91c8b610c85…`, which the fingerprint records as differing from ad393bc0 only in the baseline arm's Skill and the mutation-contract kind, with budgets, execution limits, taskset, membership, model and sampling byte-identical.
- All 288 signed episode receipts of the four runs carry `campaign_spec_digest sha256:ad393bc0…` (the v1-vs-v2 run's carry its derived digest), and each proof bundle commits to the Campaign document it ran.
- Immutability, measured in this refresh rather than asserted: across the four run trees, 847 files, none modified more than one second after that run's last journal event.

**Limitation.** 'Campaign' is an internal protocol concept; a participant never names one. Immutability is enforced by recomputing digests over frozen canonical bytes — there is no external registry, notary or timestamping authority, so the guarantee is 'this object is not the object it claims to be if a byte moved', not 'this object existed before that moment'. The Campaign itself has been regenerated twice under founder rulings (decisions 0025 and 0029); immutability is a property of each version's bytes, not a claim that the shipped Campaign has never changed.

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

- Membership digest `sha256:56f697fb182cc316…` — read in this refresh from the shipped Campaign's `taskset.membership.membership_digest` and, independently, from `proof/taskset-lock.json` of run_06b2377d…, where it appears alongside `task_count: 36` and resolved package `sha256:14d9646d…`.
- Taskset lock `sha256:2edd60bcdf67b01c…`, hashed from the copy inside the proof bundle; equal to the fingerprint's `taskset_lock_digest`.
- Every one of the four comparisons reports exactly 36 `task_deltas`, and each carries 36 baseline plus 36 candidate signed receipts — 288 receipts in total, all `evidence_status: complete` and `score_status: valid`.
- The v1-vs-v2 comparison reports 1 win / 0 losses / 35 ties over exactly those 36 tasks.

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

- Validation receipt `sha256:080895d53a967d63…` — hashed in this refresh from `proof/taskset-validation-receipt.json` of run_06b2377d…, and equal to the shipped `src/techtree/resources/catalog/taskset-validations/hello-world-climb.json`. The published receipt is the one that travelled inside the certified proof.
- Its six checks, read from those bytes, all `passed`: `upstream_gold` (all 36), `upstream_setup` (all 36), `membership_repeatability` (two independent inspections agreed on all 36 hashes in order), `task_hash_uniqueness`, `committed_membership_match`, `expected_task_count`. Method `verifiers_validate`, validator revision `7e1c47d24d055aae587ee8259f77a3e8e193513a`.
- Validation evidence `sha256:9c4959d3b9217ab8…`, named by that receipt and equal to the shipped copy; the run's own evidence file records total 36, valid 36, invalid 0, error 0, timeout 0, missing 0.

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

- All three insertion comparisons of the final lineage scored the baseline **0/36**: run_06b2377d55f6455a9dc5a73e6f14e384, run_8fdfdcf69811483b8c2e3260c7e2784c and run_ad759a00588540b3b7020a4118599799, each read from its own report's `primary_result.baseline_mean: 0`.
- The manifest comparison of each of those runs records exactly one difference, at pointer `/agents/subject/harness/skills/0`, with `baseline: null` — the baseline mounts nothing. The candidate side names `sha256:596d1368…` (1,496 bytes) in the two stability runs and the complete reference Skill `sha256:170256f7…` (2,357 bytes) in the engine reference.
- The resolved engine configuration the baseline actually ran under (`verifiers/baseline/run/config.toml` of run_06b2377d…) carries `[env.subject.harness] skills = []`.
- The shipped Campaign's `mutation_contract` is `skill_insertion`, minimum 1 / maximum 1 skill, allowed difference `/agents/subject/harness/skills`.

**Limitation.** Toy task. The baseline floor of 0/36 is on one synthetic 36-task BranchCode taskset built for this demo. A zero floor shows the Skill is doing the work in this Climb; it does not show that the measurement generalises to real tasks.

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

- All 288 signed episode receipts of the four final-lineage comparisons record the same `subject_runtime.resolved_image_digest`, `sha256:90744cff8f32887f…`, and `kind: docker` — read in this refresh from the receipts themselves.
- The resolved configuration both variants ran under (`verifiers/<variant>/run/config.toml`) carries the same pinned image, `cpu 2.0`, `memory 4.0`, egress `allow = []` / `block = ["*"]`, `[sampling] temperature = 0.0` and `max_tokens = 4096`, and the same compiled ceilings on both sides (max_turns 44, max_input_tokens 900,000, max_output_tokens 16,000, max_total_tokens 916,000, rollout timeout 600 s).
- Supervision records written by the child-local supervisor for every variant (`verifiers/<variant>/supervision.json`, mode 0600) record `reason: completed`, `escalated_to_sigkill: false`, and a 3,600-second deadline never approached.

**Limitation.** Local executor. The containers run on the participant's own Docker daemon; Techtree records what that daemon reported and verifies the two sides agree, but nothing attests that the daemon, the image or the host were unmodified. Raw subject traces stay on the participant's machine and are deliberately not committed (spec §6.19) because they carry the taskset's expected answers.

**Gaps (findings, not fixed here)**

- The `platform` field is `null` in all 288 final-lineage receipts. What those receipts establish is that every episode on both sides resolved the same image **index** digest; the per-platform manifest digests (linux/amd64 `sha256:78b39ef1…`, linux/arm64 `sha256:20eadabc…`) are a declared pin in the Campaign and are checked by a preflight test, not something these receipts recorded. The previous edition of this matrix stated that both variants resolved to the same platform-specific digest; that statement is not carried, because these receipts do not support it.
- No trace-level artifact from any canonical run is committed to this repository. The traces exist — `verifiers/<variant>/run/traces.jsonl`, whose digests are committed inside each signed execution record and episode receipt — but they live only in the durable evidence outside the repositories, by design. The only committed trace-level evidence is the sanitized fixture at `tests/fixtures/receipts/recorded/`, which came from run_6ce5e56a7dd341bca8bc6de1d6a60027 under the **superseded** Campaign (its committed campaign.json still carries the old budget contract: output 8,000, maximum_usd 1.00, no input or model-call ceiling). It is a conformance asset for the receipt pipeline, not evidence about the shipped lineage.

### claim-06 — Only the Skill changed

**Public wording.** Techtree proves that the Skill was the only difference between the two sides.

**Implementation**

- `src/techtree/manifests/compare.py` — compare_manifests, assert_controlled_comparison, pointer/variant/skill-count violations
- `src/techtree/receipts/compare.py` — the observed tool-surface comparison, the single named SKILL_INDEX_TOOL exception, and MODEL_REVISION_UNDISCOVERABLE
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

- UpliftReport file digests, one per final-lineage comparison, hashed in this refresh: `sha256:5ad470aa…`, `sha256:f002a836…`, `sha256:e3855700…`, `sha256:74c26dd1…`.
- Each report's `manifest_comparison` records `controlled: true`, `violations: []`, `allowed_differences: ["/agents/subject/harness/skills"]`, and exactly one entry in `differences` — the mounted Skill. In the v1-vs-v2 comparison the single difference is the Skill's own digest and size (`596d1368…` / 1,496 bytes to `2081ae90…` / 1,966 bytes) at `/agents/subject/harness/skills/0`.
- All four are graded `controlled_with_warnings`, score valid, evidence complete, accepted, P1.
- The one warning: `model_revision_discoverable` (`src/techtree/receipts/compare.py`). The worker ledger records it as the sole reason the status is `controlled_with_warnings` — the provider publishes no revision for qwen/qwen3.7-flash, so both variants are known to have used the same model identifier and not the same model build. The shipped Campaign declares `revision: null` honestly.

**Limitation.** Known derived description delta, plus one accepted warning. Mounting a Skill necessarily changes one tool description, because the harness renders the index of visible Skills into its own skill_manage tool description; that one difference is permitted by name in src/techtree/receipts/compare.py (SKILL_INDEX_TOOL) and a second differing description is refused. Separately, the provider exposes no immutable revision for the selected model alias, so every release comparison is controlled_with_warnings rather than controlled (decision 0007 R5). The comparison is over what the engine recorded, not over independent observation of the containers.

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

- Proof bundle payload digests, one per final-lineage comparison: `sha256:f41e5135…`, `sha256:cee88ccf…`, `sha256:9827854d…`, `sha256:7f540adc…`. Each bundle carries 72 signed episode receipts, 36 per variant — counted in this refresh, 288 in total, every one carrying its own payload digest and Ed25519 signature.
- Every one of the 288 reports `evidence_status: complete` and `score_status: valid`, and names its own task hash, trace digest and reward.
- `uv run techtree proof verify` on each of the four bundles reports 339 checks all passed, of which 84 are stored file digests and 225 are signatures.

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

- Each final-lineage bundle carries the executor public key it was signed with and a `root_report_digest` equal to that run's report file digest — checked in this refresh for all four (`5ad470aa…`, `f002a836…`, `e3855700…`, `74c26dd1…`).
- Executor key ids observed: `sha256:ce372029…` (the stability #1 home, reused for the v1-vs-v2 run because that run was prepared from stability #1's own result), `sha256:8131c7bf…` (stability #2), `sha256:61a5cf45…` (engine reference) — each home generated its own local key.
- All four report `proof_grade: P1`, and the verifier's own output states what P1 means: "integrity-bound, participant-attested local execution", alongside the standing warning that nobody else has run the comparison and no platform witnessed it.

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

**Live evidence**

- Every final-lineage comparison carries a signed ComparisonExecutionRecord inside its bundle (payload digests `sha256:f2defd94…`, `sha256:566b0b15…`, `sha256:ae4b0f19…`, `sha256:87b4519c…`), and each one reports, for **both** variants, `cost_usd: null` with provenance `unavailable` and the detail "no cost figure was reported for this variant, and this build pins no price to compute one from". The product's own record claims nothing it was not told.
- What each record does carry, measured: per-variant `usage` with provenance `normalized_traces` (36 traces with usage out of 36, both sides, all four runs), model-call counts, elapsed seconds, start and finish instants, launch skew, overlap, argv digest, resolved-config digest and raw-trace digest. Example, stability #1: baseline 385 model calls / 891.15 s, candidate 74 model calls / 424.43 s, launch skew 1.65 ms, schedule `parallel_variants`.
- The dollar figures in this document are worked out, not billed: recorded tokens at the rate card in `release/price-profile.json`. Quiet-window total USD 0.5429 on the uncached basis (0.3636 if cached input is charged at zero); programme USD 4.2487 of the 15.00 cap, per `certification-evidence/recert-0025/NOTES.md`.
- The one provider-reported cost anywhere in this lineage is the host completion that produced Skill v2: USD 0.0376, reported by the provider in its own response body (see scope-02).

**Limitation.** Provider revision unavailable, and cost is not a billed figure. Cost and timing are attributed to a model alias, not to a pinned immutable provider revision, because the provider does not expose one (accepted v0.1 warning model_revision_unavailable, decision 0007 R5). For the certified subject runs the product reports cost as unavailable and says why; every dollar figure in this document is derived from recorded tokens and a rate card recorded on 2026-08-20, and is only as current as that record. No public surface may state a price, a running total or a spending cut-off.

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

**Live evidence**

- Data policy `sha256:6c532a43d595286a…` — recomputed in this refresh from src/techtree/resources/catalog/data-policies/hello-world-climb.json; the shipped Campaign commits to it, and it appears in every one of the four reports, every one of the four bundles and all 288 episode receipts of the final lineage.
- The v1-vs-v2 comparison, which runs a derived Campaign, carries the same policy digest — the rights the source run was carried out under still govern the derived one, and its prepare record says so in plain words.
- Acknowledgement: every final-lineage run records `policy_acknowledgement_method: explicit_cli_review` in its start record, and the summary the participant had to accept is carried in the prepare record verbatim ("You own the candidate skill and everything this run produces… Uploading raw episodes to a server is prohibited. Training on raw episodes is prohibited…").
- `push = false` in every resolved engine configuration of the certification, and `--no-push` on the argv of every eval invocation — read in this refresh from `verifiers/<variant>/run/config.toml` and `verifiers/<variant>/dry-run/command.log`.

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

**Live evidence**

- This refresh ran `uv run techtree proof verify <run-dir>/proof` against all four final-lineage bundles, from the stored bytes in the durable evidence, and each returned **verified, 339 checks, every one passed**: files and key present; 84/84 stored file digests; 18/18 linkage and control; 225/225 signatures; aggregate recomputation passed; 2/2 publication; 8/8 proof-grade conditions.
- The rendered result of each verification says, in the product's own words, "This proof verifies: 339 checks, all from the stored bytes, with nothing fetched", and carries the standing warning "No independent reproduction: nobody else has run this comparison, and no platform witnessed it."
- Bundle payload digests verified against: `sha256:f41e5135…`, `sha256:cee88ccf…`, `sha256:9827854d…`, `sha256:7f540adc…`.

**Limitation.** No honest-compute proof. Verification establishes internal consistency, signature validity and that nothing was altered after the run. It cannot establish that the computation was performed honestly, and the execution has not been independently reproduced.

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

- Each of the four final-lineage comparisons records exactly **one** `run.approved` audit event in its own journal — counted in this refresh across all four `events.jsonl` files — naming the actor, the instant and the draft digest that was approved.
- Every one of the four names actor `operator_via_flag` and method `explicit_cli_review`: the certification operator approved each run on the CLI's own explicit-review surface, before dispatch, one approval per run. These runs did not exercise the host-agent surface.
- The paid-run warning the operator had to pass is carried in each start record: "This run evaluates the agent for real and spends money on model calls with prime. What you pay is whatever that provider charges."
- Host-agent approval evidence exists, but for the guided-revision proposal rather than for these four runs: `release/acceptance/terminal-e2e.json` records the surface rendered before dispatch with 0 host calls, 0 outbound requests and 0 CLI reads at the moment of approval, and the run recording actor `human_via_hermes`, method `host_agent_confirmation`. That journey ran on the superseded ReleaseCore `90cd8ad6…`, and is cited here as evidence about the approval surface, not about the shipped lineage's runs.

**Limitation.** Surface attestation. The run records which surface the answer was given on and which actor gave it, as attested by that surface. Nothing cryptographically binds a human being to the approval, and Techtree cannot tell an operator typing 'yes' from anything else that reaches that surface. In the certified runs the approver was the certification operator using the CLI flag, not a first-time participant using the host agent.

**Gaps (findings, not fixed here)**

- All four certified comparisons were approved on the CLI's explicit-review surface (`operator_via_flag` / `explicit_cli_review`). No run of the shipped lineage carries a host-agent approval; that surface is exercised only in the WP11e journey, which ran on the superseded ReleaseCore `90cd8ad6…`.

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

- `run_ba3998e2a0d94126bc7426d0c6b32aab`, the deliberate worker-SIGKILL injection of the final lineage: the run tree has **no report directory and no proof directory**, its state is stuck at phase `running_variants` because a SIGKILLed worker cannot write its own terminal state, and no UpliftReport was produced. Read in this refresh from the run directory itself and from `release/orphan-bound-analysis.json`.
- The same injection is the containment evidence: both supervision records say `parent_lost`, all four recorded subject container ids were gone 0.545 s after the kill with none surviving, the whole tree was down 1.081 s after the kill, `escalated_to_sigkill: false`, and the residual recorded provider cost was USD 0.0007 over one completed episode.
- `run_4fae4473bd1546a0a245fd9c41b898ff`, a pre-committed canonical run against the same Campaign: phase `failed`, error `variant_execution_failed`, message "the baseline evaluation did not finish; a comparison needs both sides, so the pair failed and the partial evidence was kept". No report, no bundle, no score; USD 0.1445 spent and recorded rather than hidden.
- `run_37647dbe3aa84494a791f0f6a460da50`: the same failure mode on the previous attempt (baseline reached the then-1,800-second deadline at 1,803.7 s with 35 of 36 episodes finished, candidate having completed cleanly 25 minutes earlier), USD 0.1685, no report.
- `run_2f264fc8a7c841e49e6cdc763162915a`: refused before dispatch with `worker_executable_not_found`. Nothing ran and nothing was charged.

**Limitation.** No Uplift receipt. A failed run yields no report and no proof bundle. The participant gets an honest failure and a preserved run record, but the provider spend already incurred is not recovered. A SIGKILLed worker additionally cannot record its own terminal state, so such a run stays at the phase it had reached rather than being marked failed.

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

- `run_ede1fd20186d43c68386a53501396fb5` — the replacement comparison of the final lineage, on derived Campaign `sha256:5105b91c8b610c85…`, report `sha256:74c26dd1…`, bundle payload `sha256:7f540adc…`, 23/36 -> 24/36, 1 win / 0 losses / 35 ties, USD 0.0558 on the uncached-rate basis.
- Parent Skill v1 tree `sha256:596d1368…` (SKILL.md 1,496 bytes) versus candidate Skill v2 root `sha256:2081ae90…` (SKILL.md `sha256:0beea6ec…`, 1,966 bytes, 48 lines, name `frozen-v2`, `parent_skill_digest sha256:596d1368…`, `source_kind: manual`) — read in this refresh from the run's own draft artifact.
- The report's manifest comparison records exactly two entries, both on the same skill slot: the digest and the size. Nothing else differed.
- The derivation is recorded rather than assumed: the fingerprint notes that an uplift comparison cannot run the shipped Campaign verbatim because its baseline arm carries no Skill, and that `5105b91c` differs from `ad393bc0` only in the baseline arm's Skill and the mutation-contract kind (`skill_replacement`).

**Limitation.** The certified replacement run compared two single-file bundles. No paid certification run has compared a multi-file bundle pair; full-tree hashing, per-file mounting, root-digest comparison and the exactly-one-component-changed check are covered by automated tests only. Also note this is the explicitly-supplied path, which is separate from what the guided improver can produce (see scope-02).

**Gaps (findings, not fixed here)**

- No live-evidence artifact exists for a multi-file bundle pair. Coverage for that case is tests/integration/test_multi_file_skill.py alone.

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
- `tests/plugin/contract/test_one_generation_request.py::test_the_guided_proposal_makes_exactly_one_request`
- `tests/plugin/contract/test_one_generation_request.py::test_a_second_ask_is_refused_before_it_reaches_the_provider`
- `tests/plugin/contract/test_one_generation_request.py::test_an_unusable_answer_is_not_repaired_by_a_second_request`
- `tests/plugin/contract/test_one_generation_request.py::test_a_transport_failure_is_counted_and_not_retried`
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

- The one authorised final proposal (decision 0028 ruling 1), read in this refresh from the stored request and response bodies at `certification-evidence/wp11e-recert-2026-08-20/host/record-a3/`: model z-ai/glm-5.2, temperature 0, `max_completion_tokens` 32,768, strict `json_schema` structured output, **one** generation request, zero repairs, zero transport retries. Provider response id `a2e008cb1b5e138a-SJC`, finish reason `stop`, 5,133 prompt / 6,501 completion tokens (3,834 of them reasoning), provider-reported cost USD 0.0376. Request digest `sha256:3347f071…` and response digest `sha256:30e1dc37…`, both recomputed here from the stored bodies.
- It produced Skill v2: SKILL.md `sha256:0beea6ec…`, 1,966 bytes, 48 lines, tree root `sha256:2081ae90…`, parent `sha256:596d1368…` — the same bytes the final lineage later re-executed.
- Evaluated under the final lineage exactly once, in `run_ede1fd20186d43c68386a53501396fb5`: 23/36 -> 24/36, 1 win / 0 losses / 35 ties. Decision 0029 required this comparison to be **re-executed and never re-proposed**; the draft's `source_kind: manual` and the absence of any second host call in the quiet window are what that looks like in the evidence.
- Deferred multi-file items stand (decision 0022 §2): `skills/starter.py` `_stage_document` fetches only a single SKILL.md, and `uplift/source.py` exposes only `entrypoint_text` to the host.

**Limitation. The flow is certified; the improvement is not, and the no-measured-uplift rule still holds — the final lineage strengthens it rather than changing it.** The one measured change is +1 task, and that sits inside the run-to-run spread of the *unchanged* v1 Skill measured under this very Campaign: v1 scored **24/36** in stability #1, **23/36** in stability #2, and **23/36** as the baseline arm of the v1-vs-v2 comparison — three executions of an identical arm, spread 23-24. A +1 cannot be distinguished from that. Separately and disclosed: the same frozen v2 bytes, evaluated once under the superseded lineage in `release/acceptance/terminal-e2e.json`, produced a delta of exactly **0.0** (0 wins / 0 losses / 36 ties). So the two executions of this Skill pair that exist measured +1 and 0. No measured-uplift claim is made or permitted, and none of these numbers may appear in public copy. The 0013 §4 demo target (>=32/36, >=6 task uplift) was not met; 0013 already designates that a calibrated aim rather than a guarantee. Release copy states the calibrated 20-27/36 band, never an exact score. Per decision 0028 the feature ships labelled experimental, with no published reliability rate. In v0.1 the improver can only edit the entrypoint, so auxiliary files are always inherited byte-identical from the parent Skill; no copy may claim the guided improver revises multi-file bundles.

## Extension rows — public copy claims beyond the 13

The contract says to extend if public copy claims more, and its stop condition is any public claim with no implementation row. The authoritative v0.1 description (spec §18, adopted by decision 0013 §1) makes four claims the thirteen required rows do not cover on their own. They are added here so the stop condition does not fire.

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
- `tests/unit/test_release_bootstrap.py::test_a_wrapper_that_names_this_release_verifies`
- `tests/unit/test_release_bootstrap.py::test_a_wrapper_naming_another_starter_skill_fails_alone`
- `tests/unit/test_release_bootstrap.py::test_an_install_command_that_does_not_pin_the_version_fails_alone`
- `tests/unit/test_release_bootstrap.py::test_an_install_command_that_does_not_pin_the_interpreter_fails_alone`
- `tests/unit/test_release_checks.py::test_a_recut_campaign_fails_only_the_harness_check`
- `tests/contract/test_release_artifacts.py::test_the_committed_artifacts_are_the_ones_this_tree_produces`
- `tests/contract/test_release_artifacts.py::test_this_build_carries_the_release_it_is_published_as`
- `tests/contract/test_release_copy.py::test_no_copy_says_no_account_is_required`
- `tests/contract/test_release_copy.py::test_the_techtree_scoped_account_claim_is_still_allowed`

**Live evidence**

- ReleaseCore `sha256:c037f4578134185cc22717908bce58749bbb5086536fc955881a2b831abd8530` — recomputed in this refresh and byte-identical in techtree-python/release/release-core.json, src/techtree/resources/release/release-core.json and techtree-plugin/release-core.json. Every field is concrete; the placeholder machinery of the earlier editions no longer exists (decision 0026).
- `release/fresh-install-report.json` — verdict PASS, no failures, on the candidate wheel `techtree-0.1.0-py3-none-any.whl` `sha256:5a402a43…` built from commit `a3ea8c58…`. The installed build reports `release_core_digest sha256:c037f457…`, catalog `sha256:ae300ef6…` and engine `sha256:874cbae0…` back through `techtree release info --json`.
- `release/wheel-inspection.json` — verdict PASS, no findings; the packaged lineage inside the wheel is Campaign `ad393bc0…` with the enforced budgets 44 / 900,000 / 16,000 / USD 2.50, and the build-provenance stamp names commit `a3ea8c58…`.
- `release/plugin-release-candidate.json` — plugin commit `d1d993e73160e7aa3f6739f0b871a425736a7605`, worktree clean, plugin doctor passed (10 checks, all ok), carrying ReleaseCore `sha256:c037f457…`.
- The staged BootstrapRelease in techtree-ash (`priv/releases/climb-v0.1.0/bootstrap.json`) carries the same wheel digest, the same plugin commit and a ReleaseCore byte-identical to the two above; its own checksums file names the same starter-skill file and tree digests.

**Limitation.** Not yet installed from published coordinates. The fresh-install report installed the candidate wheel from `dist/` through `--find-links`, because nothing is published: decision 0028 §8 keeps repositories, tags and install coordinates private until the founder's Gate-2 phrase, and this document cannot source the website's live release pointer from any committed artifact. The public-coordinate smoke is a post-Gate-2 step. A Prime or provider account, an API credential and network access are still needed for inference, installation and image retrieval — only a Techtree account is not. One recorded install observation stands: left to choose for itself, uv 0.10.2 built the tool environment on Python 3.14.7, which the package declares unsupported; the published command pins the interpreter (decision 0034), and the CLI refuses an unsupported interpreter rather than passing silently.

**Gaps (findings, not fixed here)**

- The fresh install was performed against the candidate wheel in `dist/` through `--find-links`, not from published coordinates, because nothing is published before Gate 2. The website's live release pointer is not readable from any committed artifact, so this document does not state it.

### ext-02 — The result is shown deterministically and the explanation is guarded

**Public wording.** The result is shown through deterministic Rich or compact output and a guarded founder-supplied explanation Skill. It states the band, never an exact score, and it always states its own limits.

**Implementation**

- `src/techtree/presentation/build.py` — the payload built from the verified report; the proof grade is read, never hardcoded
- `src/techtree/presentation/rich.py`, `src/techtree/presentation/compact.py` — the two renderings
- `src/techtree/presentation/sanitize.py` — the recursive scrubber
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
- `tests/unit/test_presentation_sanitize.py::test_a_payload_carrying_a_credential_is_refused`
- `tests/unit/test_presentation_sanitize.py::test_a_payload_naming_a_private_path_is_refused`
- `tests/plugin/unit/test_guards.py::test_a_narrative_may_not_restate_a_canonical_value`
- `tests/plugin/unit/test_guards.py::test_a_narrative_embedding_a_digest_is_refused`
- `tests/plugin/unit/test_guards.py::test_a_narrative_may_not_claim_what_is_not_true_of_a_local_run`
- `tests/plugin/unit/test_guards.py::test_saying_it_was_not_reproduced_is_fine`
- `tests/contract/test_release_copy.py::test_no_copy_claims_somebody_else_verified_the_run`
- `tests/contract/test_release_copy.py::test_no_copy_calls_the_subject_the_readers_own_model`
- `tests/contract/test_release_copy.py::test_no_copy_frames_the_result_as_a_benchmark_that_was_passed`
- `tests/contract/test_release_copy.py::test_the_result_says_what_it_does_not_establish_in_the_lines_that_lead`

**Live evidence**

- The proof grade travels in the report and is read from it: all four final-lineage reports carry `proof_grade: P1`, and the verification this refresh ran renders the grade's meaning from the verified report — "P1 means integrity-bound, participant-attested local execution" — together with the standing no-independent-reproduction warning, rather than from any label attached to a comparison.
- Each report also carries `publication_eligible: false` and `statuses.publication: not_requested`, and each verification reports the publication checks 2/2 passed: "Not published: publication was never requested, nothing was uploaded, and this report is not publication eligible."
- The copy guards are executable and were run in this refresh as part of `tests/contract` (454 passed), including the band, exact-score, account, attestation, own-model, benchmark, price and clock rules.

**Limitation.** The explanation Skill is guarded, not verified. The guards refuse numbers, digests, commands, escape codes, credentials and any claim untrue of a local run; they cannot establish that the remaining prose is a good explanation. The deterministic guard surface has been narrowed since the first certification (recorded in `release/security-review.json` as a guard-deletion history: what was removed produced false positives rather than catching real cases), so the guarantee is the current rule set, not the widest one that ever existed. The subject model is a pinned model the Campaign chooses (qwen/qwen3.7-flash), not the reader's own model, and it is distinct from the host operator model that writes the narrative.

### ext-03 — The proposed Skill v2 is shown and scanned before approval

**Public wording.** Techtree shows the proposed Skill v2 and scans it before the participant is asked to approve it.

**Implementation**

- `src/techtree/skills/scanner.py` — whole-tree enumeration, media types, findings
- `src/techtree/skills/policy.py` — the frozen v0.1 instruction-Skill policy
- `../techtree-plugin/diff.py` — the deterministic diff shown to the participant
- `../techtree-plugin/services/proposal.py` — scan, snapshot, diff, then approval

**Automated test**

- `tests/unit/test_skill_scanner.py::test_default_policy_matches_the_v01_instruction_skill_rules`
- `tests/unit/test_skill_scanner.py::test_policy_is_frozen`
- `tests/unit/test_skill_scanner.py::test_credential_shapes_are_blocking`
- `tests/unit/test_skill_scanner.py::test_a_blocking_finding_stops_the_scan`
- `tests/unit/test_skill_scanner.py::test_a_finding_carries_no_matched_text`
- `tests/unit/test_skill_scanner.py::test_findings_report_the_relative_path_not_the_participants_directory`
- `tests/unit/test_skill_scanner.py::test_scanning_the_same_content_twice_gives_the_same_answer`
- `tests/unit/test_skill_scanner.py::test_binary_content_under_a_text_suffix_is_refused`
- `tests/plugin/integration/test_one_turn_revision.py::test_the_diff_is_shown_with_the_policy_and_the_estimate`
- `tests/plugin/integration/test_one_turn_revision.py::test_the_plugin_keeps_no_copy_of_the_proposed_skill`
- `tests/plugin/integration/test_one_turn_revision.py::test_the_approved_call_does_exactly_what_was_described`

**Live evidence**

- The proposal that produced the Skill the shipped lineage carries was scanned and diffed before approval: `release/acceptance/terminal-e2e.json` records, for that exact host call (`a2e008cb1b5e138a-SJC`), the CLI Skill-scanner verdict `accepted`, the plugin guards verdict `accepted`, `secret_assignment_raised: false`, `presentation_claim_forbidden_raised: false`, `workaround_applied: false`, and a snapshot naming baseline skill `sha256:596d1368…` and candidate `sha256:0beea6ec…`, 1,966 bytes, one included file.
- The diff shown before approval is recorded as four changes, all inside the procedure and the output contract, and the session stage after the call is `second_draft_prepared` — the proposal prepared a comparison and started nothing.
- Approval state at the moment of dispatch: 0 host calls, 0 outbound requests, 0 CLI reads.

**Limitation.** Mechanical scan only, and the scan evidence predates the shipped Campaign. The scanner checks structure, media types, size, hidden and symlinked paths, credential shapes and copied task material; it does not judge meaning. The proposal, scan, diff and approval happened once, on 2026-08-20, on the superseded ReleaseCore `90cd8ad6…`; decision 0029 then required the comparison to be re-executed under the new Campaign without re-proposing, so the shipped lineage contains the re-execution of that proposal and not a fresh one. Decision 0023 §5 rules out an LLM-based semantic Skill scanner in v0.1, and the Skill-conflict-scan limitation is recorded in `release/security-review.json` against a v0.2 design brief.

**Gaps (findings, not fixed here)**

- The proposal, scan, diff and approval happened once, under the superseded ReleaseCore, and were deliberately not repeated: decision 0029 required the v1-vs-v2 comparison to be re-executed and never re-proposed. The shipped lineage therefore contains a re-execution of that proposal, and the scan evidence for it is a superseded-lineage artifact.

### ext-04 — Nothing is uploaded to the website

**Public wording.** Techtree does not upload the participant's Episodes, Traces, receipts, proof bundles or Skill proposals. Model inference is still sent to the selected model provider under that provider's policies.

**Implementation**

- `src/techtree/verifiers/config.py`, `src/techtree/verifiers/child.py` — push disabled at both the file and command-line layers
- `src/techtree/verifiers/verify.py` — the push check over the resolved configuration
- `src/techtree/presentation/sanitize.py`, `src/techtree/errors.py` — recursive scrubbing of anything rendered
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
- `techtree-ash/test/techtree_web/router_test.exs::"every route is a read"`
- `techtree-ash/test/techtree_web/router_test.exs::"no submission, artifact, proof, run, or login route exists"`
- `techtree-ash/test/techtree_web/router_test.exs::"a published address answers a mutating method with 405, not 404"`
- `techtree-ash/test/techtree_web/endpoint_test.exs::"a file in a multipart body is never read into a parameter"`
- `tests/plugin/contract/test_plugin_doctor.py::test_the_runtime_cannot_open_a_connection`
- `tests/plugin/contract/test_plugin_doctor.py::test_no_relay_dependency_exists`

**Live evidence**

- The three-method no-upload proof the release requires has now been executed (contract wp11g): the static route audit, the instrumented application-level method log (`release/network-method-log.json`) and the end-to-end destination capture (`release/destination-capture.json`), all recorded 2026-08-23 and summarised in `release/security-review.json`.
- The product made **one** request to techtree.sh across its whole non-paid command surface, and its method was GET — a read of a content-addressed object. Zero unexpected destinations were observed across all three legs; every non-loopback peer seen belongs to the expected list. The instrument was proved alive by a deliberate loopback GET that it recorded.
- In the certification runs themselves: `push = false` in every resolved engine configuration, and `--no-push` on the argv of every eval invocation — read in this refresh from run_06b2377d…'s own `verifiers/<variant>/run/config.toml` and `verifiers/<variant>/dry-run/command.log`. A flag on argv overrides whatever the file says, so the two layers agree by construction.
- The proof bundles themselves record the negative: `publication_eligible: false`, `statuses.publication: not_requested`, and the verifier's publication checks passing 2/2 on all four.

**Limitation.** The claim is about the Techtree website and the Verifiers platform, not about the network. Model inference goes to the selected provider under that provider's policies, and installation and container image retrieval need network access. The destination capture states its own limit: the sampler is a poll rather than a capture, so it supports "this peer was never observed" and not "no byte ever left"; it is the static audit that establishes there is no upload code path to exercise.

## Summary table

| # | Claim | Implementation (lead module) | Automated test (lead) | Live evidence (lead) | Limitation (short) | Gap |
|---|---|---|---|---|---|---|
| claim-01 | Campaign immutable | `src/techtree/models/base.py` | `tests/unit/test_canonical.py::test_protocol_models_are_frozen` | Campaign hello-world-climb sha256:ad393bc0, in every report and all 288 receipts | 'Campaign' is an internal protocol concept; a participant never names one | no |
| claim-02 | Same tasks on both sides | `src/techtree/models/validation.py` | `tests/unit/test_taskset_membership_logic.py::test_the_membership_digest_is_the_digest_of_the_named_ordered_object` | Membership sha256:56f697fb, read from proof/taskset-lock.json | Fixed membership: one 36-task selection, no sampling or rotation | no |
| claim-03 | Taskset validated before it is used | `src/techtree/models/validation.py` | `tests/integration/test_taskset_validation.py::test_every_task_passes_gold_and_setup` | Validation receipt sha256:080895d5, hashed out of the proof bundle | Mechanical only; the wrong-answer control is a test, not a receipt check | no |
| claim-04 | Neutral baseline | `src/techtree/manifests/builder.py` | `tests/unit/test_manifest_builder.py::test_the_baseline_preserves_the_campaign_and_carries_no_skill` | Baseline 0/36 in run_06b2377d, run_8fdfdcf6 and run_ad759a00 | Toy task | no |
| claim-05 | Clean subjects | `src/techtree/verifiers/config.py` | `tests/unit/test_verifiers_config.py::test_a_runtime_other_than_docker_cannot_be_named` | 288 receipts, all naming resolved image sha256:90744cff | Local executor | yes |
| claim-06 | Only the Skill changed | `src/techtree/manifests/compare.py` | `tests/unit/test_observed_comparison.py::test_an_unauthorized_observed_difference_is_invalid` | Four reports, controlled true, zero violations, one allowed difference each | Known derived description delta, plus one accepted warning | no |
| claim-07 | Per-task receipts | `src/techtree/receipts/episode.py` | `tests/unit/test_episode_receipt_builder.py::test_every_committed_task_gets_exactly_one_receipt` | Four bundles, 72 signed receipts each | Internal evidence | no |
| claim-08 | Signed report | `src/techtree/crypto.py` | `tests/unit/test_crypto.py::test_sign_and_verify_round_trip` | Report digests and executor public keys in each bundle | Participant-attested | no |
| claim-09 | Cost and timing are recorded honestly | `src/techtree/receipts/execution.py` | `tests/unit/test_comparison_execution_record.py::test_a_cost_figure_cannot_be_carried_without_a_provenance` | Four signed execution records, cost provenance unavailable on both sides of each | Provider revision unavailable; cost is worked out, never billed | no |
| claim-10 | Data policy is committed and enforced | `src/techtree/models/data_policy.py` | `tests/unit/test_data_policy.py::test_public_report_against_a_private_policy_is_rejected` | Data policy sha256:6c532a43, in every report, bundle and receipt | Fixed v0.1 policy | no |
| claim-11 | Offline verification | `src/techtree/receipts/verify.py` | `tests/unit/test_local_bundle_verify.py::test_a_complete_proof_verifies_offline` | `techtree proof verify` run here on all four bundles: 339/339 passed | No honest-compute proof | no |
| claim-12 | Explicit approval before anything is spent | `src/techtree/runs/service.py` | `tests/plugin/unit/test_approvals.py::test_the_plugin_issues_no_approval_of_its_own` | Exactly one run.approved event per run, actor operator_via_flag | Surface attestation; the certified approvals were CLI, not host-agent | yes |
| claim-13 | An incomplete comparison fails closed | `src/techtree/runs/real.py` | `tests/unit/test_episode_receipt_builder.py::test_a_missing_task_is_an_episode_count_mismatch` | run_ba3998e2 (killed, no report), run_4fae4473 and run_37647dbe (failed at the deadline) | No Uplift receipt | no |
| scope-01 | Skill-bundle v1-vs-v2 comparison is supported when both bundles are supplied explicitly | `src/techtree/skills/scanner.py` | `tests/integration/test_multi_file_skill.py::test_the_draft_holds_the_whole_tree` | run_ede1fd20 on derived campaign sha256:5105b91c, 23/36 -> 24/36 | The certified replacement run compared two single-file bundles | yes |
| scope-02 | Guided revision is single-SKILL.md in v0.1; the flow is certified and no measured uplift is claimed | `src/techtree/uplift/source.py` | `tests/unit/test_verified_source_skill.py::test_the_entrypoint_text_comes_back_with_what_it_was_verified_against` | One host completion, response a2e008cb1b5e138a-SJC, producing SKILL.md sha256:0beea6ec | The flow is certified; the improvement is not | no |
| ext-01 | One pinned plugin installs and verifies Techtree | `../techtree-plugin/bootstrap.py` | `tests/plugin/unit/test_bootstrap.py::test_a_missing_cli_produces_one_exact_plan` | ReleaseCore sha256:c037f457 identical across three repositories; fresh-install PASS | Not yet installed from published coordinates | yes |
| ext-02 | The result is shown deterministically and the explanation is guarded | `src/techtree/presentation/build.py` | `tests/unit/test_presentation_build.py::test_the_same_report_builds_the_same_bytes` | All four reports carry P1 and publication_eligible false; the grade is rendered from the verified report | The explanation Skill is guarded, not verified | no |
| ext-03 | The proposed Skill v2 is shown and scanned before approval | `src/techtree/skills/scanner.py` | `tests/unit/test_skill_scanner.py::test_default_policy_matches_the_v01_instruction_skill_rules` | Scanner and guard verdicts accepted for the proposal that produced SKILL.md sha256:0beea6ec | Mechanical scan only; the scan predates the shipped Campaign | yes |
| ext-04 | Nothing is uploaded to the website | `src/techtree/verifiers/config.py` | `tests/unit/test_verifiers_verify.py::test_a_resolved_config_that_would_upload_fails_the_push_check` | One techtree.sh request across the whole surface, method GET; zero unexpected destinations | The claim is about the website and the Verifiers platform, not the network | no |

## Gap register

Every cell below is an honest gap: the claim holds, but a specific artifact or a specific named test that the contract asks for does not exist yet. None of these was invented around, and none is fixed by this refresh.

1. **claim-05 — Clean subjects.** The `platform` field is null in all 288 final-lineage receipts, so the per-platform manifest digest is a declared pin checked by a preflight test, not something the certified runs recorded. Separately, no trace-level artifact is committed to this repository: the traces exist in the durable evidence and their digests are committed inside the signed receipts, but the only committed trace-level bytes are the sanitized fixture from run_6ce5e56a7dd341bca8bc6de1d6a60027, which belongs to the superseded Campaign.
2. **claim-12 — Explicit approval before anything is spent.** All four certified comparisons were approved by the certification operator on the CLI's explicit-review surface (`operator_via_flag` / `explicit_cli_review`). The host-agent approval surface is exercised in the WP11e journey, which ran on the superseded ReleaseCore `90cd8ad6…`. No run of the shipped lineage carries a host-agent approval.
3. **scope-01 — Skill-bundle v1-vs-v2 comparison is supported when both bundles are supplied explicitly.** No live-evidence artifact exists for a multi-file bundle pair. Coverage for that case is tests/integration/test_multi_file_skill.py alone.
4. **ext-01 — One pinned plugin installs and verifies Techtree.** The fresh install was performed against the candidate wheel in `dist/` through `--find-links`, not from published coordinates, because nothing is published before Gate 2. The website's live release pointer is not readable from any committed artifact, so this document does not state it.
5. **ext-03 — The proposed Skill v2 is shown and scanned before approval.** The proposal, scan, diff and approval happened once, under the superseded ReleaseCore, and were deliberately not repeated: decision 0029 required the v1-vs-v2 comparison to be re-executed and never re-proposed. The shipped lineage therefore contains a re-execution of that proposal, and the scan evidence for it is a superseded-lineage artifact.

## Figures the previous edition stated that this refresh could not source in the final lineage

Recorded rather than substituted, as the refresh required.

1. **The five first-certification run identifiers and everything derived from them** — `run_d9409450…`, `run_a6c608b9…`, `run_6ff833ca…`, `run_9f2a5025…`, `run_e29f1781…`, their report digests (`47253518…`, `784614a1…`, `c1a88d20…`, `5668a0f1…`, `421f1a0b…`), bundle digests (`19493177…`, `faa8260e…`, `d32c7dca…`, `c7b76024…`, `4db83924…`) and costs (0.1780, 0.1709, 0.1827, 0.1702, 0.0551). Superseded. Not carried; replaced by the five final-lineage runs.
2. **Derived campaigns `b9e3f00c…` and `f2f04ae5…`** — superseded by `ad393bc0…` and its uplift derivation `5105b91c…`.
3. **Catalog Campaign `5aef3fb7…`, Climb `61a7dd46…`, catalog `468e8ab1…`, ReleaseCore `80807821…`** — the pre-0025 coordinates the previous edition recorded as verified. Not carried.
4. **Skill v2 root `b143866e…`, SKILL.md `7cc03c89…`, 1,907 bytes, 47 lines** — the Gate-1 rehearsal's v2. The shipped lineage carries a different Skill: root `2081ae90…`, SKILL.md `0beea6ec…`, 1,966 bytes, 48 lines.
5. **The Gate-1 rehearsal host call** — request `12e1aa49…`, response `69d0657e…`, response id `a2b2c61f2a1fb1b4-SJC`, 5,139 in / 7,400 out, USD 0.0417. Superseded by the 2026-08-20 final attempt recorded in scope-02.
6. **"USD 1.9717 of the 3.00 programme cap"** and the estimated ledger entry disclosed with it (rehearsal attempt 3, ~USD 0.0010, bounded 0.0023). The cap is now 15.00 and the programme total 4.2487; the estimated entry has no counterpart in the final lineage and is not carried forward.
7. **"USD 0.5037 of pre-change spend bought no comparison", and the four failed run identifiers `run_a8da75d4…`, `run_af675e08…`, `run_8f46f6c9…`, `run_28261de5…`.** Superseded; claim-13 now cites final-lineage failures instead.
8. **"Both variants of each run resolved to the same platform-specific image digest."** Not sourceable from the final-lineage receipts, whose `platform` field is null. Replaced with what those receipts do establish: the same image index digest on all 288 episodes.
9. **The Gate-1 §3 immutability method and its result.** Rather than carry the old attestation, this refresh re-ran the check itself over the four final-lineage run trees; the result is stated in claim-01.
10. **"102 implementation paths and 255 test citations."** Recounted for this edition: 74 and 259.

## Corrections — things the previous edition got wrong rather than merely stale

1. **Every plugin test citation pointed at a path that does not exist.** Thirty-nine citations were written as `techtree-plugin/tests/…`; the plugin's tests and tooling live in techtree-python under `tests/plugin/` and `tools/plugin/`, so that the install-time scanner reads no adversarial fixture. Thirty-six of them resolve unchanged at the new path and have been re-pathed and re-verified; the other three had also been renamed and are covered by item 2.
2. **Five cited tests no longer exist.** `test_a_placeholder_release_refuses_the_public_install_flow`, `test_this_build_carries_a_self_declaring_placeholder_release` and `test_a_real_wrapper_over_a_placeholder_release_is_refused` went with the placeholder machinery decision 0026 deleted; `test_a_narrative_may_not_state_a_number` and `test_a_narrative_claiming_a_different_score_is_refused` were replaced by `test_a_narrative_may_not_restate_a_canonical_value` and `test_a_narrative_embedding_a_digest_is_refused`. Live citations replace them; none of the five is carried.
3. **"placeholder_release is still true" was no longer true.** `release/release-core.json` carries no placeholder field at all, and every coordinate in it is concrete. The ext-01 limitation now states the real constraint: nothing is published before Gate 2, so no install from published coordinates has happened.
4. **The claim-09 evidence overstated what the runs record.** The previous edition presented per-run costs as figures the runs carry. In this lineage every signed execution record reports cost as unavailable on both sides; the dollar figures are worked out from recorded tokens and a dated rate card, and the row now says so.
5. **The known-wrong-answer control was attributed to the validation receipt.** The receipt's six checks do not include it; it is an automated test over the taskset. claim-03's limitation now states this precisely.

## Stop conditions

- *Any public claim with no implementation row* — not triggered. The authoritative v0.1 product statement (spec §18) was walked clause by clause; the four clauses not covered by the thirteen required rows are `ext-01`…`ext-04`.
- *Any row whose limitation contradicts public copy* — not triggered. Every limitation above is either already in public copy, already in a binding decision (0007 R5, 0013 §1, 0022, 0023 §4, 0028, 0029, 0033), or a deferral recorded against a ticket.

## Discrepancies noted, not fixed

1. `release/founder-skill-approval-draft.md` still opens with "Status: FINAL, awaiting the founder's Gate-1 approval phrase", but `release/founder-approvals/gate1-founder-skills.md` records that the approval phrase was received on 2026-08-14 against exactly this packet's digest (`sha256:b3ea3ba1…`, recomputed here from the working-tree bytes). The packet header is stale. Reported, not amended — changing those bytes would change the approved digest.
2. The shipped Climb's own prepare-time output describes it as "a development Climb", whose report is "not publication eligible" and whose "result is not comparable evidence", and every certified run carries `publication_eligible: false`. That is consistent with the proof bundles and with the toy framing, but it is a stronger self-description than the rows above discuss, and it is recorded here rather than interpreted.
