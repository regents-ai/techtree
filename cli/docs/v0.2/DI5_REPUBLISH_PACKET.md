# Republish packet: the v0.2 Campaign write path (techtree-di5, WP1.7)

Status: **branch candidate**. Nothing in this packet is a release, a
publication, or permission to publish. Every digest below is what this
worktree generates; Sean confirms or renames the release identity before any
of it reaches main, origin, the plugin, or the website.

Branch `regent/techtree-di5-campaign-write-cutover`, based on
`a5bfba68bdae71bfaa9bb9bc94a963bc34be93f9`.

## 1. What changed in one sentence

The live Campaign write path now produces and consumes one shape,
`techtree.campaign.v2`, which binds its resolved execution plan by digest;
every v0.1 document is read only through the historical boundary, and every
v0.1 record stays byte-identical.

## 2. Release identity (founder-confirmed fields, 2026-09-02)

`release/release-inputs.json` changes in exactly two fields:

| field | v0.1 (history) | candidate |
| --- | --- | --- |
| `release_id` | `climb-v0.1.0` | `climb-v0.2.0` |
| `cli_version` | `0.1.1` | `0.2.0` |

Unchanged on purpose: `intro_climb_reference` (`hello-world-climb@1`),
`minimum_host_hermes_version` and `maximum_tested_host_hermes_version`
(`0.20.1`), the publication network key, `public_log_url`,
`submission_endpoint`, `starter_skill_digest`, `skill_improver_digest`,
`starter_skill_object_url`.

The package version moves with it: `pyproject.toml` and `uv.lock` say
`0.2.0`.

## 3. Regenerated release document

`make release-core` over the regenerated packaged catalog:

