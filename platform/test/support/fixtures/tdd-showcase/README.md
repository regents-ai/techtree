# Test fixture: tdd showcase folder

Test data only. These are not real results and must never be copied into
`priv/examples/tdd-showcase/`.

The folder has the layout `TechtreeWeb.TddShowcase` reads. Every record was
written by the Techtree CLI's own code, driven by the scripted stand-ins of
its forge tests (planner, creator, Docker and Hermes), on 2026-09-25. No model
was called and no task was run. The claims and the eight task summaries were
written for the stand-in planner, and the scores were set per task so that
the held-out part is mixed and the study part improved.

- `comparison.json`: the `forge compare` record of the two runs.
- `runs/baseline/spec.json`, `runs/candidate/spec.json`: each run's
  specification, as `forge run` wrote it.
- `claims-and-tasks.json`: the accepted proposal's claims and tasks.
- `export/README.md`, `export/export.json`: from `forge export` of the
  accepted collection (the task folders are left out).
- `skill/tdd/`: Matt Pocock's `tdd` Skill (mattpocock/skills 1.2.3, MIT) as
  the stand-in runs carried it, with the repository's licence copied in as
  `LICENSE.txt`.

`../tdd-showcase-variants/` holds the comparison records of four more pairs of
stand-in runs, made in the same session on the same collection with the same
run specifications, whose held-out tasks came out regressed, no different,
with one task missing a score, and with too few tasks scored on both runs.
Each replaces this folder's `comparison.json` in the tests.
