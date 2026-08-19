# Release runbook — techtree-ash

What this site publishes, how a new release becomes the published one, and how
to check that it did. Rolling back is the same pointer move in the other
direction and has its own page: [rollback.md](rollback.md).

## What is published

| Address | What it returns |
| --- | --- |
| `GET /api/v1/bootstrap` | the exact bytes of the active bootstrap release |
| `GET /api/v1/catalog` | the exact catalog index of the active catalog release |
| `GET /api/v1/climbs/:slug` | the Climb manifest bytes |
| `GET /api/v1/objects/:digest` | the exact bytes filed under one content address |
| `GET /healthz` | whether a release is being served, and which one |

Every route answers `GET` and `HEAD`. A published address answers the four
mutating methods with `405` and an `Allow: GET, HEAD` header. There is no
upload, submission, or login route, and none may be added.

### The starter Skill

`GET /api/v1/objects/sha256:2aff27070177d9f37b99d5bef6fa372586887e78180005195cb808971ae55a4c`

returns the 1496 bytes of `hello-world-starter-v1/SKILL.md` as
`text/markdown; charset=utf-8`, cached `public, max-age=31536000, immutable`,
tagged with an ETag that is the digest.

The address is the digest of the **file**, because the address returns the file.
The digest of the one-file Skill *tree* the CLI builds after fetching it
(`sha256:596d1368…`) is a different number that names the mounted bundle; it is
not resolvable at this endpoint and must never be used as a URL key.

The installation contract carries both, as `starter_skill.file_digest` and
`starter_skill.tree_digest`. The file digest is what the address returns and
what a fetcher checks the response against; the tree digest is what the CLI
checks the Skill it built against before it will run anything.

The file itself ships in `priv/release/skills/hello-world-starter-v1/SKILL.md`
and is byte-identical to `release/skills/hello-world-starter-v1/SKILL.md` in
`techtree-python`, which is its source of truth. It is hashed again on every
request: bytes that no longer match the pinned digest are refused with `503`
rather than published.

## Publishing a release

The application never imports or republishes anything while booting. A release
that starts is a release serving exactly what it was serving before, so each
step below is deliberate.

1. **Sync the bundle** — release engineering, run in the repository, not on the
   host:

       mix run scripts/sync_catalog.exs \
         --source ../techtree-python/src/techtree/resources/catalog \
         --source-revision <full commit> \
         --generator-version <version> \
         --bootstrap <path to bootstrap.json>

2. **Deploy** the built release.

3. **Migrate**:

       bin/techtree eval 'Techtree.Release.migrate()'

4. **Import** the bundle it ships. The bundle is verified in full before
   anything is written, and the import is one transaction: on any failure the
   previously active release keeps serving.

       bin/techtree eval 'Techtree.Release.import_catalog()'

   Locally: `mix techtree.catalog.import`.

   An import stages its bootstrap release and publishes it. Every bootstrap
   release imported before it stays staged and stays publishable.

5. **Verify** (below).

### What the import refuses

A bundle whose bootstrap release states `"placeholder_release": false` is held
to decision 0007 R10: every coordinate concrete and immutable. The import
refuses `placeholder.invalid` addresses, `0.0.0-placeholder` and other
non-versions, empty values, commits shorter than 40 characters or spelled in
uppercase, `latest`, `main` and other moving references, zeroed-out fields,
container images named by tag rather than by digest, any address with no hash
beside it, and a starter Skill address keyed by anything other than the digest
of the file it returns. A release that states `"placeholder_release": true` is
believed and its placeholders are accepted — that is what the flag is for.

## The Gate-2 candidate

`priv/releases/climb-v0.1.0/` holds the exact bytes the founder is asked to
approve, and this build does not serve them. It is three files:

| File | What it is |
| --- | --- |
| `bootstrap.json` | the installation contract with `"placeholder_release": false` and every coordinate concrete |
| `release-core.json` | the ReleaseCore, byte-identical to the copy in `techtree-python` and in the plugin |
| `checksums.json` | the digest of each file above, and of every coordinate they name |

| | |
| --- | --- |
| Release channel | `stable` |
| Candidate bootstrap digest | `sha256:ed7cb6128ef7fdc9a75685f8e62354e0a9c36360956945f517ed3fce4daf4ff4` |
| ReleaseCore digest | `sha256:90cd8ad6976c1db55708a172601464e8cf01b8e658cb40398a594ab15daeec71` |
| CLI | `techtree==0.1.0`, source `a444c4d6…`, wheel `sha256:9a8c02af…` |
| Hermes plugin | `regents-ai/techtree-hermes` at `0670ff11…` (carries ReleaseCore `sha256:90cd8ad6…`) |
| Host Hermes | 0.20.1 minimum, 0.20.1 highest tested |
| Starter Skill | file `sha256:2aff2707…`, tree `sha256:596d1368…` |
| Rollback floor | `priv/bootstrap/stable.json`, `sha256:da064357…` |

