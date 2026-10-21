# Test your Skill

Techtree makes practice tasks from what your Skill teaches, then your agent works them without the Skill and with it. Every step that sends anything to a model prints a review first and waits for your yes. Each command prints the next one.

```sh
regents techtree forge inspect-skill path/to/your-skill
regents techtree forge plan SOURCE_ID --provider PROVIDER --model MODEL
# Review, correct, build and accept, one printed step at a time.
regents techtree forge run --arm baseline --collection COLLECTION_ID --provider PROVIDER --model MODEL
regents techtree forge run --arm candidate --collection COLLECTION_ID --provider PROVIDER --model MODEL --skill path/to/your-skill
regents techtree forge compare BASELINE_RUN_ID CANDIDATE_RUN_ID
```

Both runs use the same provider and model. The comparison calls no model: it pairs every task across the two runs and says whether the Skill improved, regressed, was mixed or made no difference, overall and on the held-out tasks alone. To compare two versions of a Skill, give the baseline run the earlier version with `--skill path/to/earlier-skill`. The [tdd example](/examples/tdd) shows a finished comparison.
