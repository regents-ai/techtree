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

`src/techtree/resources/release/release-core.json` holds the same bytes as
`release-core.json` here. The wheel has to contain the release document, and a
file outside the package cannot go into a wheel, so the generator writes both
copies and `make generated-check` fails if they ever differ.

## This release is a placeholder

Every coordinate that only the release owner can choose is still blank, and the
document says so in its own data:

```text
placeholder_release   true
placeholder_fields    cli_source_commit, cli_version,
                      maximum_tested_host_hermes_version, release_id,
                      rich_output_skill_digest, skill_improver_digest,
                      starter_skill_digest
```

There are three spellings of "not chosen yet", one per kind of coordinate, and
none of them can collide with a real value: the version `0.0.0-placeholder`,
the commit of forty zeros, and the digest of sixty-four zeros. A blank is never
an empty string and never an omitted field, because both of those read as an
oversight.

The declaration is checked in both directions. A document cannot claim to be a
real release while it still holds a blank, and cannot be marked provisional
once every coordinate is bound. The engine digest, the catalog digest, the
protocol version, the introductory Climb and the subject harness version are
read out of this source tree, so they are never blank at all.

## Cutting a real release

1. Edit `release-inputs.json`. Every value in it is a decision, not a
   derivation: the release identifier, the published CLI version, the tagged
   source commit, the introductory Climb, the three Skill artifacts, and the
   host Hermes range that has actually been tested.
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
