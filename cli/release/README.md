# Release artifacts

This directory holds the document that binds one Climb release together, and
the record of how it was produced. Specification: `docs/spec/climb-v0.1-wp9-wp11.md`
sections 6.6, 9.3–9.5 and 9.7.

## What is here

| File | Owner | What it is |
| --- | --- | --- |
| `release-inputs.json` | a person | The decisions only the release owner can make. |
| `release-core.json` | the generator | The release document other repositories copy. |
| `release-core.schema.json` | the generator | What a non-Python consumer validates it against. |
| `build-info.json` | the generator | Which inputs produced which bytes. |
| `skills/hello-world-starter-v1/SKILL.md` | the founder | The starter Skill the release names. |

The starter Skill sits here rather than inside the package because the wheel
carries no Skill bytes: what a machine runs is fetched from
`starter_skill_object_url` and checked against `starter_skill_digest`, and this
is the copy that digest is taken from. The two coordinates are one decision in
two halves — an address with no digest invites running whatever is served, and
a digest with no address names bytes nobody can obtain. It is
the founder's own text with one change the founder directed, so nothing
generates it and nothing may edit it without a new approval.

Two things about it are deliberate and easy to undo by accident. Its
frontmatter description names the task family and the answer shape and stops
there, because a description that taught the procedure would hand a subject
the whole intervention without the Skill ever being opened. And the Skill says
nothing about being an introductory one that is incomplete on purpose — that
disclosure belongs to the Climb page, to `techtree skill starter`, and to the
calibration record, never to the text a subject reads while being measured.

`src/techtree/resources/release/release-core.json` holds the same bytes as
`release-core.json` here. The wheel has to contain the release document, and a
file outside the package cannot go into a wheel, so the generator writes both
copies and `make generated-check` fails if they ever differ.

## What this release names

Every coordinate in `release-core.json` is concrete, and the schema is what
makes that true rather than a convention (decisions document 0026). A version
is three numbers, a release identifier is a name, a digest is sixty-four
hexadecimal characters that are not all zero, and the starter Skill's address
is a content address ending in the digest of the file it returns. Nothing that
means "not chosen yet" validates, so a document that parses is a document
somebody finished.

```text
release_id                            climb-v0.1.0
cli_version                           0.1.0
starter_skill_object_url              https://techtree.sh/api/v1/objects/sha256:2aff2707…
publication.submission_endpoint       https://techtree.sh/api/v1/publications
publication.public_log_url            https://techtree.sh/runs
publication.network_key.key_id        sha256:75e4239e…
```

`starter_skill_digest` is the ordered content-tree digest of
`skills/hello-world-starter-v1/SKILL.md` in this directory, and
`skill_improver_digest` is the SHA-256 of the exact bytes of the plugin's
`skills/skill-improver/SKILL.md` — two different digest semantics for two
different kinds of consumption, fixed by decisions document 0008 and stated
here because a reader cannot tell which is which by looking. The object URL is
keyed by a third number, the SHA-256 of the starter Skill *file*, because that
is what the address returns and what a fetcher checks a response against
before it builds anything.

## The run log's key

`publication.network_key` is the public half of the key the run log
countersigns publication receipts with. `techtree publish` checks every receipt
against exactly this key before it writes one into a run directory, which is
what makes a countersignature worth anything: a server that invented a key and
signed with it is refused, because the participant already knows which key to
expect.

The founder generated this key on 2026-08-27 and gave only the public half.
Its identifier is the sha256 of the key's own 32 bytes, which is how every
key identifier in this protocol is derived and why a receipt naming a key it
does not carry is caught without looking anything up.

The private half lives in one place on the founder's machine, outside every
repository, and in Fly's secrets as `TECHTREE_NETWORK_SIGNING_KEY`. It is in
no file here and must never be. A release refuses to build if the block is
missing, if the key is not 32 bytes, if it is all zeros, or if the identifier
is not the digest of the key beside it.

Rotation is a new key and therefore a new identifier, a new ReleaseCore and a
new release. Receipts signed under an older key stay verifiable by anybody who
kept that release's own coordinates, which is the point of pinning them.


## What the release document does not say

It names no wheel hash, no plugin commit and no source commit. Those are facts
about artifacts that do not exist when the document is written, and a document
that guessed at them would be wrong in a way nobody could see. Instead:

| Fact | Where it comes from |
| --- | --- |
| the commit a wheel was built from | stamped into that wheel by the build (`tools/stamp_provenance.py`), reported by `techtree release info` |
| the wheel's SHA-256 and the plugin commit | the website's `BootstrapRelease`, which wraps this document |

The build refuses to stamp a wheel it cannot name a commit for: no git, no
commit, or one packaged file differing from that commit, and there is no wheel.
`release/build-info.json` records the mechanism in full.

## Cutting a real release

1. Edit `release-inputs.json`. Every value in it is a decision, not a
   derivation: the release identifier, the published CLI version, the
   introductory Climb, the two Skill artifacts, the address the starter Skill
   is published at, the host Hermes range that has actually been tested, and
   the publication coordinates — including the run log's real public key, which
   the section above says how to fill in.
2. Run `make release-core`. It rewrites the four generated files from the
   inputs and from this source tree, and prints the ReleaseCore digest.
3. Run `make check`. The drift check regenerates everything in a throwaway copy
   of the repository and fails if what is committed is not what this tree
   produces.
4. Run `uv run python tools/verify_release_core.py`, adding
   `--bootstrap <path> --wheel <path>` once the website's bootstrap document
   and the built wheel exist, to confirm all three agree on every coordinate
   they name.

Steps 2 and 4 are ordinary local commands. Nothing in this directory publishes,
uploads, or contacts anything.

## Where these bytes go next

```text
release/release-core.json
    -> src/techtree/resources/release/release-core.json   (this repository)
    -> the techtree-hermes plugin repository, verbatim
    -> wrapped by the website's BootstrapRelease, which adds the wheel hash
       and the plugin commit that cannot exist yet when this document is made
```

The release document deliberately names no plugin commit, no wheel hash and no
source commit. All three are produced *after* it, from it, which is what keeps
the cross-repository binding free of a cycle (specification section 9.3.3).
