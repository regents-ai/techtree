# Rollback — techtree-ash

Rollback here is a pointer moving. Nothing is rewritten, nothing is deleted, and
nothing on a participant's machine is touched.

## Why it is a pointer

A bootstrap release is filed under the digest of its exact bytes, so two rows
with the same digest are the same release and a release can never become a
different one. Which release a channel publishes is a single flag that exactly
one row per channel may hold. Moving it forward is what an import does at the
end; moving it back is this procedure. Both are the same operation.

Consequences worth stating plainly:

- **Nothing is deleted.** Every bootstrap release the channel ever imported
  stays staged and stays publishable, in both directions, indefinitely.
- **Nothing is edited.** The stored bytes are hashed again before the pointer
  moves; a payload that no longer matches the digest it is filed under is
  refused rather than published.
- **Nothing local is affected.** A participant's installed CLI, plugin,
  Skills, runs, and receipts live on their machine. This site publishes; it
  does not reach back. A rollback changes what a *new* reader is told to
  install. It does not uninstall, downgrade, or revoke anything.
- **Content addresses keep their meaning.** Objects already published stay
  resolvable at their digests after a rollback, which is what the immutable
  caching header promised.

## What `stable` rolls back to

Decision 0027 §2 makes the floor of the `stable` channel an ordinary staged
release rather than an empty pointer: `priv/bootstrap/stable.json`,

    sha256:f8a7adf65f0e6ce50eab933419d4f830aad894204fcc690e25105d5f9db61e62

It is a deliberately non-installable release. It declares
`"placeholder_release": true`, pins version `0.0.0-placeholder`, leaves both
revisions unset, and gives the starter Skill the address
`https://placeholder.invalid/unchosen`, so nothing can be installed from it and
the public install flow stays shut while it is published. It passes every rule
the import applies to a declared placeholder; decision 0007 R10, which demands
concrete coordinates, applies only to a release claiming to have them.

The consequences of that choice are the point of it:

- It is **staged before the candidate**, on the live site, before Gate 2. A
  channel whose only release is the one being activated has nowhere to go back
  to.
- It **stays staged after activation**. Rolling back is the pointer move below
  onto those exact bytes — never a rebuild, never a pointer to nothing.
- Rolled back, the site is honest rather than broken: it serves a contract that
  says it is not a real release, which is what it said before Gate 2.
- Its digest is named exactly, here and in the Gate-2 packet, so the bytes a
  rollback lands on are approved in advance rather than found later.

The `development` channel keeps its own floor,
`priv/bootstrap/development.json` (`sha256:9da7a90dcca51a5bfb3950aae75e1bb9032a979931983edd29d8f8215d1126e5…`), for local work. Neither
channel can roll back to the other's releases: staged releases belong to a
channel.

## The procedure

1. **Find the two digests.**

       bin/techtree eval 'Techtree.Release.list_bootstrap_releases()'

   Locally: `mix techtree.bootstrap.list`. Newest first; `*` marks the release
   being published now. Note the digest marked `*` (what you are leaving) and
   the digest you are going back to.

2. **Move the pointer.**

       bin/techtree eval 'Techtree.Release.publish_bootstrap("sha256:<64 hex>")'

   Locally:

       mix techtree.bootstrap.publish --digest sha256:<64 hex>

   It prints the channel, the digest now published, and the digest that was
   published before it. It refuses, and changes nothing, when the digest is
   malformed, when this channel never staged it, or when the stored bytes
   drifted.

3. **Verify.**

       curl -sD- https://<host>/api/v1/bootstrap -o bootstrap.json
       shasum -a 256 bootstrap.json

   The body digest and the `ETag` must both be the digest you published.
   `mix techtree.bootstrap.list` must now mark that digest with `*`, and must
   still list every release it listed before.

4. **Going forward again** is step 2 with the other digest.

## What this does not cover

The catalog bundle is a directory of files that ships inside the deployed
release, not rows in a database. Publishing a different catalog therefore means
deploying the release that carries it and importing again — the sequence in
[runbook.md](runbook.md) — not a pointer move. The bootstrap pointer is
independent of it: rolling the installation contract back does not change which
catalog is being served.

## Rehearsal record

Rehearsed 2026-08-15 against the local development database with the site
running, on channel `development`.

| Step | Command | Result |
| --- | --- | --- |
| Before | `mix techtree.bootstrap.list` | `*` on `sha256:9da7a90dcca51a5bfb3950aae75e1bb9032a979931983edd29d8f8215d1126e5…`, four others staged |
| Serve | `GET /api/v1/bootstrap` | ETag and body digest `sha256:9da7a90dcca51a5bfb3950aae75e1bb9032a979931983edd29d8f8215d1126e5…` |
| Roll back | `mix techtree.bootstrap.publish --digest sha256:be2e965a…` | published `be2e965a…`, previously `9da7a90dcca51a5bfb3950aae75e1bb9032a979931983edd29d8f8215d1126e5…` |
| Serve | `GET /api/v1/bootstrap` | ETag and body digest `sha256:be2e965a…`; pages still render |
| Roll forward | `mix techtree.bootstrap.publish --digest sha256:9da7a90dcca51a5bfb3950aae75e1bb9032a979931983edd29d8f8215d1126e5…` | published `9da7a90dcca51a5bfb3950aae75e1bb9032a979931983edd29d8f8215d1126e5…`, previously `be2e965a…` |
| Serve | `GET /api/v1/bootstrap` | byte-identical to the first response |
| After | `mix techtree.bootstrap.list` | all five releases still staged, one active |
| Refusal | `mix techtree.bootstrap.publish --digest sha256:4fe1e72a…` | the Gate-2 candidate was never staged: `bootstrap_release_missing`, pointer unmoved |

The last row names whichever candidate is current — now
`sha256:4fe1e72a…`, the candidate re-cut onto the state-root-permission-fixed
plugin commit. The refusal is a property of any digest this channel never staged
rather than of one release: publishing a never-staged digest returns
`bootstrap_release_missing` and moves nothing, so the row reads the same against
each candidate in turn. It was last exercised live on 2026-08-21, when the
then-current candidate was refused, the pointer stayed on
`sha256:9da7a90dcca51a5bfb3950aae75e1bb9032a979931983edd29d8f8215d1126e5…`, and
all five releases stayed staged. Every candidate digest that has stood in this
row — `2ef4a475…`, `57f95dcc…`, `ed7cb612…`, `73623d58…`, `9a4dca4f…`,
`a3e6d350…` and `09d6dc4e…` — has since been superseded, and none names bytes any
repository still carries.

This rehearsal was run on `development`, the only channel a local database has.
The equivalent on `stable` is the pointer move in
[deploy-flyio.md](deploy-flyio.md): back onto `sha256:f8a7adf65f0e6ce…`, the floor
described above.
