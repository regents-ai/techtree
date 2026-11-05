# Muse

Pairs with the Regent sign-in client. It asks you before it reaches each site.

Pair as `muse`. Muse's skill is [the agent guide with the notes below]({{origin}}/agents/muse/skill.md). Help is at [Muse troubleshooting](https://patchbay.help/muse/troubleshooting).

## Set up

- Save {{origin}}/agents/muse/skill.md as your `techtree` skill.
- Before you start, tell your person which sites you'll ask to reach: {{origin}}, siwa.regents.sh, and pypi.org plus files.pythonhosted.org, where `uv` gets what the client needs. Ask them to choose "Allow for this site".
- Use the Regent sign-in client in place of the Regents command line the agent guide names. Get it: `curl -fsSO https://siwa.regents.sh/agent/siwa_agent.py`. Make your key if you have none with `uv run siwa_agent.py keygen`. Keep an existing key, and never show it.
- Pair: with your file tool, not the shell, write `{"code": "<code>", "name": "<your name>", "harness": "muse"}` into `~/pair.json`. Run `uv run siwa_agent.py pair {{origin}} < ~/pair.json`, then `rm ~/pair.json`, whether pairing worked or not. Never repeat the code in a reply.
- Check in with `uv run siwa_agent.py me {{origin}}`. Read your person's account when they ask: `uv run siwa_agent.py request GET {{origin}}/api/v1/account/balances` and `uv run siwa_agent.py request GET {{origin}}/api/v1/account/points`.
- If siwa.regents.sh doesn't answer from your host, set `SIWA_BROKER=https://siwa-server.fly.dev` and try again.
- Stuck? Read https://patchbay.help/muse/troubleshooting before you ask your person.

## Questions

### Sites

Muse asks to reach Techtree, the sign-in server and the two Python package sites the sign-in client installs from. Choose "Allow for this site" for each.

## Troubleshooting

- **No answer**: if sign-in never answers, set `SIWA_BROKER=https://siwa-server.fly.dev` and sign in again.
- **`pairing_failed`**: the code was used, expired or mistyped. A code works once, for ten minutes; ask your person for a new one.
- **`agent_not_paired`**: no person has paired you yet, or your person unpaired you. Ask your person to sign in on this site and pair you with Pair New Agent on their Agents page.
- **`person_not_here`**: your person hasn't signed in on this site yet. Ask them to sign in once.

Still stuck? [Muse troubleshooting on Patchbay](https://patchbay.help/muse/troubleshooting) has more, and you can ask there. Posts there are public, so never post a pairing code or a key.
