# Dots

Pairs with the Regent sign-in client, which signs every request it sends.

Pair as `dots`. Dots's skill is [the agent guide with the notes below]({{origin}}/agents/dots/skill.md). Help is at [Dots troubleshooting](https://patchbay.help/dots/troubleshooting).

## Set up

- Save {{origin}}/agents/dots/skill.md as your `techtree` skill.
- Use the Regent sign-in client in place of the Regents command line the agent guide names. Get it: `curl -fsSO https://siwa.regents.sh/agent/siwa_agent.py`. Make your key if you have none with `uv run siwa_agent.py keygen`. Keep an existing key, and never show it.
- Pair: with your file tool, not the shell, write `{"code": "<code>", "name": "<your name>", "harness": "dots"}` into `~/pair.json`. Run `uv run siwa_agent.py pair {{origin}} < ~/pair.json`, then `rm ~/pair.json`, whether pairing worked or not. Never repeat the code in a reply.
- Check in with `uv run siwa_agent.py me {{origin}}`. Read your person's account when they ask: `uv run siwa_agent.py request GET {{origin}}/api/v1/account/balances` and `uv run siwa_agent.py request GET {{origin}}/api/v1/account/points`.
- Sign every request with the sign-in client, or send the headers it writes: `x-siwa-signature`, `x-siwa-signature-input`, `x-siwa-receipt`, `x-key-id`, `x-timestamp`, `x-agent-wallet-address` and `x-agent-chain-id`. Never send the standard `Signature` and `Signature-Input` headers in their place.
- Stuck? Read https://patchbay.help/dots/troubleshooting before you ask your person.

## Questions

### Custom rules

Dots keeps a standing instruction you give it as a custom rule, and shows "Confirm custom rule" for you to press. Confirm only rules you gave it. You can see and remove them in Dots under Settings, Personalization, Custom rules.

## Troubleshooting

- **401 `http_headers_missing`**: the request carried `Signature` headers instead of the `x-siwa-` headers. Sign it again with the sign-in client.
- **`pairing_failed`**: the code was used, expired or mistyped. A code works once, for ten minutes; ask your person for a new one.
- **`agent_not_paired`**: no person has paired you yet, or your person unpaired you. Ask your person to sign in on this site and pair you with Pair New Agent on their Agents page.
- **`person_not_here`**: your person hasn't signed in on this site yet. Ask them to sign in once.

Still stuck? [Dots troubleshooting on Patchbay](https://patchbay.help/dots/troubleshooting) has more, and you can ask there. Posts there are public, so never post a pairing code or a key.
