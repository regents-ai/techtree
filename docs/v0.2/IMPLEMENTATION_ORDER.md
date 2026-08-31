# Techtree v0.2 implementation order

The sole architecture authority is the
[`v0.2 implementation contract`](../plan/v0.2.md). The
[`ticket ledger`](TICKETS.md) is its actionable backlog, not a second design.

Implement the work packages in this order:

1. `V2-WP0` — authority, release identity, and upstream contract lock.
2. `V2-WP1` — protocol, durable state, and historical readers.
3. `V2-WP2` — Fabric-Hermes backend parity.
4. `V2-WP3` — Relay evidence on Fabric-Hermes.
5. `V2-WP4` — Prime Hosted Evaluations.
6. `V2-WP5` — reruns, publication, and public evidence.
7. `V2-WP6` — Codex subject and operator path.

WP3 requires WP2. WP5 requires WP3 and WP4. WP6 requires WP2. WP3 and WP4
may proceed in parallel after WP1 when they have separate owners and fixtures.

Before production code begins:

- reconcile every active v0.2 ticket to one work package;
- replace every pending field in `UPSTREAM_CONTRACT_LOCK.json` with tested
  coordinates and record the founder decision authorizing them;
- populate `FABRIC_CAPABILITY_MATRIX.json` from upstream descriptors,
  Techtree conformance evidence, and release admission;
- add only sanitized deterministic fixtures under component-owned test paths;
- commit the lock and decisions before production backend code; and
- freeze the adopted upstream candidates for the release line.

Do not create future module trees before their first executable caller exists.
