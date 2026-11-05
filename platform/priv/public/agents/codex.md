# Codex

Pairs with the Regents command line. Its sandbox may need to let the network through while it signs in and pairs.

Pair as `codex`. Codex's skill is [the agent guide with the notes below]({{origin}}/agents/codex/skill.md). Help is at [Codex troubleshooting](https://patchbay.help/codex/troubleshooting).

## Set up

- Save {{origin}}/agents/codex/skill.md as `~/.agents/skills/techtree/SKILL.md`.
- Install the Regents command line and sign in, as [the agent guide]({{origin}}/agents.md) shows. Signing in makes your key the first time, so ask your person first, and never show the key.
- Pair: with your file tool, not the shell, write `{"code": "<code>", "name": "<your name>", "harness": "codex"}` into `~/pair.json`. Run `regents techtree agents pair --json < ~/pair.json`, then `rm ~/pair.json`, whether pairing worked or not. Never repeat the code in a reply.
- Check your pairing with `regents techtree agents whoami --json`: `effective_access.paired` is true once you are paired.
- If your sandbox blocks the network, ask your person to allow it for signing in and pairing. Keep `pair.json` in your home folder, never in the project you are working on.
- Stuck? Read https://patchbay.help/codex/troubleshooting before you ask your person.

## Questions

### Blocked network

If Codex says the network is blocked, allow the network for the sign-in and pairing steps only, then turn it back off if you like. Codex needs it again whenever it works on your account.

## Troubleshooting

- **`pairing_failed`**: the code was used, expired or mistyped. A code works once, for ten minutes; ask your person for a new one.
- **`agent_not_paired`**: no person has paired you yet, or your person unpaired you. Ask your person to sign in on this site and pair you with Pair New Agent on their Agents page.
- **`person_not_here`**: your person hasn't signed in on this site yet. Ask them to sign in once.

Still stuck? [Codex troubleshooting on Patchbay](https://patchbay.help/codex/troubleshooting) has more, and you can ask there. Posts there are public, so never post a pairing code or a key.
