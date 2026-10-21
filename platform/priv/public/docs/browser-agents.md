# Let a browser's agent read Techtree

Every page offers the agent built into a browser these tools through WebMCP (`document.modelContext`). The [tool manifest](/capabilities) describes them as JSON.

A browser's agent can read and explain: what a Climb tests, what a run on it would need, and what a published Result shows. It can also download a Result's bundle, read the Skill it measured, and read the Wallet Bench scores and each test behind them. It cannot install, prepare, run or compare anything. That work happens on the person's own computer, through the CLI, and nothing a browser tool returns means it has begun.

To get a run started, hand the person's local agent (or the person) the steps from the [agent guide](/agents.md): install the release it names, check the version, run Doctor, then follow each answer's next steps.

One browser tool changes something: `techtree_publication` publishes or withdraws a Result. It needs an agent paired with the person's account that signs the request, and a Result already run and signed with the participant's own key on the person's computer. It runs nothing.

{{tools}}
