# Execution contract — WP11d (ndq.3.4): Ash BootstrapRelease + rollback

Binding: decisions 0007 R10, 0011, 0023; spec wp9-wp11 §9.3–9.4.
Workspace: techtree-ash/.

## Purpose
Build the exact BootstrapRelease Gate 2 will approve, wire the starter
Skill's content-addressed serving, and establish pointer-based
rollback — WITHOUT activating the new release or deploying.

## Binding design decisions (0023)

### Starter URL is keyed by the SKILL.md FILE digest
The URL serves exact file bytes, so:
`starter_skill_object_url = https://techtree.sh/objects/sha256:<SKILL.md-file-digest>`

The bootstrap starter_skill object carries BOTH digests:
```json
{
  "starter_skill": {
    "name": "hello-world-starter-v1",
    "object_url": "https://techtree.sh/objects/sha256:<file-digest>",
    "file_digest": "sha256:<file-digest>",
    "tree_digest": "sha256:<tree-digest>",
    "media_type": "text/markdown",
    "size": <bytes>
  }
}
```
file_digest identifies the exact bytes the URL returns; tree_digest
identifies the complete Skill bundle mounted during evaluation. The
CLI fetch path: fetch URL → verify file digest → stage as SKILL.md →
build the canonical one-file tree → verify tree digest. Never use the
tree digest as a URL key for a raw single file. (Check whether the
frozen CLI's _stage_document verifies against file or tree digest and
make the bootstrap consistent with what the frozen CLI actually
verifies; if the frozen CLI verifies the tree digest of the built
tree, both fields above make that work without CLI changes.)

### Object endpoint requirements
GET /objects/:digest returns exact bytes with
`Content-Type: text/markdown; charset=utf-8`, an ETag derived from the
digest, `Cache-Control: public, max-age=31536000, immutable`, no
dynamic serialization, no content mutation, and refuses to serve when
the stored bytes no longer match the requested digest (this refusal
already exists — keep its test).

### placeholder_release rule — no flip after approval
Build the final release candidate WITH `"placeholder_release": false`
and every coordinate concrete BEFORE founder approval, but do NOT make
it the active served release. The Gate-2 packet contains the exact
false-valued bytes that will later be activated unchanged. The
currently active site keeps serving the placeholder document until
approval. This forbids the sequence approve-digest-A → flip →
serve-digest-B.
Enforce 0007 R10 in ash: placeholder_release:false must reject every
placeholder-like value (placeholder.invalid, 0.0.0-placeholder, empty,
short commit, `latest`, `main`, mutable image tag, missing hash).

### Rollback = pointer switch
Releases are immutable rows/files; an active_release pointer selects
one. Rollback moves the pointer to the previous release. No mutation,
no deletion, no change to user-local artifacts. The runbook records:
current active digest, previous digest, exact command/Ash action,
verification step.

### Database decision
No queryable URL/digest column in v0.1. The BootstrapRelease is exact
JSON; derive views from the object.

## Steps
1. Import the starter SKILL.md bytes as a served object keyed by file
   digest; wire the endpoint headers above.
2. Build the inactive final BootstrapRelease candidate (wheel hash and
   plugin commit from WP11b/WP11c; both starter digests; regents-ai
   coordinate).
3. Implement/verify the R10 rejection validation with tests.
4. Implement the active-release pointer and rehearse rollback against
   a local/staging pointer.
5. Cross-repo equality: file and tree digests agree across python,
   plugin, and ash release sources.

## Outputs
priv/releases/<release-id>/{bootstrap.json, release-core.json,
checksums.json}; docs/release/runbook.md; docs/release/rollback.md;
the candidate bootstrap digest.

## Acceptance
Digest agreement across the three repos · R10 rejects all placeholder
values · candidate not active before Gate 2 · rollback rehearsed · no
write/upload route added · endpoint drift-refusal test still passes.

## Stop conditions
Any placeholder value surviving into the false-valued candidate · any
mutation-based rollback design · activation before approval.

## Founder decisions required
Hosting/deploy remains the founder's; deployment itself is Gate 2.
