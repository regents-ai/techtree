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

Rehearsed 2026-08-14 against the local development database with the site
running, on channel `development`.

| Step | Command | Result |
| --- | --- | --- |
| Before | `mix techtree.bootstrap.list` | `*` on `sha256:be2e965a…`, three others staged |
| Serve | `GET /api/v1/bootstrap` | ETag and body digest `sha256:be2e965a…` |
| Roll back | `mix techtree.bootstrap.publish --digest sha256:d95a0c3a…` | published `d95a0c3a…`, previously `be2e965a…` |
| Serve | `GET /api/v1/bootstrap` | ETag and body digest `sha256:d95a0c3a…`; pages still render |
| Roll forward | `mix techtree.bootstrap.publish --digest sha256:be2e965a…` | published `be2e965a…`, previously `d95a0c3a…` |
| Serve | `GET /api/v1/bootstrap` | byte-identical to the first response |
| After | `mix techtree.bootstrap.list` | all four releases still staged, one active |
| Refusal | `mix techtree.bootstrap.publish --digest sha256:cccc…` | `bootstrap_release_missing`, pointer unmoved |
