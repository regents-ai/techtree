# SkillOpt Climb template

Microsoft Research's SkillOpt (github.com/microsoft/SkillOpt, MIT, v0.2.0, arXiv 2605.23904)
becomes a Climb template (Sean, 3 a, 2026-10-05). A run improves a Skill against a Climb's tasks
and ends as an ordinary Climb Result, with a record of each edit and what it cost.

## Decided

- **Spend limit (103 a, 2026-10-06):** $25 per run by default, paid by the person through their
  own key. SkillOpt has no spend limit of its own; the template enforces this one.
- **Two models:**
  - The model doing the tasks is the Climb's own fixed model, so the before and after scores
    compare. It is not configurable.
  - The model writing the Skill edits (SkillOpt's optimizer) is configurable. The default is
    `anthropic/claude-opus-5.5` at effort `high` (Sean, 1 a, 2026-10-06), $4 in and $20 out
    per million tokens on Prime.
- **Route:** the person's own Prime key only. The ChatGPT plan route (59 a) serves OpenAI
  models only, so it cannot run this optimizer.

## Effort

SkillOpt v0.2.0's OpenAI-compatible backend, the one that reaches Prime, drops
`reasoning_effort` before sending (`skillopt/model/openai_compatible_backend.py`,
`del reasoning_effort`). Prime's model card for `anthropic/claude-opus-5.5`
(`GET https://api.pinference.ai/api/v1/models/anthropic/claude-opus-5.5`, read 2026-10-06)
says reasoning is mandatory, the default effort is `high`, and `reasoning_effort` is a
supported parameter. So the optimizer runs at `high` today. The template sends
`reasoning_effort: "high"` itself so the run does not depend on Prime's default.

The approved test call (about $0.01) was refused with 402 before it ran: the Regents Labs team
has no Prime inference balance. Nothing was charged. The model card settles the question; the
first funded SkillOpt run records the effort it used.

## Still open

- Built after the two-route Campaign change (105 b) lands in climb-v0.7.0.
- Template shape: pinned SkillOpt version, its settings, a practice / check / scoring split of
  the Climb's tasks (the optimizer never sees the scoring tasks), and the spend limit above.
