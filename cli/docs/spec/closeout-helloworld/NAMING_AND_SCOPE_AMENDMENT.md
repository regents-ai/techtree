# Hello World Naming and Presentation-Scope Amendment

This amendment supersedes the previous founder closeout pack wherever it used
`procedure-transfer-v1` or `BranchCode` as the public product name, or treated
`rich-terminal-output` as a shipped founder Skill.

## Public Naming

Use these public names:

```text
Display title:       Techtree Hello World
Subtitle:            A toy Skill-uplift Climb
Climb slug:          hello-world-climb
Climb reference:     hello-world-climb@1
Campaign title:      Hello World Skill Uplift
Starter Skill:       hello-world-starter-v1
First result label:  Hello World Uplift Receipt
Second result label: Hello World — Iteration 2
Task family:         BranchCode v1
```

BranchCode v1 remains the synthetic underlying procedure and task family.
Do not rename the already-pinned Python taskset package or internal environment
module solely for marketing. Public catalog metadata, CLI copy, plugin copy,
website copy, bootstrap data, and release coordinates use the Hello World
names.

Every public description must say that this is a toy introductory mechanism
test, not a broad capability benchmark.

## Remove `rich-terminal-output` from the Product Release

The `rich-terminal-output` Skill is a local development Skill used to direct
implementation of `techtree-python` terminal output. It is not a Techtree
product Skill and must not be shipped, registered, digest-pinned, or listed in
release coordinates.

The v0.1 result path is:

```text
signed UpliftReport
    ↓
deterministic techtree-python presentation payload
    ↓
deterministic Rich terminal renderer or compact gateway renderer
    ↓
Hermes plugin relays the deterministic result
```

There is no host-model presentation completion in the released v0.1 flow.

The only guided host-model completion in Climb v0.1 is the explicitly requested
one-turn `skill-improver` proposal.

## Required Repository Changes

### `techtree-python`

- Keep deterministic Rich and compact result renderers.
- Use `Techtree Hello World` and the labels above in public presentation.
- Remove any release-coordinate dependency on a rich-output Skill.
- Keep scientific values and caveats deterministic.

### `techtree-hermes`

- Delete or stop packaging `skills/rich-terminal-output/SKILL.md`.
- Do not register `techtree:rich-terminal-output`.
- Remove it from founder-asset verification.
- Remove it from ReleaseCore equality checks.
- `techtree_run_result` must relay deterministic CLI/gateway output and must
  not invoke a host LLM for presentation.
- Existing narrative/guard modules may remain temporarily only when they are
  unreachable from the released flow and excluded from all release promises;
  do not reopen stable code solely for cosmetic deletion during closeout.
- Retain `skill-improver` as the only founder-supplied operator Skill used by
  the guided flow.

### `techtree-ash`

- Rename the public catalog card and Climb page to `Techtree Hello World`.
- Use `hello-world-climb@1` in bootstrap and catalog references.
- Use the starter prompt:
  `Set up Techtree and run the Hello World Climb.`
- Remove any rich-output Skill digest or asset coordinate from release data.

## Release Schema

Because no public production ReleaseCore has been issued, remove
`rich_output_skill_digest` from the current pre-release ReleaseCore schema and
regenerate all copies and equality fixtures.

If a production ReleaseCore using the old schema was unexpectedly published,
do not mutate it; create a new schema version instead.

The founder-controlled Skill set for v0.1 is now exactly:

```text
hello-world-starter-v1
skill-improver
```
