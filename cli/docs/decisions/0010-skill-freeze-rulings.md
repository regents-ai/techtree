# 0010 — Binding rulings before the Skill freeze

Status: binding (author rulings relayed by the founder, 2026-08-13).
Answers the two chief-queued questions from the Phase-1 compatibility
review and adds four directives. The closeout-pack Skill digests
(0009 table) are **intentionally superseded** and must not be
founder-approved; new bytes and digests are produced after the edits
below.

## 1. skill-improver is operative, not ceremonial

The exact verified founder `skill-improver` text must be included in
the single host-model completion request. The existing hardcoded
instruction block shrinks to a small non-overridable safety envelope
(exactly one completion, exact structured-output schema, no hidden
material, no executable attachments, no automatic retry, no automatic
second run). Precedence: safety envelope → founder Skill → sanitized
evidence + verified source Skill → output schema. A conflict between
the founder Skill and the envelope is a release-test failure; the
runtime must not silently ignore either.

The single-turn request commits to: `skill_improver_digest`,
`improvement_context_digest`, `source_skill_root_digest`,
`source_skill_entrypoint_digest`, `output_schema_digest`,
`complete_request_digest`, `host_model_id`, `host_response_digest`,
`revision_attempt = 1` — and candidate Skill v2 provenance carries all
of them. Required tests: changing only the verified skill-improver
text changes the host request digest, the instruction content, and the
candidate provenance; a test double proves the Skill text appears
exactly once in the completion request.

## 2. The evaluated starter must not disclose its own defect (amends 0007 R4)

0007 R4's "self-identifies as intentionally incomplete" is amended:
the *release metadata* discloses, the *evaluated Skill content* does
not. Mounting a defect disclosure would contaminate the evaluation.
Disclosure locations: the public Climb page ("The Hello World starter
Skill is intentionally incomplete so the guided one-turn revision has
measurable headroom."), the CLI preparation output (starter artifact
name + "Purpose: intentionally incomplete introductory Skill"), and
the release calibration record (`intentional_defect`: total character
count used where the complete procedure uses distinct-character
count). The current draft body is correct on this point.

## 3. Starter description: exact trigger, not the method

Frontmatter description becomes exactly:
`Apply BranchCode v1 and return a BRANCH-XX token.`
The lean description is deliberate — the procedure must never move
into frontmatter, or discovery metadata would deliver the intervention
without the Skill being opened. Before calibration, a two-task
discovery probe (one all-unique input, one repeated-character input)
must confirm from the trace: Hermes discovered/opened the Skill, the
first input followed the procedure, the second exhibited the intended
defect, and the procedure was not supplied via frontmatter.

## 4. skill-improver prose loses guard-trigger vocabulary

The Prohibited Strategies section and the "No answer table."
requirement are rewritten in semantic language (exact replacement text
in the founder ruling, mirrored into ticket notes): "evaluation-case
mappings", "case-specific exceptions", etc. — so the prompt does not
teach the model the exact phrases the deterministic guard flags. The
guard itself is unchanged. New digest; compatibility/contract pass
re-run.

## 5. Materialization: path, name, and label are separate values

A file path must never double as a Skill name or candidate label. The
materialization response exposes `skill_path`, `skill_name`
(`hello-world-starter-v1`), and `candidate_label` (`hello-world-v1`);
the suggested next action uses the real path and the bounded semantic
label, and never derives a label from a path, temp-dir name, object
URL, or filename. Regression tests: >200-char source path, spaces in
parent dirs, digest-based directory, frontmatter name stays valid,
suggested command works verbatim, label never comes from the path,
JSON returns argv elements. Release blocker.

## 6. Freeze sequence

Wire improver text → minimize hardcoded prompt to envelope → starter
description edit → improver prose edit → materialization fix → static
+ contract tests → two-task discovery probe → starter calibration
rehearsals → one complete guided v1→v2 rehearsal → new exact Skill
bytes and digests → founder-skill approval packet → STOP for founder
approval. No ReleaseCore freeze and no release-coordinate approval
until all six items are green. The approval packet must state that the
closeout-pack files received these founder-directed pre-freeze edits.
