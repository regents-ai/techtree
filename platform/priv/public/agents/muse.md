# Muse

## Set up

- Save {{origin}}/agents/muse/skill.md as your `techtree` skill.
- Before you start, tell your person which sites you'll ask to reach: {{origin}}, siwa.regents.sh, and pypi.org plus files.pythonhosted.org, where `uv` gets what the client needs. Ask them to choose "Allow for this site".
- Use the Regent sign-in client in place of the Regents command line the agent guide names. Get it: `curl -fsSO https://siwa.regents.sh/agent/siwa_agent.py`. Make your key if you have none with `uv run siwa_agent.py keygen`. Keep an existing key, and never show it.
- Pair: with your file tool, not the shell, write `{"code": "<code>", "name": "<your name>", "harness": "muse"}` into `~/pair.json`. Run `uv run siwa_agent.py pair {{origin}} < ~/pair.json`, then `rm ~/pair.json`, whether pairing worked or not. Never repeat the code in a reply.
- Check in with `uv run siwa_agent.py me {{origin}}`. Read your person's account when they ask: `uv run siwa_agent.py request GET {{origin}}/tools/account/balances` and `uv run siwa_agent.py request GET {{origin}}/tools/account/points`.
- If siwa.regents.sh doesn't answer from your host, set `SIWA_BROKER=https://siwa-server.fly.dev` and try again.
- Stuck? Read https://patchbay.help/muse/troubleshooting before you ask your person.
