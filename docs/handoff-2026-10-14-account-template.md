# Techtree account/template adoption — 14 October 2026

## Scope and revisions

Local candidate on `tt/account-template-1014`, based on `7c6dc70d69d20aa9a4ac2f1248b060b3d5bdfcf2`
in `worktrees/techtree/walletbench-harbor`. The four earlier unpushed Skill/guide
commits remain intact. No push, release, migration, signing, paid run or earning
activation is authorized by this completion task.

The reference is released ash-template `3cd30cc5d87dce7da55cb01769736899bb1e09f5`,
confirmed by its owner, and its shared-library pin
`9db13eb6e8475326626860721d082e90cb0f93fc`. Integration head `d5fe886` includes
unpublished UI work and is not the release baseline. This change covers agent
account reads and their guidance; it does not claim complete site-wide UI parity.

Done: adopt the shared account behavior, accurately describe published CLI
support, complete relevant local checks, independently review the committed
candidate, and distinguish remaining release dependencies from later features.

## Changes

- Use the shared episode-bound Credits budget; add the template's readable
  Points, daily allowances, history pagination and exact disabled-state notes.
- Preserve current pairing, canonical owner lookup, private no-store responses
  and independent publication proof. Retain existing Points fields and history
  pagination aliases. History entries intentionally adopt shared grouped events
  instead of the former per-transfer fields; documentation states that change.
- Adopt Ash 3.36/AshOban 0.10 required by the shared pin and regenerate dependency
  guidance through its existing generator.
- Update the agent guide, public docs, product Skills, plugin instructions,
  command descriptions, tool manifest and generated OpenAPI together. Published
  CLI 1.10.2 supports identity, pairing and account reads. Python Skill helpers
  remain pending in unpublished 1.10.3; Model Climb commands are separate work.
- Points retain `starts_at: nil`, no approved rules and no adapters. Reads award
  nothing. No money tests were run. Disabling new spending approvals does not
  revoke existing grants, and the guidance does not claim otherwise.

Design check: shared Ash actions/policies own account data and authority;
PostgreSQL owns constraints; Phoenix/Plug owns request handling and responses;
the existing SIWA integration owns proof verification. No new queue, timer,
lease, retry mechanism or background process was introduced.

## Verification

Passed: warning-free compilation, strict Credo, Sobelow, compile-dependency
check, Ash generated-code check, assets build and type checking, formatting,
unused dependency check, regenerated usage-rule check, CLI contract check and
the current template's required-security-fix check. Existing plugin checks
passed (618 passed, 12 skipped); the existing OpenAPI check passed (1 test).
The OpenAPI export matches its producer's exact response bytes. Compiled local
checks confirmed inactive Points, shared 100/50 account-wide daily caps, no
Techtree earning rules, disabled new grant approvals and the exact Skill response.

`mix hex.audit` still reports only Bandit 1.12.5 / EEF-CVE-2026-105659. It is
unchanged by this candidate. The existing handoff records Sentinel's NOT EXPOSED
assessment and Sean's limited release-while-audit-red decision. This is not a
blanket waiver for new advisories or deployment configuration changes.

No new tests, test databases, application listener, database migration or
authenticated wallet action was introduced for these checks. Signed successful
account reads and native signed browser-tool execution remain unverified here;
the manifest says so. The full platform suite was not rerun because its setup
performs migrations. Prior base-suite results are not claimed as candidate results.

The resumed Claude implementor session `49febdb0-bc39-431e-9524-26ee4c3827ad`
could not authenticate (expired OAuth session). Codex completed the bounded local
checks and coordinated with the template/account owners instead. An independent
security reviewer examines the final committed change; its final verdict is in
the accompanying workspace review report.

## Guidance coverage

| Surface | Disposition and verification |
| --- | --- |
| Public agent guide, docs, llms and README | Updated; commands checked against CLI 1.10.2 source and current PyPI release |
| Product Skill and plugin instructions | Updated; exact Skill response and existing plugin checks passed |
| CLI descriptions, OpenAPI and WebMCP manifest | Updated together; producer export and CLI contract checks passed; native signed execution explicitly unverified |
| Dependency instructions | Regenerated; usage-rule check passed |
| Human UI and tooltips | No UI/tooltip behavior changed by this bounded candidate; broader shared UI adoption is separate |
| Frozen release records | Retained; no claim that CLI 1.10.3 or Model Climb commands are published |
| Deployed content and private runtime data | Candidate remains local; private runtime data was not inspected |

## Release dependencies and remaining work

The shared Credits prerequisite is **satisfied by recorded owner evidence**:
workspace `docs/orchestrator/open-decisions.md:876-877` records application of
`20261013202732`, independent confirmation of nullable `holds.tool`/`holds.request`
and the 4000-byte constraint, then a second migration run returning none. Line
1138 reconfirms it after template's release. This task did not query production
or repeat the migration.

Before release:

1. Complete the final immutable review and resolve any concrete findings.
2. Respect the earlier instruction to release after the final bench run. Its
   latest handoff has OpenCode and Prime pending (32 attempts, $24.64 recorded,
   no attempts open). This task did not resume paid batches or change that condition.
3. Obtain Sean's applicable push/deployment decision naming the final candidate
   and perform the approved release preflight. Never deploy during a bench batch.
4. Exercise the authenticated account responses with an approved paired identity;
   native browser-tool acceptance is a separate unverified surface.

CLI 1.10.3 publication and a subsequent `climb-v0.7.4` record are prerequisites
for advertising Python helper support, not prerequisites for these account reads.
The queued Model Climb report ownership-lock fix, harness install-log improvement,
future benchmark plan and broader UI/ENS adoption remain separate work. Points
earning, money tests and new Credits charging remain off.

Evidence and final review: workspace
`artifacts/techtree-account-adoption-2026-10-14/README.md` and its logs.
