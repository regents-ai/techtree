# Agent-version browsing

Status: implemented locally; awaiting founder review. New upstream runtimes have
not been executed or certified as part of this change.

## Product rule

Techtree must not impose one globally permitted Hermes harness version. Agent
versions are properties of individual submissions, not a platform-wide release
pin. This supersedes the single-version product assumption; it does not change
or relabel historical evidence.

The public results interface groups submissions by agent family: Hermes first,
with Prime Agent and Codex using the same structure when their adapters are
available. Do not present future adapters as working integrations.

For each family, default to the newest agent version represented in accepted
submissions, not the latest upstream release and not the last uploaded run.
Uploading another result from an older version must not make that version the
new default. Version precedence must respect that agent family's version format;
do not sort version strings lexicographically or rewrite source identifiers.

Show the scores belonging to the selected family and exact version. Provide a
carousel-style version list with explicit previous/next controls and direct
selection of historical versions. Keep the selected family/version in the URL
so links, reloads and pagination retain the same view. Do not auto-advance while
someone is reading. Empty states must not imply that a future adapter has results.

## Evidence and comparison boundary

Every run still records its exact agent family, runtime version/build, model,
Campaign, execution plan and evidence. A baseline/candidate comparison must use
the same recorded runtime; accepting multiple versions across the platform does
not permit a runtime change inside one comparison.

Do not pool scores from different versions, models or incompatible Campaigns into
one unexplained score. Retain the existing score meanings and attestation labels;
version navigation alone does not authorize a leaderboard or a new aggregation
formula. Keep withdrawn submissions marked and preserve historical proof bytes.

Admission should validate the adapter's supported protocol/capabilities and the
submission's internally consistent version-bound evidence. A hard-coded list of
previously recorded Hermes versions must not be the product's global admission
policy. Do not implement this by removing integrity checks or fabricating a
conformance recording for an unmeasured runtime.

Host-agent runtime version and Techtree plugin package version are distinct.
The carousel uses the former; record the latter separately when relevant to
provenance.

## Implementation boundary

- `platform/lib/techtree/network/publication_entry.ex` already stores
  `subject_harness` and `subject_harness_version`.
- `platform/lib/techtree/network/ingest.ex` derives those fields from submitted
  evidence. Family/version selection must use accepted records, not arbitrary
  display labels supplied separately.
- `platform/lib/techtree/network/query.ex` filters by exact family/version before
  keyset pagination. A separate Ash distinct read discovers versions across the
  accepted log, selecting their first appearance rather than the latest upload.
- `platform/lib/techtree/network/agent_versions.ex` orders semantic versions by
  release precedence, retaining original labels. Opaque identifiers follow
  releases and use newest-first initial appearance as a deterministic fallback,
  not a claim about upstream release precedence. Duplicate uploads do not reorder
  an already known opaque build. Semantically equivalent labels are tied by their
  exact strings; they are never merged.
- `platform/lib/techtree_web/live/runs_live/index.ex` defaults to Hermes when it
  has submissions, otherwise the first populated family. It supplies direct
  selection and previous/next links, preserves selection in pagination, and
  replaces the initial live URL with exact coordinates so reloads/reconnects do
  not silently switch to a newly submitted version. Invalid or half-specified
  coordinates show an error with no rows; empty families are not advertised.
- `cli/src/techtree/receipts/compare.py` checks paired, nonempty, uniquely named
  tool inventories, matching schemas and descriptions. Only the Hermes adapter
  gets the existing Skill-index description exception. The comparison no longer
  requires a tool surface in the single-version historical conformance lookup.
  Exact runtime/version equality, image digests and agreement with the bound
  execution plan remain independently checked.
- Historical conformance recordings remain reference evidence, not an admission
  allowlist and not proof that another runtime was measured. The supplied Climb's
  runtime remains its reproducibility default; a different runtime still needs
  a matching Campaign/execution plan that passes the existing catalog and
  publication verification. This change does not invent an automatic runtime
  upgrade, a new Campaign, or a working Prime Agent/Codex execution adapter.

## Acceptance criteria

- Two accepted Hermes versions can coexist without a global version toggle.
- Each family defaults to its newest submitted version independently.
- A later upload for an older version does not move the default backwards.
- Selecting a past version shows only its results and preserves the selection
  through pagination, deep links and browser navigation.
- Version discovery considers the whole accepted log, not just its first page.
- Keyboard-operable version controls expose the active selection and preserve
  reduced-motion behavior.
- Missing/invalid family-version combinations have explicit behavior and never
  silently show another version's scores under the requested label.
- Exact-version evidence binding, same-runtime comparisons, score comparability,
  withdrawn-result markers and historical readers continue to hold.
