# Run locally

Techtree runs on your own computer and shows what a Skill changes: it makes tasks from the Skill, and your agent works them once without it, or with its earlier version, and once with it. Only the Skill changes, so the difference is the Skill's.

## Steps

1. **Inspect.** Techtree reads the Skill's files without running any of them and tells you what it can use.
2. **Review.** Before a model sees your Skill, you see what would be sent, to which provider, and the limits. Nothing runs until you say yes.
3. **Tasks.** Tasks are built and checked, and you choose which to keep. Some are held out from anyone improving the Skill.
4. **Compare.** Your agent works the tasks without the Skill, or with its earlier version, and then with it. Each run shows the most it may spend and waits for your yes.
5. **Decide.** Techtree compares the two runs task by task and says whether the Skill improved, regressed, was mixed or made no difference, with the held-out tasks judged on their own.

## Your data

Nothing is uploaded to Techtree. Making the tasks and running them send your Skill's files and the tasks to the model provider you chose, only after you approve the review that says so. Episodes and traces stay on your computer. Publishing a finished Result is optional and uploads only its proof bundle.

## Next

- [Install](/docs/install) names the release and checks this machine.
- [Evaluate & Climb](/docs/test-a-skill) has every command, including the comparison.
- [Hello World](/docs/hello-world) explains the example Climb.
- [Use Hermes](/docs/hermes) lets Hermes run each step.
- [Proof](/docs/verify) shows what a Result proves and how to check one.
- The [agent guide](/agents.md) has every step, for your agent to follow.
