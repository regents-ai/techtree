# Techtree Hello World Climb v0.1 — Founder Closeout Directive

## Mission

Close the Climb v0.1 release without adding product scope.

The public introductory experience is now **Techtree Hello World**, a toy
Skill-uplift Climb using the synthetic BranchCode v1 task family.

The remaining founder-controlled work is:

1. Freeze and certify two Skill files.
2. Generate one immutable release-coordinate packet.
3. Stop for founder approval.
4. Only after exact approval, publish/tag/deploy the approved coordinates.
5. Do not upload any participant receipt, Episode, Trace, Skill proposal, or
   proof.

Read `NAMING_AND_SCOPE_AMENDMENT.md` first. It is binding.

## Public Names

Use:

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

Do not use `HelloWorldBench`.

BranchCode v1 remains the underlying synthetic procedure. Internal taskset
package/module names may remain unchanged.

## Presentation Decision

`rich-terminal-output` is not a shipped Techtree Skill.

Use only:

```text
deterministic techtree-python Rich terminal output
deterministic compact gateway output
```

The plugin relays those deterministic results. It does not make a host-model
completion to explain the result.

The only guided host-model completion in v0.1 is the one-turn
`skill-improver` proposal after the user explicitly requests it.

Remove `rich_output_skill_digest` and all corresponding product/release
coordinates before the final ReleaseCore is frozen.

## Binding Release Decisions

- Subject model release candidate: `qwen/qwen3.7-flash`.
- Verifiers commit: `7e1c47d24d055aae587ee8259f77a3e8e193513a`.
- Subject Hermes version: `0.19.0`.
- Raw-platform push remains explicitly disabled and conformance-tested.
- Docker image must be pinned by image-index digest and resolved platform
  digest.
- Missing immutable provider model revision remains the honest
  `model_revision_unavailable` warning.
- Release comparison may be `controlled_with_warnings`.
- The second receipt is a same-benchmark guided Skill-replacement result, not
  a held-out or generalization proof.
- Nothing is uploaded to `techtree.sh`.
- `placeholder_release` is required and has no default.
- `placeholder_release: false` is forbidden until every coordinate is
  concrete.

## Phase 0 — Apply Naming and Scope Migration

Across Python, plugin, and Ash:

1. Change public Climb title/slug/reference to the Hello World values.
2. Change public Campaign title to `Hello World Skill Uplift`.
3. Change starter Skill name/path to `hello-world-starter-v1`.
4. Update CLI headers, gateway copy, website pages, bootstrap prompt, tests,
   goldens, and release fixtures.
5. State prominently that this is a toy mechanism demonstration.
6. Keep BranchCode v1 as the task-family name.
7. Do not rename pinned internal package/module identities solely for
   presentation.
8. Remove the bundled `rich-terminal-output` Skill.
9. Remove its plugin registration, asset checks, release digest, website
   coordinate, founder gate, and runtime invocation.
10. Make deterministic CLI/gateway presentation the entire released result
    path.
11. Regenerate all affected schemas, goldens, catalog objects, and cross-repo
    release copies.
12. Verify no stale `procedure-transfer-v1` public reference or
    `rich_output_skill_digest` remains in release data.

## Phase 1 — Install the Founder Skill Drafts

Use the two files supplied beside this directive:

```text
skills/hello-world-starter-v1/SKILL.md
skills/skill-improver/SKILL.md
```

Before installing them:

1. Compare each file with the current runtime schemas and guards.
2. Make only compatibility edits required by committed code.
3. Do not weaken any truth, answer-table, one-turn, size, secret, or
   no-memorization guard.
4. If implementation no longer accepts a documented field, adapt the Skill to
   the committed schema; do not modify the schema merely to fit prose.
5. Replace the frontmatter license only if the founder has chosen a different
   license before hashing.
6. Run Hermes Skill validation and repository-specific Skill contract tests.
7. Produce exact byte size and SHA-256 for each final file.

### Starter Skill Calibration

The starter file intentionally uses:

```text
7 × total character count
```

instead of the correct general rule.

Calibrate it against the exact release Campaign and model.

Hard gate:

```text
neutral baseline:       0–2 / 36
starter Skill v1:      20–27 / 36
preferred starter:        24 / 36
proposed/corrected v2:  ≥32 / 36
v2 task uplift:          ≥6 tasks
v2 regressions:          ≤1
```

Procedure:

1. Run static analysis across all frozen inputs.
2. Confirm the wrong and correct rule do not collide on failed tasks.
3. Run at least two paid certification rehearsals.
4. Do not change the scorer or hidden answers.
5. Prefer adjusting only the public introductory membership or the singular
   intentional defect if calibration misses the band.
6. Never retry the user-facing one-turn proposal to force a positive outcome.
7. Preserve negative/tie rendering tests.

### Deterministic Presentation Gate

Prove:

- Terminal output comes from the deterministic Rich renderer.
- Gateway output comes from the deterministic compact renderer.
- No host LLM is called for presentation.
- Scores, statuses, cost, timing, proof grade, and digests come only from
  verified Techtree artifacts.
- Gateway output is bounded and ANSI-free.
- Warning and negative-result language is honest.
- `Techtree Hello World` and the correct iteration labels are shown.
- The result says the task family is synthetic and introductory.

### Skill Improver Gate

Prove:

- Exactly one host completion.
- Full revised `SKILL.md`, not a patch.
- No task-specific input/output pair appears.
- No answer table or memorized exception list.
- No hidden replies or expected answers enter context.
- Source Skill bytes are loaded from the just-verified run snapshot.
- Proposal is scanned and snapshotted through ordinary Techtree logic.
- User sees exact diff, policy, budget, and digests before second approval.
- An unusable proposal does not silently start a second run.

## Phase 2 — Produce a Founder Skill Approval Packet

