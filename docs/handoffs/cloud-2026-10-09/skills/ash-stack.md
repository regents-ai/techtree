---
name: ash-stack
description: Choose an Ash workflow for cross-layer features or refactors.
---

# Ash Stack

Use the smallest relevant specialist. Product intent and repository authority come
from the current task; this pack supplies Ash-specific judgment, not a delivery ritual.

Before building or reviewing, run elixir-stack's design check: name the standard
tool (Ash, Ecto, Oban, Phoenix, OTP) for each moving part. Code that rebuilds one is
a defect, however correct it is.

## Shared work across the five Ash sites (founder rule, 8 Oct 2026)

Regents, Patchbay, Keyfleet, Autolaunch and Techtree are five similar Ash sites. Site-specific work stays in the site's monorepo. Anything shared goes in two places, in this order:

1. **The shared component library** (`repos/design-system`, the `regent_ui` pin, and the shared Elixir packages in `repos/elixir-utils`): components, primitives, CSS tokens, and library code every site uses.
2. **`repos/ash-template`**: the reference implementation that wires those pieces into a working site (pages, resources, policies, WebMCP tools, skills).

Then, before building a feature in a site monorepo: **check whether ash-template already implements it, use that implementation, and improve it there if it falls short.** Never fork a second copy of a shared feature into one site. When a site needs something the template lacks, the change lands in the library and the template first, then the site re-pins. The ash-template chief owns the template and the shared skills; coordinate the change with that thread.

| Work | Reference |
| --- | --- |
| Resources, actions and domain interfaces | [ash-backend](../ash-backend/SKILL.md) |
| Forms, LiveView and presentation | [ash-frontend](../ash-frontend/SKILL.md) |
| Schema changes, SQL and concurrency | [ash-data](../ash-data/SKILL.md) |
| Policies, actors and data exposure | [ash-security](../ash-security/SKILL.md) |
| Regression design or test cleanup | [ash-testing](../ash-testing/SKILL.md) |
| Agent readiness, shared discovery metadata, and building or adopting WebMCP tools | [ash-webmcp](../ash-webmcp/SKILL.md) |
| Background, retried or scheduled work, webhooks, polling, GenServers, PubSub, HTTP clients and shared Elixir libraries | [elixir-stack](../elixir-stack/SKILL.md) |

For uncertain APIs, use the app's actual Mix root, lockfile and installed dependency
usage rules. [Documentation lookup](references/docs-workflow.md) covers version
mismatches; the [inventory helper](scripts/inventory.py) optionally locates projects
without executing them. Before an edit, open the files the change touches, their callers
and the nearest existing example of the same pattern in the site, even when the request
names none of them; a whole-repository scan is not needed.

In Regent, [integration guidance](references/regent-integration.md) resolves shared
libraries, claims and wallet rules. For Privy bridge/session changes, use
[Privy reconciliation](references/privy-reconciliation.md). Consult the
[shared contract](references/shared-contract.md) only when a boundary is unclear.
