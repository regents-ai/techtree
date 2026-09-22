# Skill2Env import contract

This is Techtree's static admission subset of NVlabs/Skill2Env 0.3.0,
revision `9beb0b64a70290f862c8374bbef21f2ac88992ab` from
<https://github.com/NVlabs/Skill2Env.git>, under Apache-2.0 (see LICENSE).
Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
The upstream launcher and generator are not included or executed.

`planner-prompt.md` is Techtree's own planning instructions for `forge plan`,
adapted from the planning stage of the same revision and attributed in the
text itself; it is not a copy of the upstream prompt.

`contract.json` records the upstream pin, Harbor 0.16.0 dependency and
authoritative Harbor task schema 1.3. Its fixed sections are derived from
Skill2Env's host-authored `task_config.py` and Harbor 0.16.0's serialized defaults.
Techtree requires those sections explicitly and rejects aliases and additional
configuration. These are intentionally narrower rules than Harbor's full schema.
The SHA-256 of `contract.json` alone is stored as the Skill build's
`source.recipe_version`; it is not a task identity. Task identity remains the
existing `TaskSetCommitment`.

Reviewed upstream SHA-256 values:

- `skill2env/task_config.py`: `2cb2f75242404c477e6f133f9eb57dd5e42b9f73907e14d10f55f265f1df038f`
- `skill2env/validation.py`: `8b332613f71f253771a5a8c3b27eb8b6f7e62fa0b1d54eb0d22e5499df5eeb57`
- `skill2env/buildaudit.py`: `994df1ffd84d2e0ff6dcde6bfe9834132e8229a21130ad44ddba9abb2558cf30`
- `pyproject.toml`: `3d31eeb90a2882bf9794d0c4a9a893e09614c7153c213014aebf41cff4c5785b`

The importer accepts one already-generated local task and an explicit expected
Source Skill `provider/id`, its Skill2Env bundle digest (with `sha256:` prefix),
and Linux platform. The digest commits to the reviewed private source bundle;
the importer does not receive or independently reconstruct private source bytes.
Package metadata must match both expected values. Task bytes are never rewritten.

Admission requires the six upstream files, separate environment/tests/solution
trees, explicit offline network policies, and the pinned host-authored limits.
Only literal absolute artifact paths without overlaps are supported. There are
no fallback schemas, supplied images, host environment variables, MCP servers,
alternate verifier environments or multi-step tasks.

The local package is bounded to 128 MiB, 4096 entries and 32 directory levels.
Symlinks, special files, hidden/private filenames, recognized credential
signatures, source-digest disclosure outside task.toml, changing files and
case-colliding paths are rejected. Executable bits are retained. Filename and
signature checks cannot establish that arbitrary task text is free of secrets;
source disclosure review remains necessary before authoring or export.

Only those five root members are accepted; any other root file or directory
rejects the task (upstream tolerates stray files). The Dockerfile must be
printable ASCII with LF line endings; continued lines are joined exactly as
BuildKit joins them, and a blank or comment line inside a continued
instruction rejects the recipe.

The build context is exactly `environment/`. Static admission rejects parser
directives, ADD, dynamic or unpinned external FROM, COPY flags or sources outside
that context, RUN flags/mounts, heredocs, ARG and ONBUILD. COPY permits literal
local files/directories only, never `--from`; multi-stage FROM may refer to an
earlier stage.

Every external FROM must name a base image from `base-images.json`, the
release's allow-list: the exact name as listed (no registry prefix, no
alias) pinned `@sha256:` to that name's multi-platform index digest or to the
manifest digest of the platform being built for. A pin to another platform's
manifest, an unlisted name or an unlisted digest rejects the task before
anything is pulled. A recipe must name at least one such image; `scratch`
alone is not enough. The list is release data, not user input; changing it
is a release change.

Admission copies the task into `<build>/tasks/`, which must not exist yet, and
returns the content commitment with the base images the recipe named. It
writes no build record. A failed copy can retain partial files under
`tasks/`; that directory is never reused.

The service then pulls each named base image by digest (never by tag), records
the reference and the daemon's content id for it in the build record's
`source.base_images`, and writes `build.json`. The recipe is built later, at
qualification, with the network disabled (`docker build --network none`), from
exactly the committed `environment/` directory, with no build arguments,
secrets, SSH or cache mounts; its log is retained beside the qualification
evidence whether it succeeded or not, and a failed build tags no image.

When `task.toml` carries `metadata.base_image_pins` (Skill2Env's build audit
records the digest it pinned each `FROM` to), those pins must be exactly the
recipe's own `FROM` pins; a task without the record is admitted on the
recipe's pins alone.

The import then qualifies the task with the common profile
(`forge/qualify.py`): the package must still hash to its commitment before
and after; no file of `tests/` or `solution/` may appear inside
`instruction.md` or any `environment/` file; the image must build offline;
the image must hold no `/tests`, `/solution` or `/logs`; a run that does
nothing must score 0; `solution/solve.sh` followed by `tests/test.sh` must
score 1; and what the tests leave under `/logs/verifier` across both runs
must be regular files, with no link of any kind, within 1 MiB and 1024
entries. Both graded runs use the isolated runtime (`--network none`, memory
and CPU caps, `tests/` and `solution/` mounted read-only, the verifier's
output directory mounted writable at `/logs/verifier`, nothing else) bounded
by the pinned `task.toml` times: the verifier's 600 s for the run that does
nothing; in the reference run one container is started, `solve.sh` runs in
it with the agent's 1800 s and then the tests with the verifier's 600 s, each
deadline kept from the host, since the image comes from the task's own
recipe. A step still running at its deadline ends with the container removed
and leaves no verdict; so does a `solve.sh` that exits with an error (the
tests then do not run) and an image that cannot be started. Every check and what it saw is written to
`qualification.json` beside the build; a rejected task keeps its image build
log and both containers' transcripts. The repository runner does not yet
execute Skill tasks.
