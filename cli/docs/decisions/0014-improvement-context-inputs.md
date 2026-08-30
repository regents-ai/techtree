# 0014 — The improvement context carries public task inputs; guard refusals tell the truth

Status: binding (chief rulings under already-ratified permissions,
2026-08-13). Founder/author may veto before the Skill freeze.

## Finding (rehearsal attempts 1 and 2, both disclosed)

Two rehearsal attempts produced unusable proposals, and the diagnosis
exonerates the founder improver Skill:

1. The improvement context hands the host model, per task, an outcome
   word, a reward, and a hash-derived label — `public_prompt` is
   hardcoded `None` in `src/techtree/uplift/context.py`. The planted
   defect ("failures are exactly the inputs that repeat a character")
   is undiscoverable without seeing inputs; the model's wrong
   diagnosis (non-ASCII filtering) is what a competent reasoner
   produces about a pattern it has no evidence for. Attempt 2 had
   10,834 unused completion tokens, killing the token-squeeze
   hypothesis.
2. Attempt 2's proposal was a complete SKILL.md emitted without any
   newline characters. The plugin guard refused it as "a diff rather
   than a complete SKILL.md" because the newline-free frontmatter
   opener (`--- n…`) matches the diff-header pattern. The refusal is
   right; the stated reason is false, and a participant would be
   misled by it.

## Rulings

1. **Populate the public task input in the improvement context.**
   Ratified decision R1 already says the context MAY include the
   public task input/label and requires excluding only the subject
   reply, the expected answer, grader source, and hidden fields. The
   BranchCode input is a public tree name; the answer stays hidden.
   `public_prompt` carries the real public input; every existing
   sanitization invariant (no replies, no expected answers, no grader
   material, no secrets, no local paths) stays contract-tested.
2. **The guard refuses the newline-free file for the true reason.**
   Structure is validated first (a complete SKILL.md has parseable
   frontmatter and line structure); the diff-header patterns then
   apply to real lines. A single-line blob is still refused — as
   malformed, which it is — and nothing is weakened: every previously
   refused shape is still refused.
3. **Rehearsal attempt 3 authorized after both fixes**, one
   completion, raw bytes persisted before judgment, honest outcome.
   These fixes are not improver-Skill revisions, so 0013's one-time
   improver-revision lever remains unused. If attempt 3 still misses
   the defect WITH inputs visible, that lever is next, decided with
   the author on preserved bytes.
4. Attempts 1 and 2 are disclosed in the Gate-1 packet in full,
   including the lost attempt-1 bytes, the shim token ceiling, this
   diagnosis, and these rulings.