Write:

```text
release/founder-skill-approval.md
release/founder-skill-approval.json
```

Include:

```text
exact relative path
complete SHA-256
byte size
frontmatter name/version/license
git diff from supplied draft, if any
all validation commands and exit codes
starter calibration run IDs
baseline/v1/v2 scores
cost and timing
first and second proof verification status
known warnings
```

Calculate a canonical digest of the JSON approval packet.

Stop and request this exact founder approval:

```text
APPROVE CLIMB V0.1 FOUNDER SKILLS
packet_digest: sha256:<complete-digest>
starter_skill_digest: sha256:<complete-digest>
skill_improver_digest: sha256:<complete-digest>
```

Do not generate final ReleaseCore until the founder approves the exact Skill
packet.

## Phase 3 — Freeze Source and Generate ReleaseCore

After Skill approval:

1. Commit the exact two Skill files.
2. Complete the single WP11 engine-bundle regeneration.
3. Regenerate engine, taskset, Campaign, Climb, catalog, schemas/goldens, and
   cross-repository release copies in the approved order.
4. Run every drift check.
5. Require all source trees clean.
6. Freeze the Python source commit.
7. Generate ReleaseCore with exact Skill, engine, catalog, and source values.
8. Confirm ReleaseCore contains `starter_skill_digest` and
   `skill_improver_digest`, and contains no rich-output Skill field.
9. Keep `placeholder_release: true` until all external artifacts exist.
10. Verify byte-identical ReleaseCore across Python, plugin, and website
    release source.

## Phase 4 — Build External Release Artifacts

Follow the cycle-safe order:

1. Build the CLI wheel from the clean frozen Python source.
2. Inspect the wheel and compute SHA-256.
3. Install it into a fresh home with the exact proposed argv.
4. Require `techtree release verify` to pass.
5. Commit/tag the plugin with the exact ReleaseCore and skill-improver Skill.
6. Obtain the full 40-character plugin commit.
7. Generate BootstrapRelease using the wheel hash and plugin commit.
8. Add the exact Hello World starter-Skill source URL coordinate.
9. Import the BootstrapRelease into the read-only Ash release source.
10. Run cross-repository equality and bootstrap verification.
11. Keep `placeholder_release: true` until the founder approves the packet.

## Phase 5 — Generate the Concrete Release Approval Packet

Populate `RELEASE_COORDINATES_TEMPLATE.json` with actual values and write:

```text
release/founder-release-approval.json
release/founder-release-approval.md
```

The packet must surface:

```text
public Hello World naming fields
release ID
ReleaseCore digest
BootstrapRelease digest
CLI version and source commit
wheel origin, filename, and SHA-256
plugin repository, version, and full commit
exact install argv arrays
engine digest
catalog digest
Hello World Climb reference and digest
Campaign digest
DataPolicy digest
two Skill digests
model ID and provider profile
accepted model-revision warning
Verifiers commit
subject Hermes version
host Hermes tested range
OCI image-index digest
resolved platform digest
published budget
website origin and documentation URLs
placeholder_release value
deterministic-presentation-only status
```

Attach evidence:

```text
all three repo quality gates
generated-file drift checks
fresh wheel installation
plugin doctor
clean terminal journey
reference phone/gateway journey
first proof verification
second proof verification
no-upload network assertion
plugin disable/remove test
CLI uninstall/data-retention test
privacy/security review
```

Reject the packet when any coordinate is:

```text
latest
main
TBD
empty
a short commit
an unpinned package range
a mutable image tag without digest
a missing wheel hash
a missing Skill digest
placeholder_release omitted
```

Also reject when:

```text
rich_output_skill_digest is present
rich-terminal-output is registered or packaged
public Climb reference is not hello-world-climb@1
```

## Phase 6 — Stop for Final Founder Approval

Do not publish the wheel, tag a public release, flip `placeholder_release` to
false, or deploy the public bootstrap unless the founder supplies an approval
that names the exact packet digest.

Request:

```text
APPROVE CLIMB V0.1 RELEASE
approval_packet_digest: sha256:<complete-digest>
release_id: <exact-release-id>
release_core_digest: sha256:<complete-digest>
bootstrap_release_digest: sha256:<complete-digest>

Authorized:
- publish the exact CLI wheel in this packet
- publish/tag the exact plugin commit in this packet
- set placeholder_release to false
- deploy the read-only Hello World bootstrap/catalog release at techtree.sh

Not authorized:
- upload user receipts, Episodes, Traces, proof bundles, or Skill proposals
- enable a leaderboard or submission endpoint
- add Relay, remote execution, or training export
```

Any changed byte after approval invalidates the approval and requires a new
packet digest.

## Phase 7 — Execute Approved Release Only

After exact approval:

1. Publish only the approved wheel.
2. Verify the published artifact hash.
3. Publish/tag only the approved plugin commit.
4. Generate the final bootstrap with `placeholder_release: false`.
5. Verify the final bootstrap digest matches the approved packet.
6. Deploy only the read-only Hello World web release.
7. Run one post-deploy bootstrap smoke test.
8. Run one fresh install and Doctor check from public coordinates.
9. Do not make an additional paid evaluation unless release artifact bytes
   differ from the certified bytes.
10. Produce a final launch report with all public URLs, digests, and rollback
    commands.

## Scope Lock

Do not add:

```text
rich-terminal-output as a product Skill
host-model result narration
NeMo Relay
Prime compatibility guide migration
public receipt upload
proof publication
leaderboards
remote evaluation
more than one guided revision
new harnesses
private programs
training export
```

The task is done when a clean user can install the pinned plugin, approve the
pinned CLI installation, run both local comparisons, see both deterministic
Hello World result presentations, verify both local proof bundles, and no
artifact is uploaded.
