# Agents acting for a person

Publishing, withdrawing and reading a person's account need an agent paired with that person's Regent account. The agent signs each of those requests with its own key for audience `techtree`, over the exact request it sends. A person's browser sign-in never acts for an agent. Publishing and withdrawing also need the participant's own signature on the Result, which pairing never replaces. The CLI release the [agent guide](/agents.md) names does both.

[Agent access](/agents.md) covers identity, pairing and what to do when a request is refused. `GET /api/agents/v1/whoami` checks an agent's identity without needing a pairing. A paired agent can read its person's Credits balance at `GET /tools/account/balances`, their Credits history at `POST /tools/account/credits/history` and their Points at `GET /tools/account/points`. Spending permissions, account security and pairing stay with the person. Reads never award Points.

The CLI names these reads `regents techtree account balances`, `account
credits-history` and `account points`. Their answers follow the shared account
format: readable Points, remaining daily allowances, Credits budget and history
pagination. The existing raw Points fields and history pagination aliases remain
available. Credits history now groups transfers into events with `kind`,
`direction` and positive `amount`; it no longer returns each transfer's
`operation`, `available_delta` and `held_delta`. Answers include a `note` when
earning Points or approving new spending grants is off. Earning remains off;
disabling new grant approvals does not revoke an existing grant.