The source commit is the commit the published wheel was built from, and it is
read from the stamp inside the wheel rather than from anything the repository
says about itself (decision 0026). `techtree-python` checks the whole table:

    uv run python tools/verify_release_core.py \
      --bootstrap ../techtree-ash/priv/releases/climb-v0.1.0/bootstrap.json \
      --wheel dist/techtree-0.1.0-py3-none-any.whl

All 25 checks are green for these bytes: 21 pass and 4 are skipped as facts only
the plugin and this site can see, and none fail.

### The channel and its floor

Decision 0027 puts this release on the channel `stable`, and gives that channel
a floor to roll back to: `priv/bootstrap/stable.json`, a release that declares
itself a placeholder and carries no coordinate anything could be installed from
— version `0.0.0-placeholder`, both revisions unset, the starter Skill address
`https://placeholder.invalid/unchosen`. It is staged on `stable` before the
candidate is, and it stays staged afterwards, so a rollback is a pointer move
onto bytes that exist rather than onto nothing.

`development` is untouched and stays what it always was: the channel this
repository serves locally, whose placeholder is `priv/bootstrap/development.json`
(`sha256:9e5afcb3…`). A build serves one channel, chosen by
`TECHTREE_BOOTSTRAP_CHANNEL`; the compile-time default is `development`.

Activating the candidate is the ordinary publishing sequence above with the
candidate as the bundle's bootstrap, so the approved bytes become the served
bytes without being rewritten:

    mix run scripts/sync_catalog.exs \
      --source ../techtree-python/src/techtree/resources/catalog \
      --source-revision a444c4d603a4094545cff8ae0d72f2197e26ce63 \
      --generator-version 0.1.0 \
      --bootstrap priv/releases/climb-v0.1.0/bootstrap.json

The digest served afterwards must be the candidate digest above, unchanged. The
floor stays staged, so rolling back is the pointer move in
[rollback.md](rollback.md). The host-side sequence, including moving the live
site onto `stable` before any of this, is [deploy-flyio.md](deploy-flyio.md).

**None of this happens before Gate 2.** Until then the candidate is a file in
the repository, the pointer is on a declared placeholder, and the public
install flow stays shut.

## Verifying

    curl -sD- https://<host>/api/v1/bootstrap -o bootstrap.json
    shasum -a 256 bootstrap.json

The digest of the body must equal the `ETag`, and both must equal the digest
that was intended to be published.

    curl -s https://<host>/healthz

reports the active channel, the catalog digest, and the Climb count.

    curl -sD- "https://<host>/api/v1/objects/sha256:2aff2707…" -o SKILL.md
    shasum -a 256 SKILL.md

must return `2aff2707…` and `content-type: text/markdown; charset=utf-8`.

## Current pointer state

Rehearsed on the local development database, 2026-08-15. These are development
values; the channel is `development` and the release is a declared placeholder.

| | |
| --- | --- |
| Channel | `development` |
| Active bootstrap digest | `sha256:9e5afcb33633a702e106b5379a75f3a7cca250239b5fa08b228843cb61a2b9da` |
| Previous bootstrap digest | `sha256:be2e965a889723cc25ddf97ba9cac822d031194a5d4ec97dd828c87bcb659ffe` |
| Also staged | `sha256:d95a0c3a392942a671dfe5a178440508ea53805dbda47f695c361e1b5f154a24`, `sha256:21802d59bfd32599bf0388849dd470393a8b4982bb256e34ebd3d3e75ff5893a`, `sha256:2273821d4c44b8ec39b38f93dcb1710879d43d1349625db610c2a58016bc604f` |
| Catalog digest | `sha256:62714b7782eb461fa62654455ffcbf74b3efce3555065f83b11f6ffa41cbf903` |
| CLI version pinned | `0.0.0-placeholder` |
| Plugin revision pinned | forty zeros |
| Host Hermes minimum | 0.20.1 |

The Gate-2 candidate `sha256:ed7cb612…` is deliberately absent from that list:
it is a file in the repository and has never been staged, so naming it to
`publish` refuses with `bootstrap_release_missing` and moves nothing. So is the
`stable` floor `sha256:da064357…`, which is staged on the live site before
Gate 2 rather than here — `stable` has no rows in a local development database.

`mix techtree.bootstrap.list` prints this table for whatever database it is
pointed at, newest first, marking the published release with `*`.
