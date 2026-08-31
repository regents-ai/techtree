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
| `GET /api/v1/publications` | one keyset page of the run log, newest first |
| `GET /api/v1/publications/:bundle_digest` | the verified projection of one published run |
| `GET /api/v1/publication-keys/:key_id` | the public half of the key this site countersigns receipts with |
| `GET /healthz` | whether a release is being served, and which one |
| `POST /api/v1/publications` | where a participant publishes a finished run, and later withdraws one |

Every route but the last answers `GET` and `HEAD`, and answers the four mutating
methods with `405` and an `Allow: GET, HEAD` header. The one write was added by
decision 0038 and takes two documents: a
`techtree.publication-submission.v1alpha1`, which publishes a finished run, and
a signed `techtree.publication-withdrawal.v1alpha1`, which withdraws one already
published. Which arrived is read off the document rather than off the URL, so
the site keeps one write address. Both are answered with a signed envelope this
site countersigns. There is no login route, no route that uploads a file, and no
address that returns the bytes a run was submitted with — a public address
handing back the file mapping is the bundle itself however it is wrapped, and
0038 defers that. No second write may be added.

`GET /api/v1/publications` takes `?before_sequence=` and `?limit=`, twenty-five
by default and at most a hundred. The order is arrival order, newest first, by
log sequence and by nothing else. A log sequence is not a position and not a
rank, and it may have gaps.

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
approve. The currently deployed image already carries these candidate files,
but the live `stable` pointer still serves the rollback floor until activation.
It is three files:

| File | What it is |
| --- | --- |
| `bootstrap.json` | the installation contract with `"placeholder_release": false` and every coordinate concrete |
| `release-core.json` | the ReleaseCore, byte-identical to the copy in `techtree-python` and in the plugin |
| `checksums.json` | the digest of each file above, and of every coordinate they name |

| | |
| --- | --- |
| Release channel | `stable` |
| Candidate bootstrap digest | `sha256:3fdadeeb3f435fe08232e401c38751345b4809e9b1bb4202c892b43464c73c76` |
| ReleaseCore digest | `sha256:c92b602e8097a6498c49f52587a486f46f2cfd0a7adfe5cb082c5e98527e40a1` |
| CLI | `techtree==0.1.0`, source `2e714835469dc0a3fb4bece3ed2f861317fe4d7c`, wheel `sha256:5565e553f2e29a145711d5b13f6c03760a99b6c17d404e4a36768513a7660040` |
| Hermes plugin | `regents-ai/techtree-hermes` at `db827e714094c89514ea63d3ace1c97e6698589d` (carries ReleaseCore `sha256:c92b602e8097a6498c49f52587a486f46f2cfd0a7adfe5cb082c5e98527e40a1`) |
| Host Hermes | 0.20.1 minimum, 0.20.1 highest tested |
| Publication key | `sha256:84ea8ffad2b0fc59f9db9f14b7d97f25c060e71b644dec316ecd582ac040b966` |
| Starter Skill | file `sha256:2aff27070177d9f37b99d5bef6fa372586887e78180005195cb808971ae55a4c`, tree `sha256:596d1368ac157975accce7ceff835eed6bfb789eaf68528a0aefa25a68793b0b` |
| Rollback floor | `priv/bootstrap/stable.json`, `sha256:d3fdb91588e897253af6e7c6c2bdc1fadc2b346d2e924c85f6e02c1393843191` |

The source commit is the commit the published wheel was built from, and it is
read from the stamp inside the wheel rather than from anything the repository
says about itself (decision 0026). `techtree-python` checks the whole table:

    uv run python tools/verify_release_core.py \
      --bootstrap ../techtree-ash/priv/releases/climb-v0.1.0/bootstrap.json \
      --wheel dist/techtree-0.1.0-py3-none-any.whl

All 26 checks are green for these bytes: 22 pass and 4 are skipped as facts only
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
(`sha256:9da7a90dcca51a5bfb3950aae75e1bb9032a979931983edd29d8f8215d1126e5…`). A build serves one channel, chosen by
`TECHTREE_BOOTSTRAP_CHANNEL`; the compile-time default is `development`.

Activating the candidate is the ordinary import step above with the candidate
bundle already carried by the deployed image. No new image or secret change is
needed: the import stages the exact bytes and moves the `stable` pointer in one
transaction, so the approved bytes become the served bytes without being
rewritten. For the currently verified production image, no repository sync or
deploy is required; the host command is shown below after Gate 2 approval.

The digest served afterwards must be the candidate digest above, unchanged. The
floor stays staged, so rolling back is the pointer move in
[rollback.md](rollback.md). The host-side sequence, including moving the live
site onto `stable` before any of this, is [deploy-flyio.md](deploy-flyio.md).

**None of this happens before Gate 2.** Until then the candidate is present in
the deployed image but is not staged or active, the pointer is on a declared
placeholder, and the public install flow stays shut. Once the public
coordinates are approved, run the import on the existing image:

    flyctl ssh console --app techtree-sh \
      --command "/app/bin/techtree eval 'Techtree.Release.import_catalog()'"

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

## Current production pointer state

Verified live on 2026-08-28. The app serves `stable`, the catalog import is
complete, and the v0.1.0 release is the active bootstrap release:

| | |
| --- | --- |
| Channel | `stable` |
| Active bootstrap digest | `sha256:3fdadeeb3f435fe08232e401c38751345b4809e9b1bb4202c892b43464c73c76` |
| Active catalog digest | `sha256:10a7fcc5de1951c14509947c0512a4eeb247a703cdf01cc3f268580979a7d12c` |
| Catalog source revision | `2e714835469dc0a3fb4bece3ed2f861317fe4d7c` |
| Catalog import status | `complete` |
| Active CLI | `0.1.0` |
| Active plugin revision | `db827e714094c89514ea63d3ace1c97e6698589d` |
| Rollback floor | `sha256:d3fdb91588e897253af6e7c6c2bdc1fadc2b346d2e924c85f6e02c1393843191` |
| Release state | staged and active on `stable` |

The rollback floor remains staged on `stable`. Rolling back is a pointer move
to those already imported bytes; it does not require rebuilding the release.

The image verified for this state is
`registry.fly.io/techtree-sh:deployment-01M15DF3M7QW26HD69NSSAADZV` (Fly release
v12).

`mix techtree.bootstrap.list` prints this table for whatever database it is
pointed at, newest first, marking the published release with `*`.
