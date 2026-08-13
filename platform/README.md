# techtree-ash

The read-only public surface for Techtree Climb: an onboarding and bootstrap
registry, and a catalog of the public Climbs and the protocol objects they are
built from.

This application does not run evaluations, accept Skills, receipts, or reports,
store Episodes or Traces, authenticate anyone, or run a leaderboard. The local
scientific loop in `techtree-python` keeps working when this site is offline —
the site is discovery and onboarding, never a runtime dependency.

## What is implemented so far

Work package 8a: the Ash resources behind the public projection and the release
state, and the transactional importer that ingests a generated catalog bundle.

```text
lib/techtree/catalog/
├── domain.ex            Techtree.Catalog — resources, code interfaces, config
├── catalog_entry.ex     one searchable row per shipped object
├── catalog_release.ex   one import attempt and what came of it
├── bootstrap_release.ex the published install contract, as exact bytes
├── bundle.ex            a generated export on disk, and safe path resolution
├── digest.ex            sha256 over raw bytes; no canonicalization
├── verifier.ex          digests, paths, index shape, bootstrap shape, no dangling refs
├── importer.ex          verify, stage, activate — all of it or none of it
└── query.ex             the only read path the web surface may call
```

Public routes and pages are added by work packages 8b and 8c.

## Exact bytes

Protocol objects are served byte-for-byte as `techtree-python` generated them.
They are never decoded and re-encoded here: an alternate JSON serialization
would be an alternate scientific representation with a different digest. The
database holds projections and release state; the bytes stay in the bundle and
are hashed again on every read.

## The catalog bundle

`priv/catalog` holds the generated export and is not under version control in
this repository — the Python repository is the single owner of those artifacts.
Sync one in before importing:

```bash
mix run --no-start scripts/sync_catalog.exs \
  --source ../techtree-python/src/techtree/resources/catalog \
  --source-revision <full-commit> \
  --generator-version <generator-version> \
  --bootstrap <path-to-bootstrap.json>
```

`--source-revision`, `--generator-version`, and the bootstrap release are
release inputs, supplied explicitly rather than guessed: the pinned CLI version
and the pinned Hermes plugin commit are founder-owned decisions.

Then verify and import:

```bash
mix catalog.verify --path priv/catalog
mix catalog.import --path priv/catalog
```

Both exit nonzero on failure. A failed import leaves the previously active
release serving exactly what it was serving.

## Development

Requires PostgreSQL 14 or newer.

```bash
mix setup   # deps, database, assets
mix check   # formatting, warnings-as-errors, tests
```

`PGUSER`, `PGPASSWORD`, and `PGHOST` override the development and test database
connection when the local server does not use the Phoenix defaults.

## Runtime configuration

```text
DATABASE_URL                 required in production
SECRET_KEY_BASE              required in production
PHX_HOST, PORT               endpoint
TECHTREE_CATALOG_ROOT        a bundle deployed beside the release, optional
TECHTREE_BOOTSTRAP_CHANNEL   the release channel to import and serve
```

No model-provider credential is read by this application.