| artifact | digest |
| --- | --- |
| `release/release-core.json` (= `src/techtree/resources/release/release-core.json` = `plugin/release-core.json`) | `sha256:f81429367dde864907c40f510aadde6b7e2e5b05c306586129a5fa54f45f612e` |
| `release-core.catalog_digest` | `sha256:edf773ee561c09413d9704046b2d53edff19bc04c0cfbe7d6efee646670a26f3` |
| `release-core.engine_digest` (unchanged) | `sha256:29b1bbb8327d8f1a9ade03ff4504695ad3783ae34aaaa559e5c6bf9fc95e879b` |
| `release-core.subject_hermes_version` (unchanged value, now read from the plan's subject plane) | `0.19.0` |
| `release-core.protocol_version` (unchanged) | `v1alpha1` |

`release/release-core.schema.json` is byte-identical to v0.1 (the ReleaseCore
model did not change). `release/build-info.json` records the new inputs
digest and artifact digests.

## 4. Packaged catalog (`src/techtree/resources/catalog`)

Index schema `techtree.catalog.v2`; one Climb, five objects.

| object | kind | digest |
| --- | --- | --- |
| `climbs/hello-world-climb.json` (`hello-world-climb@1`) | climb | `sha256:10643f2153f4efd55866ca88dfc9f64852073712dadde22857c6fbff6e2d330c` |
| `campaigns/hello-world-climb.json` | campaign (`techtree.campaign.v2`) | `sha256:d5e91926076b69401c25c29868d00dad5c057ca4151a141b58186bb811b9f07c` |
| `execution-plans/hello-world-climb.json` | execution_plan (new object kind) | `sha256:6e3443231e0605c2a07b100507c72bd3c49fa848cf454f79f70666ab922f8eb3` |
| `taskset-validations/hello-world-climb.json` | taskset_validation | `sha256:4944bd71caa1a295e03325b18a7af753d0d8fcf787189c89244209171cda1302` |
| `data-policies/hello-world-climb.json` | data_policy | `sha256:6c532a43d595286a08260481890bbbffa16d1b4dd89465d1cc8395099d9ebcf9` |
| `validation-evidence/hello-world-climb.json` | validation_evidence | `sha256:991be5e42acbd48c6bd9aaf8e1f5a5a2478c0a0e4bf04ad4f2be84b702adee43` |

The Campaign binds the plan by `execution_plan_digest`; the plan's evaluation
plane names the packaged engine bundle (`evaluation.engine_digest` equal to
the publisher validation receipt's `engine_digest`), so the Climb is
preparable. A plan whose engine differs from the receipt's is refused at
prepare (`engine_plan_mismatch`), by the executor, and by the bundle verifier
(`linkage.plan_engine`).

The three digests above moved between the first candidate and this one
because the plan's evaluation field was renamed from `wheel_digest` to
`engine_digest` (section 8a); the bytes it names are unchanged.

## 5. Preserved history (byte-identical, verified with `git diff --quiet HEAD`)

New snapshot `release/history/climb-v0.1.0/` holds exact copies of the four
generated v0.1 release files as they were at the base commit:

| file | sha256 |
| --- | --- |
| `release-inputs.json` | `cdb1f19dab00d1075b239e400e1e7e00dcd4ef755fbc60ab9b7b832e02303b11` |
| `release-core.json` | `07bfd0f0f07c4df08e879c2ff6dbb8e17c6363445e15be62c6ec9549989d67fa` |
| `release-core.schema.json` | `583c8b09665eca0807d45de971791e7e17108686ba271897f61e3ca5e3b45c38` |
| `build-info.json` | `06786fb6b39d2e1bdacf5977e54c0ac28e4ddc139b1595d1b17a2a9167c8bf27` |

The v0.1 `release-core.json` digest above is the one the v0.1 plugin, wheel
and website were verified against. No approval status was carried forward;
the v0.2 candidate has none.

Untouched under `release/` (27 entries): `HANDOFF.md`, `README.md`,
`acceptance/`, `budget-contract-audit.json`,
`certified-scientific-fingerprint.json`, `destination-capture.json`,
`founder-approvals/`, `founder-release-approval-packet.md`,
`founder-skill-approval-addendum-1.md`, `founder-skill-approval-draft.md`,
`fresh-install-report.json`, `hermes-scanner-dossier.md`,
`limit-calibration.json`, `network-method-log.json`,
`orphan-bound-analysis.json`, `plugin-release-candidate.json`,
`post-certification-change-classification.json`, `price-profile.json`,
`product-claim-evidence-matrix.json`, `product-claim-evidence-matrix.md`,
`public-visibility-review.md`, `release-core.schema.json`,
`security-review.json`, `security-review.md`, `skills/`,
`wheel-inspection.json`.

Also untouched: `schemas/v1alpha1/` (28 frozen schemas, re-verified by
`make schemas`); the 16 pre-existing goldens that v2 did not rebuild
(`campaign`, `climb`, `data-policy`, `evidence-artifact-ref`, `evidence-facets`,
`execution-approval`, `executor-identity`, `experiment-baseline`,
`experiment-candidate`, `fake-uplift-report`, `real-episode-receipt`,
`real-uplift-report`, `remote-execution-estimate`, `skill-artifact`,
`taskset-lock`, `taskset-validation-receipt`); the recorded
evidence under `tests/fixtures/receipts/recorded/`; the frozen conformance
submission `tests/fixtures/publication/conformance-submission.json` (its 84
files still verify with the v0.1 outcome through `techtree.historical`);
`UPSTREAM_CONTRACT_LOCK.json`; `platform/` (out of scope, not opened).

## 6. Copies refreshed outside `cli/src`

- `plugin/release-core.json`: the one plugin edit. It is the byte copy of
  the release document the plugin verifies itself against (`make
  check-plugin` fails without it). No plugin code changed; the `plugin/`
  rename Astra deferred is untouched.
- `cli/tests/plugin/fixtures/cli/release-info.json` and
  `release-verify.json`: re-captured from the source tree with
  `techtree release info --json` and
  `techtree release verify --json --no-color --no-input`, the same way the
  decision 0029 captures were made (null `source_commit`, with its warning).
  The other recorded plugin envelopes were not re-captured; the plugin's
  battery passes against them as they are.

## 7. Generated artifacts (`make regenerate`, drift-free under `make generated-check`)

- `schemas/v2/`: 9 schemas, one new (`catalog.schema.json`);
  `execution-plan`, `compatibility-result` and `climb-summary` carry the
  `engine_digest` rename.
- v2 goldens rebuilt over v2 documents: `campaign-parity-candidate`,
  `campaign-v2`, `cli-envelope`, `climb-summary-v2`, `climb-v2`,
  `comparison-execution`, `configuration-comparison`,
  `configuration-compatibility-policy`, `episode-receipt-v2` (now a signed
  envelope), `execution-plan`, `experiment-baseline-v2`,
  `experiment-candidate-v2`, `improvement-context`, `presentation-payload`,
  `run-request-v2`, `uplift-report-v2` (now a signed envelope); new
  `execution-plan-parity`. Signatures use the disposable golden fixture key.
- `tests/fixtures/catalog/complete/`: regenerated, with
  `execution-plans/synthetic.json`.

## 8. WP1.8 follow-ups carried in this candidate

- (a) `compare_manifests` is generalised to v2 and reports an undeclared
  plan move as a "different execution plan" violation
  (`tests/unit/test_manifest_compare.py::test_an_undeclared_execution_plan_move_is_rejected`);
  the configuration-compatibility policy has the sibling
  (`tests/unit/test_configuration_compatibility.py::test_an_undeclared_plan_move_is_incompatible`).
- (b) `CompatibilityResultV2.required_engine_digest` (from the validation
  receipt) and `evaluation_engine_digest` (from the plan) are reconciled:
  the packaged plan, the synthetic fixture plan and the golden plan all name
  the receipt's engine, and a mismatch blocks prepare.
- (c) Signed v2 receipt and report goldens: `episode-receipt-v2.json`,
  `uplift-report-v2.json`.
- (d) `executor_kind` is the only live name; `execution_backend` survives
  only inside the historical v0.1 models and on two internal execution
  records (`receipts/execution.py`, `verifiers/models.py`) that are not
  protocol documents. Flagged in section 10 rather than renamed here.

## 8a. Corrections after Astra's review of the first candidate (2026-09-07)

Astra reproduced three acceptances the first candidate should have refused
(`artifacts/techtree-delivery-audit-2026-09-06/di5-review/reproduce.py`).
Each is now refused, each has a negative test, and the reproduction script
(with `wheel_digest` read as `engine_digest`) reports all three rejected.

- Signed receipts placed elsewhere than the plan. `verify_local_bundle`
  only compared the receipts' `execution_plan_digest`; a bundle whose every
  receipt said `prime_hosted` under a local plan verified. Every receipt's
  `execution_location` is now read against the plan's execution plane
  (`receipt_set.<variant>.execution_location`, `RECEIPT_SET_INVALID`).
  Test: `tests/unit/test_local_bundle_verify.py::test_receipts_placed_elsewhere_than_the_plan_fail_their_receipt_set`.
- A supplied plan the Campaign never bound. `compile_variant_config` (and
  `compile_plans` through it) took `plan` on trust; it now calls
  `bound_execution_plan_digest(campaign, plan)` before anything is compared
  or written. `verify_variant_execution` had the same gap and now refuses a
  plan whose digest is not the manifest's `configuration.execution_plan_digest`
  (`variant_execution_uncheckable`). Tests:
  `tests/unit/test_verifiers_compiler.py::test_a_plan_the_campaign_never_bound_is_refused`
  (nothing written) and
  `tests/unit/test_verifiers_verify.py::test_a_plan_the_manifest_was_not_resolved_under_cannot_be_verified`.
- A plan naming another engine than the validation receipt. Prepare and the
  executor refuse it; the bundle verifier did not. It now records
  `linkage.plan_engine` (`COMPARISON_INVALID`) comparing
  `execution_plan.evaluation.engine_digest` with
  `validation_receipt.engine_digest`. Test:
  `tests/unit/test_local_bundle_verify.py::test_a_plan_naming_another_engine_than_the_receipt_fails_the_linkage`
  (fails as the engine binding, not as a moved plan).
- `EvaluationEngineRef.wheel_digest` renamed to `engine_digest`. The value
  was always the managed engine bundle's content digest (the engine bundle
  installs Verifiers from pinned source and ships no wheel; the descriptor's
  packages carry `source_digest`), and every consumer compares it to the
  bundle digest: the taskset lock, the validation receipt, the installed-
  engine registry, the executor and now the bundle verifier. The inherited
  WP1.8 field `CompatibilityResultV2.evaluation_engine_wheel_digest` had the
  same conflation and is `evaluation_engine_digest`. The Verifiers wheel
  itself stays where it was recorded, in `UPSTREAM_CONTRACT_LOCK.json`
  (`verifiers.wheel_sha256`), unchanged. The rename moves the v2 execution
  plan, compatibility-result and climb-summary schemas, the packaged plan and
  everything that hashes it (section 4), the goldens and the synthetic
  fixture catalog. No v1alpha1 schema, historical document or frozen fixture
  changed.

## 9. Acceptance evidence (model-free)

- One campaign through draft, prepare, run, result and bundle on the v2
  path: `tests/integration/test_fake_run.py`,
  `tests/integration/test_skill_prepare.py`,
  `tests/unit/test_run_artifacts.py`, `tests/unit/test_local_bundle_verify.py`,
  `tests/integration/test_real_result_to_report.py` (recorded evidence,
  nothing executed).
- Historical proofs verify with unchanged outcomes and bytes:
  `tests/contract/test_v01_historical_readers.py` (140 tests) and
  `tests/unit/test_proof_dispatch.py::test_a_v01_proof_is_read_by_the_historical_verifier`.
- Undeclared plan drift: the two WP1.8(a) tests above, plus
  `tests/unit/test_local_bundle_verify.py::test_a_plan_the_campaign_never_bound_fails_the_binding_itself`
  and `tests/unit/test_campaign_models.py::test_a_campaign_bound_to_another_execution_plan_is_rejected`.
- Unsupported location fails before external work:
  `tests/integration/test_skill_prepare.py::test_a_climb_planned_to_run_elsewhere_is_refused_before_anything_starts`
  (no draft written) and
  `tests/unit/test_execution_facts.py::test_a_plan_this_release_cannot_run_is_refused_naming_the_plane`
  (the gate the run service, the fake executor and the real executor all call).
- Malformed or missing linked documents:
  `tests/unit/test_local_bundle_verify.py::test_an_unreadable_execution_plan_is_reported_by_name`
  and `tests/unit/test_proof_dispatch.py::test_a_proof_this_build_cannot_place_is_refused_not_guessed`.
- Tamper fixtures: the existing bundle tamper tests, now over v2 bundles.
- Internally consistent but wrong bundles and inputs (section 8a): the four
  negative tests listed there, plus Astra's reproduction script run against
  this candidate.

## 10. Decisions and open points for Sean / Astra

The release identity (`climb-v0.2.0`, CLI `0.2.0`) and the history
snapshot location `release/history/climb-v0.1.0/` were confirmed in review
and are no longer open. The digests in sections 3 and 4 are what this
candidate generates and are read, not approved, until Astra integrates.

1. `protocol_version` in the ReleaseCore stays `v1alpha1`: the v0.2 documents
   are published under `schemas/v2` while the ReleaseCore field still names
   the v1alpha1 protocol. Not changed here because it was not in the
   confirmed field list; say if it should move.
2. Internal `execution_backend` on `RealExecutionResult` /
   `VariantExecutionResult` traces (not protocol documents): rename to
   `executor_kind` in a follow-up, or leave.
3. The plugin's other recorded CLI envelopes (`climb-show*.json`,
   `climb-list*.json`, `doctor.json`) still describe the v0.1 CLI's Climb
   summary. They should be re-captured when the plugin is cut over.
