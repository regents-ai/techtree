---
name: skill-improver
description: Propose one general revision to a tested agent Skill.
version: 0.1.0
author: Sean Brennan, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [techtree, skill, improvement, reflection]
    related_skills: []
---

# Techtree One-Turn Skill Improver

Propose exactly one reviewable revision to a tested `SKILL.md` using a
sanitized Techtree improvement context and the verified source Skill text.

The proposal is not proof and must not start another run. Techtree will scan,
snapshot, diff, and evaluate the proposed Skill separately after explicit user
approval.

## Inputs

The caller provides:

- A digest-pinned improvement context.
- The verified source `SKILL.md` text loaded from the completed run snapshot.
- Public task labels or inputs only when policy permits.
- Per-task outcome categories, rewards, public metrics, and safe errors.
- Mutation and size constraints.
- A structured output schema.

The context intentionally omits subject final replies, expected answers,
hidden task fields, grader source, and private paths.

## Objective

Find the smallest **general procedural correction** that best explains the
observed failure pattern while preserving behavior that already works.

Prefer:

1. One general rule over many exceptions.
2. A semantic correction over added verbosity.
3. A change that transfers to unseen inputs of the same task family.
4. Minimal edits to the source Skill.
5. Explicit output and edge-case instructions when those are the true cause.

## Prohibited Strategies

Do not:

- Embed any evaluation case or its result in the revised Skill.
- Add mappings or exceptions tied to particular observed cases.
- Copy any supplied task text, identifier, reply, result, or score into the
  revised Skill.
- Add memorized examples whose purpose is to fit the observed membership.
- Infer or reconstruct hidden verifier material.
- Add scripts, executable attachments, shell commands, network calls, or new
  tools.
- Change the benchmark, scorer, model, harness, runtime, or task membership.
- Delete correct constraints merely to make the Skill shorter.
- Claim the revision will improve, generalize, or pass before evaluation.
- Produce more than one candidate.
- Ask for or perform an automatic retry.

## Revision Method

1. Read the complete verified source Skill.
2. Identify which rules are already supported by successful outcomes.
3. Look for one public, general feature that separates failures from successes.
4. Form one minimal hypothesis about the procedural defect.
5. Revise only the rule or clarification needed to express that hypothesis.
6. Preserve the source frontmatter and overall structure where possible.
7. Return a complete replacement `SKILL.md`, not a patch.
8. Ensure the revised file remains self-contained and does not refer to this
   evaluation, its task IDs, or its result.
9. State realistic tradeoffs and uncertainty.

## Structured Output

Return exactly the schema supplied by the caller. For the current Techtree
release, populate:

- `analysis_summary`
- `change_rationale`
- `revised_skill_markdown`
- `expected_tradeoffs`
- `confidence`

### `analysis_summary`

Briefly describe the general failure pattern and proposed procedural change
without quoting task-specific values or answers.

### `change_rationale`

Provide a short ordered list explaining why this is the smallest general
correction supported by the allowed evidence.

### `revised_skill_markdown`

Return the full proposed `SKILL.md`.

Requirements:

- Non-empty.
- Valid frontmatter and body.
- No NUL characters.
- No secret-like values.
- No task-specific inputs or outputs from the context.
- Contains no evaluation-case mappings or case-specific exceptions.
- No executable material.
- Within the caller's size limit.

### `expected_tradeoffs`

State plausible risks, such as over-specializing a rule or changing behavior
on an edge case. Do not state guaranteed benefits.

### `confidence`

Return exactly one of:

- `low`
- `medium`
- `high`

Confidence describes the evidence for the proposed general rule, not a
prediction that the next evaluation will pass.

## Final Rule

Produce one candidate and stop. The user must see Techtree's deterministic
diff, policy, and budget before any Skill v1-versus-Skill v2 run begins.
