---
name: fixture-rich-terminal-output
description: TEST FIXTURE, NOT THE FOUNDER SKILL. A stand-in that follows the rich-terminal-output behavioural contract so the loading, digest, and contract checks can be tested before the real Skill exists.
---

# FIXTURE — not the founder Skill

This file is a test fixture. It is not the founder-supplied
`rich-terminal-output` Skill, it is not pinned by any release, and it must
never be shipped as one. It exists so that the digest verification and the
contract checks have something contract-shaped to run against.

## Purpose

Choose how to word a comparison result that Techtree has already computed.

## Contract

- Produce only narrative choices: a headline, the observations to emphasize,
  one caveat to foreground, and an explanation of the next step.
- Never output a score.
- Never output a delta.
- Never output wins, losses, or ties.
- Never output a cost.
- Never output a timing.
- Never output a proof grade.
- Never output a status.
- Never output a digest.
- Never output a command.
- Never alter any number, verdict, or status that was given to you.

## What you are given

The deterministic presentation payload, already computed. Read it, and choose
what deserves emphasis. The numbers are rendered separately by Techtree; your
words appear beside them, never instead of them.

## What to say when nothing improved

Say it plainly and first. A comparison that shows no improvement is a
comparison that worked. Do not soften it, and do not look for a smaller number
that sounds better.
