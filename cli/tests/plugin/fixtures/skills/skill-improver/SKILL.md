---
name: fixture-skill-improver
description: TEST FIXTURE, NOT THE FOUNDER SKILL. A stand-in that follows the skill-improver behavioural contract so the loading, digest, and contract checks can be tested before the real Skill exists.
---

# FIXTURE — not the founder Skill

This file is a test fixture. It is not the founder-supplied `skill-improver`
Skill, it is not pinned by any release, and it must never be shipped as one.

## Purpose

Propose exactly one revision of a Skill, from what a finished run is willing
to show about it.

## Contract

- Find one general rule that explains the failure pattern.
- Make the smallest general correction that fixes that rule.
- Never add a task-specific exception.
- Never copy input and output pairs into the Skill.
- Never write an answer table.
- Return one complete revised SKILL.md, not a patch and not a fragment.
- Preserve every rule that is already correct.
- State the tradeoffs your change makes.
- Make exactly one proposal.

## What you are given

The sanitized improvement context, which pins the Skill by digest, and the
verified text of that Skill supplied separately. Nothing else. The context
never contains the expected answers or the subject's replies, and you must not
ask for them or guess at them.

## How to think about a failure

Look for the single rule that, stated correctly, would have made the failing
cases work without breaking the passing ones. If several rules could explain
it, choose the one that generalizes; a rule that only fixes the cases you were
shown is an answer table with extra steps.
