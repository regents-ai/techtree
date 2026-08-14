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

## This release is a placeholder

The coordinates that can only be chosen at deploy time are still blank, and
the document says so in its own data:

```text
placeholder_release   true
placeholder_fields    cli_source_commit, cli_version,
                      maximum_tested_host_hermes_version, release_id,
                      starter_skill_object_url
```

Both founder Skills are now bound. `starter_skill_digest` is the ordered
content-tree digest of `skills/hello-world-starter-v1/SKILL.md` in this
directory, and `skill_improver_digest` is the SHA-256 of the exact bytes of the
plugin's `skills/skill-improver/SKILL.md` — two different digest semantics for
two different kinds of consumption, fixed by decisions document 0008 and stated
here because a reader cannot tell which is which by looking.

`starter_skill_object_url` is the one starter coordinate still open, and it is
open for a reason rather than by oversight: the release knows exactly which
Skill it measured, and where that Skill will be served from is not decided
until the object is published. So this build can name the Skill and cannot
fetch it, which is what `techtree skill starter` says when it refuses.

There are four spellings of "not chosen yet", one per kind of coordinate, and
none of them can collide with a real value: the version `0.0.0-placeholder`,
the commit of forty zeros, the digest of sixty-four zeros, and the address
`https://placeholder.invalid/unchosen`, under the top-level domain RFC 2606
reserves so that it can never resolve. A blank is never an empty string and
never an omitted field, because both of those read as an oversight.

The declaration is checked in both directions. A document cannot claim to be a
real release while it still holds a blank, and cannot be marked provisional
once every coordinate is bound. The engine digest, the catalog digest, the
protocol version, the introductory Climb and the subject harness version are
read out of this source tree, so they are never blank at all.

## Cutting a real release

1. Edit `release-inputs.json`. Every value in it is a decision, not a
   derivation: the release identifier, the published CLI version, the tagged
   source commit, the introductory Climb, the two Skill artifacts, the address
   the starter Skill is published at, and the host Hermes range that has
   actually been tested.
2. Run `make release-core`. It rewrites the four generated files from the
   inputs and from this source tree, and prints the ReleaseCore digest.
3. Run `make check`. The drift check regenerates everything in a throwaway copy
   of the repository and fails if what is committed is not what this tree
   produces.
4. Run `uv run python tools/verify_release_core.py`, adding
   `--bootstrap <path>` once the website's bootstrap document for this release
   exists, to confirm the two agree on every coordinate they both name.

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

The release document deliberately names no plugin commit and no wheel hash.
Both are produced *after* it, from it, which is what keeps the cross-repository
binding free of a cycle (specification section 9.3.3).
