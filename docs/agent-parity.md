# Agent parity

An action only a person can do is a bug (founder rule, 28 October 2026). Each action a
visitor can take on Techtree has a row here naming its five agent surfaces: the website in a
headless browser, WebMCP, hosted MCP at `/mcp`, the Claude connector, and the regents CLI.
Each surface reads the same records with the same answers and refusals. A missing surface is
a gap with the lane that closes it.

Hosted MCP (`/mcp`) is not on Techtree's main branch yet: it waits on branch
`connector-mcp-1108`, so every hosted MCP cell is a gap owned by the **hosted MCP lane**. The
Claude connector is served from hosted MCP, so every Claude connector cell is a gap owned by
the same lane. The checks that prove each surface are in `docs/feature-map.md`.

This file starts with Train. **Gap:** the site's other actions (Results, Climbs, the Wallet
Bench, Verify, the account pages) are not listed here yet; their checks are in
`docs/feature-map.md`.

## Train

Public reads; none needs a sign-in. Every read goes through `Techtree.Train.Comparisons`,
so a report whose digest or traces do not check out is refused on every surface alike. CLI
cells are gaps owned by the **regents-cli lane**: `regents techtree` has no Train command.

| Action | Operation | Browser | WebMCP | Hosted MCP | Claude connector | CLI |
| --- | --- | --- | --- | --- | --- | --- |
| List the comparisons, newest first | `Comparisons.list` | `/train` | `train_comparisons` (`GET /train.json`) | Gap: hosted MCP lane | Gap: hosted MCP lane | Gap: regents-cli lane |
| Read one comparison with every task | `Comparisons.fetch` | `/train/{slug}` | `train_report` (`GET /train/{slug}/report.json`) | Gap: hosted MCP lane | Gap: hosted MCP lane | Gap: regents-cli lane |
| Download a comparison's report | `Comparisons.download`, `:report` | `/train/{slug}`, Report | `train_report` | Gap: hosted MCP lane | Gap: hosted MCP lane | Gap: regents-cli lane |
| Download a comparison's traces | `Comparisons.download`, `:traces` | `/train/{slug}`, Traces | Gap: Train lane. `train_comparisons` gives each `traces_url`; no tool reads it | Gap: hosted MCP lane | Gap: hosted MCP lane | Gap: regents-cli lane |
| Ask about private training | `TechtreeWeb.TrainCopy.private_mailto` | `/train`, Email build@regents.sh | Not a tool: `/agents.md` and `/train` as Markdown give the address, and the person writes the email | Gap: hosted MCP lane | Gap: hosted MCP lane | Gap: regents-cli lane |
