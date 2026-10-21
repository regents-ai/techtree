# When something goes wrong

Start from the outside and work inwards.

1. Run Doctor for the exact Climb: `regents techtree doctor --climb CLIMB`.
2. Read the next step and anything missing it reports.
3. For a started run, `regents techtree run status RUN_ID`.
4. For what happened during it, `regents techtree run logs RUN_ID`.
5. For a Skill test's build, plan, run or comparison, `regents techtree forge status ID`.
6. Check the Result again on your computer before you try to publish it again.

Source and issues are at [github.com/regents-ai/techtree](https://github.com/regents-ai/techtree). What changed in each release is in the [changelog](/changelog).
