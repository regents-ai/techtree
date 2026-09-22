# Skill2Env import contract

This is Techtree's static admission subset of NVlabs/Skill2Env 0.3.0,
revision `9beb0b64a70290f862c8374bbef21f2ac88992ab` from
<https://github.com/NVlabs/Skill2Env.git>, under Apache-2.0 (see LICENSE).
Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
The upstream launcher and generator are not included or executed.

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
An existing build destination must be empty. A failed copy can retain partial
files but never writes build.json, and its destination cannot be reused.

An accepted build is unqualified. No image is acquired or built, no task code is
executed, and no offline-execution or reference/no-op claim is made. Release-owned
base-image acquisition, network-disabled builds and qualification remain U2b2.
The current repository-only execution and qualification paths still refuse it.