4. The platform consumer for `techtree.catalog.v2` / `techtree.campaign.v2`
   (the platform rejects catalog v2 today and has no `execution_plan` object
   kind) is Astra's bounded follow-up ticket; `platform/` was not opened and
   its bytes are unchanged here.

## 11. Known failures and what was not run

- Docker itself is not exercised by any check in this candidate. The Docker
  daemon is unreachable on this machine (`docker version` hangs; Astra's
  probe of the same host timed out too), so Docker readiness is recorded as
  unavailable rather than retried. The four tests in
  `tests/unit/test_doctor_execution_checks.py` that reach the `docker`
  command (`test_an_image_that_is_not_present_locally_blocks`,
  `test_with_a_campaign_the_subject_questions_are_asked_too`,
  `test_the_evaluation_doctor_treats_a_missing_engine_as_a_stop`,
  `test_a_host_that_cannot_run_anything_is_not_told_it_is_ready`) now put a
  stand-in `docker` on PATH that answers at the command boundary the way the
  real client does with no daemon listening, or with a daemon that holds no
  such image. The checks, and Doctor's classification of their answers, are
  the real code; what Docker would do with a container is not verified here.
- `real_model` tests were not run (paid inference is out of authority).
- No wheel was built, nothing was pushed, published, or signed with a real
  key.

