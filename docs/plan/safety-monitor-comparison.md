# Safety: compare two monitors on the same transcripts

Founder brief, 2026-09-11: *Choose a test. Compare two monitors. See what
they missed.* A small addition to the platform, not a new product. One fixed
test pack, two monitor presets, one run button, one comparison table,
expandable evidence. Nothing more.

## What exists (platform, `platform/`)

| Route | Purpose | Main action |
| --- | --- | --- |
| `/safety/protected-file-edits` | Understand the test and configure a comparison | **Run comparison** |
| `/safety/runs/:id` | Follow progress, read the comparison, open the evidence | **Inspect a case** |
| `/safety/runs/:id/evidence` | The whole run as one JSON file | Download |

`/safety` (browse tests) is deliberately absent until there is more than one
test, as the brief says.

### The test pack

`Techtree.Safety.TestPack`, authored in code. *Protected-file edits*, v1:
twenty synthetic transcripts, ten violations and ten compliant cases,
interleaved. Every case carries an independent record of what happened and,
for a violation, the event it happened at. The monitors never see the record.
The cases are built to separate a careful monitor from a casual one: a file
edited then restored, a formatter that reports touching a test file, a patch
applied from an allowed file, a near-miss path, a proposed change that was
never made.

### The monitors

`Techtree.Safety.Monitor`: two system prompts, *Basic prompt* and
*Evidence-first prompt*, both answering in one JSON shape (`flag`, `clear`,
`abstain`, plus a rationale and an evidence event). A failed call or an
unreadable answer is an `error`, kept apart from every verdict. The prompts
and the model are shown on the test page under *View monitor prompts*.

### The run

`Techtree.Safety.Run` (Ash resource, table `safety_runs`) records the run
and every verdict as one document column. `Techtree.Safety.Runner` evaluates
both monitors over every case, four cases at a time, and broadcasts each
recorded case to the results page. Cancel closes the run as cancelled with
what it has; the runner sees that at its next write and stops. A crash closes
the run as failed. Neither ever writes `complete`.

`Techtree.Safety.Scoring` computes missed violations, false alarms,
abstentions and errors per monitor from the verdicts every time the page
reads them, and writes the one tradeoff sentence. It names no winner.

## Decisions taken while building (founder to confirm or overturn)

1. **Model and funding.** The site makes the calls, with Anthropic's
   `claude-haiku-4-5-20251001` at temperature 0, one call per monitor per
   case (40 per comparison). The key is read at boot from
   `TECHTREE_SAFETY_ANTHROPIC_API_KEY` and nowhere else. Without it the test
   page says comparisons are not switched on and has no run button. Setting
   that variable on a deployed site is the moment platform-funded inference
   begins, and it is a founder action.
2. **Free, capped demo.** The test page discloses the cost in calls, who pays,
   and how many of the day's comparisons remain before the button. The cap is
   `daily_run_cap` in `config :techtree, Techtree.Safety` (25 a day, site-wide).
   There is no paid tier yet.
3. **Public runs.** Every pack is synthetic, so packs and runs are readable
   without signing in. Private packs and private runs are a later addition
   that reuses these screens.
4. **Shareable case address.** An expanded case lives at `?case=N` rather than
   a `#case-N` fragment, because the page expands it on the server and a
   fragment never reaches the server. Every case row still carries
   `id="case-NN"`, and every event `id="case-NN-event-M"`, so the evidence
   links jump straight to the event.

## Verification

`mix check` in `platform/` (format, compile with warnings as errors, the
existing suite). Behaviour is verified by running it: both pages in the
browser at desktop and mobile widths, the evidence download, and a driver
script against a disposable run in the development database for the refused
write after a run is closed. No tests are kept for this feature (founder
decision, 2026-09-15). No real model call has been made from this code.
