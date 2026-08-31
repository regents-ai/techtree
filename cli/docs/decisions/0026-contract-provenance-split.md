# 0026 — ReleaseCore is a contract; build provenance is stamped

Status: binding (founder ruling, 2026-08-15: option B, hard cutover,
no legacy maintenance). Resolves ticket cxb. Amends the closeout
directive's ReleaseCore field expectations — relay to the author for
countersign; implementation proceeds on the founder's ruling.

## The principle

An artifact never describes its own identity. Identity is stamped
onto it at build time or witnessed externally. The release record
(ReleaseCore) is a pure CONTRACT: it contains only values knowable
when it is authored, so it is honestly final at commit time — one
ordinary commit, no placeholder tracking, no two-commit dance.

## 1. ReleaseCore schema — hard cutover

DELETED fields: `cli_source_commit` (self-referential — the design
mistake this decision removes), `placeholder_release`,
`placeholder_fields` (their only job was tracking unfilled fields;
with every field authorable, they are dead machinery).

The canonical committed ReleaseCore carries, all concrete:
cli_version "0.1.0" · release_id "climb-v0.1.0" ·
starter_skill_object_url
"https://techtree.sh/api/v1/objects/sha256:2aff27070177d9f37b99d5bef6fa372586887e78180005195cb808971ae55a4c"
· starter_skill_digest (tree) · skill_improver_digest ·
engine_digest · catalog_digest · minimum_host_hermes_version
"0.20.1" · maximum_tested_host_hermes_version "0.20.1" ·
subject_hermes_version "0.19.0" · protocol_version. The schema
REQUIRES every field concrete (no placeholder-shaped value
validates). Producers, consumers, fixtures, goldens, and tests move
to the new shape only; all placeholder-handling code paths are
deleted, not policed (user hard rules 1–10).

## 2. Build provenance — stamped, never committed

The wheel carries a build-provenance record (the exact full source
commit, and nothing invented) written DURING the build, never present
in the committed tree. Constraints: the stamped commit must be the
real full 40-char commit of the built tree; same commit → identical
bytes (reproducibility holds); a build that cannot determine the
commit FAILS — no "unknown", no fallback value. Mechanism is the
implementer's choice (git-based build hook, or git-archive
export-substitution) — pick ONE mechanism, the simplest that meets
the constraints, and document it in release/build-info.json.
`techtree release info` reports the stamped commit. The existing
release/build-info.json repo record continues to describe how the
build works; the stamped file inside the wheel is the per-artifact
provenance.

## 3. External witness — unchanged role, updated fields

The BootstrapRelease remains the external witness binding wheel
SHA-256 + plugin commit + source commit together, and KEEPS its
`placeholder_release` flag — dev-vs-release is a real distinction for
the serving site, and R10 enforcement stays exactly as built. The
python-side bootstrap checker (verify_release_core/bootstrap tooling)
is cut over in the same pass: it compares the bootstrap's cli.source
against the WHEEL's stamped provenance and the bootstrap's
release_core_digest against the concrete core, and adopts the
canonical starter_skill shape (file_digest + tree_digest — this
absorbs ticket 3bp). No comparison references deleted fields.

## 4. Gates — opened by correctness, not loosened

The plugin's placeholder-release install refusal and the CLI's
placeholder-URL starter refusal are DELETED — their job is now done
by construction (a schema-valid core is concrete) and by the
bootstrap-side R10 validation. The CLI's starter fetch reads the
contract's real URL and verifies file digest then built-tree digest
as designed. These are release-tooling behavior changes, not
scientific ones (0022: runs, approvals, proposals, receipts, proof,
host requests, mounting, guards, Campaign are untouched); the two
paid journeys certify the opened flow end to end.

## 5. What must not move

Campaign b9e3f00c · engine 874cbae0 · membership 56f697fb · starter
tree 596d1368/file 2aff2707 · improver e6bc16c4 · DataPolicy
6c532a43 · subject model/sampling/budgets/execution. The
certified-scientific-fingerprint check must pass unchanged (it
asserts these from artifacts). ReleaseCore's digest changes (contract
content changed) — expected and recorded; byte-identical propagation
across python/plugin/ash re-verified.

## 6. Acceptance

All three repos' full batteries green · new-shape goldens/fixtures
regenerated through tooling (never hand-edited) · wheel rebuilt
reproducibly, inspection updated (asserts stamped provenance present
and correct, no placeholder anywhere, no deleted-field references) ·
fresh isolated install: `release info` shows the stamped commit,
`release verify` passes against the new core digest · regenerated
inactive bootstrap candidate accepted by R10 with the new core ·
grep-clean: no `cli_source_commit`, no ReleaseCore
`placeholder_release`/`placeholder_fields` references anywhere in
live code, schemas, fixtures, or docs-of-record (historical decision
docs and the approved Gate-1 packet/addendum are records, not code —
they stay).
