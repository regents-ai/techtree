# techtree-ash

The read-only public surface for Techtree Climb: an onboarding and bootstrap
registry, and a catalog of the public Climbs and the protocol objects they are
built from.

This application does not run evaluations, accept Skills, receipts, or reports,
store Episodes or Traces, authenticate anyone, or run a leaderboard. The local
scientific loop in `techtree-python` keeps working when this site is offline —
the site is discovery and onboarding, never a runtime dependency.

## What is implemented so far

All of it: the catalog kernel, the public API over it, and the pages.

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

## The published surface

```text
GET /                           what Techtree Climb is
GET /start                      the two supported ways to run a Climb
GET /climbs                     the Climbs this release offers
GET /climbs/:slug               one Climb in full
GET /proofs/local               what a locally produced result claims
GET /protocol                   the documents a trial is made of

GET /healthz                    is a catalog being served, and which one
GET /api/v1/bootstrap           the installation contract, exact bytes
GET /api/v1/catalog             the generated catalog index, exact bytes
GET /api/v1/climbs/:slug        one Climb summarized, with links to its objects
GET /api/v1/objects/:digest     one protocol object, exact bytes
```

Every route is a read. There is no route that creates, accepts, uploads,
authenticates, or ranks anything.

Caching follows how immutable each address is. A content-addressed object may be
kept forever; the catalog index and the installation contract are cached briefly
and revalidated against their digest, and both honour `If-None-Match`.

Refusals share one shape — a stable code, a message that is safe to show a
stranger, and whether retrying could help:

```text
400  the digest in the path is not a digest
404  the digest or slug names nothing this release ships
503  nothing is imported yet, or the stored bytes no longer match their digest
```

The last one is deliberate: bytes that do not match the digest they are filed
under are never served, under any status.

### The installation contract

`/api/v1/bootstrap` publishes the pinned installation path: the minimum host
Hermes version, the exact CLI version, the plugin repository and its full
immutable commit, and the introductory Climb. Every executable instruction is an
array of arguments. Nothing in the payload is a shell string, nothing in it is a
credential, and the server never runs any of it.

Until the real release coordinates are signed off, the shipped contract is a
placeholder and says so in the payload itself: `placeholder_release` is `true`,
the versions read `0.0.0-placeholder`, and the pinned commits are all zeroes, so
an instruction that escaped review would fail rather than install the wrong
thing. Every bootstrap document must state `placeholder_release` either way — a
release that forgot to say would be read as real.

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
  --bootstrap priv/bootstrap/development.json
```

`--source-revision`, `--generator-version`, and the bootstrap document are
release inputs, supplied explicitly rather than guessed: the pinned CLI version
and the pinned Hermes plugin commit are founder-owned decisions. The document in
`priv/bootstrap` is the placeholder used until they are made.

Then verify and import:

```bash
mix catalog.verify --path priv/catalog
mix catalog.import --path priv/catalog
```

Both exit nonzero on failure. A failed import leaves the previously active
release serving exactly what it was serving.

## The pages

Plain documents: a serif measure of about 40 characters wide, three type sizes,
high contrast in both light and dark, no animation, and a print stylesheet. The
markup is semantic and the stylesheet is hand-written CSS with no framework and
no remote fonts, so a page is readable on a phone, in a reader, and on paper.

Every page renders completely on the first response; the live connection only
keeps it current. Nothing on the site collects anything about a reader.

Copy follows one rule: say what something means for the person reading it. The
protocol page is written for a technical reader and names documents the way the
protocol names them; everywhere else, a fingerprint is a fingerprint.

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
