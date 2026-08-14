---
name: hello-world-starter-v1
description: Apply BranchCode v1 and return a BRANCH-XX token.
version: 0.1.0
author: Sean Brennan, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [techtree, hello-world, branchcode, evaluation]
    related_skills: []
---

# Techtree Hello World Starter Skill

Use this Skill when a task asks you to apply **BranchCode v1** to a
lowercase text input and return one final token.

BranchCode v1 is the synthetic procedure used by the **Techtree Hello World**
introductory Climb. It is a toy task family for demonstrating controlled Skill
uplift, not a general-purpose coding standard or broad capability benchmark.

## Procedure

1. Strip surrounding whitespace and convert the input to lowercase.
2. Require every remaining character to be an ASCII letter from `a` to `z`.
3. Map letters to values with `a = 1`, `b = 2`, through `z = 26`.
4. Multiply each letter value by its one-indexed position in the input.
5. Sum all of those position-weighted values.
6. Add `7` times the total number of characters in the normalized input.
7. Reduce the result modulo `97`.
8. Format the result as `BRANCH-XX`, where `XX` is a zero-padded
   two-digit decimal number.

## Output Contract

- Return exactly one `BRANCH-XX` token.
- Do not include reasoning, arithmetic, punctuation, Markdown, or commentary.
- Preserve a leading zero when the result is less than ten.
- Do not guess when the input contains unsupported characters.
