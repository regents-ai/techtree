# 0002 — Campaign kernel

Status: binding for all WP0–WP5 work.

- Climb is a public wrapper. `ClimbManifest` owns public identity, slug,
  version, title, status, schedule, candidate policy, publication policy,
  and leaderboard policy — nothing scientific.
- `CampaignSpec` owns scientific execution: taskset reference, selection,
  membership commitment, publisher validation reference, environment,
  named agents, mutation contract, evaluation backend, execution policy,
  scoring, evidence requirements, budgets, and the data-policy reference.
- `DataPolicy` is required. Every execution artifact (draft, manifest,
  receipt, report) copies `data_policy_digest`. No run may silently change
  its rights policy.
- `EvaluationBackend` (who orchestrated and attested) is separate from the
  subject runtime (where the evaluated agent executed). WP0–WP5 permit only
  `local_techtree` / `participant`.
- Execution artifacts reference `campaign_spec_digest`, never the public
  Climb directly. Public Climb context is an optional `PublicContext`.
- `ProgramRef` and `outcome_contract_digest` are optional forward-compatible
  pointers. `ImprovementProgram` and `OutcomeContract` behavior is deferred.
- No public product policy is duplicated inside `CampaignSpec`.
- No worker may continue from an older ticket slice that places scientific
  configuration directly inside `ClimbManifest` (spec Appendix A.5).