## 12. Check commands and results (this worktree, 2026-09-07)

`make check` now completes as one command on this machine; the deselected
count it reports is the integration and `real_model` markers it excludes by
default, which are run separately below.

| command | result |
| --- | --- |
| `make check` (format-check, lint, typecheck, test, generated-check, v02-conformance-preflight) | exit 0: `388 files already formatted`; `All checks passed!`; `Success: no issues found in 308 source files`; `4048 passed, 1 skipped, 302 deselected in 407.92s`; `generated-check: generated artifacts match the working tree`; preflight `6 passed in 18.34s` |
| `uv run pytest -m "integration and not real_model" tests/integration` (equivalent to `make test-integration`; the `real_model` files are not marked `integration`) | `300 passed, 2 deselected in 340.28s` |
| `make check-plugin` | `929 passed in 94.35s`, plugin typecheck clean, plugin doctor passed (release `climb-v0.2.0` pins CLI `0.2.0`) |
| Astra's three reproductions from the first review, rerun against this tree with `wheel_digest` read as `engine_digest` | contradictory receipt location: rejected, `receipt_set.baseline.execution_location` and `receipt_set.candidate.execution_location` fail; replacement plan: rejected, "this execution plan is not the one the Campaign binds"; plan/validation engine mismatch: rejected, `linkage.plan_engine` fails |
