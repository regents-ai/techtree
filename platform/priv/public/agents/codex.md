# Codex

## Set up

- Save {{origin}}/agents/codex/skill.md as `~/.agents/skills/techtree/SKILL.md`.
- Install the Regents command line and sign in, as [the agent guide]({{origin}}/agents.md) shows. Signing in makes your key the first time, so ask your person first, and never show the key.
- Pair: with your file tool, not the shell, write `{"code": "<code>", "name": "<your name>", "harness": "codex"}` into `~/pair.json`. Run `regents techtree agents pair --json < ~/pair.json`, then `rm ~/pair.json`, whether pairing worked or not. Never repeat the code in a reply.
- Check your pairing with `regents techtree agents whoami --json`: `effective_access.paired` is true once you are paired.
- If your sandbox blocks the network, ask your person to allow it for signing in and pairing. Keep `pair.json` in your home folder, never in the project you are working on.
- Stuck? Read https://patchbay.help/codex/troubleshooting before you ask your person.
