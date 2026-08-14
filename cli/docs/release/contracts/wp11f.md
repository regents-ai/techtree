# Execution contract — WP11f (ndq.3.6): agent-first Hermes community onboarding E2E

Binding: decision 0024 (replaces the phone/gateway framing); decision
0023; spec wp9-wp11 §9.9 (channel behavior, bounded output — the
channel-generic requirements survive; the phone-client framing does
not). Blocked by: WP11e (candidate artifacts exist and the terminal
journey passed).

## Purpose
Certify the reference onboarding path: a Hermes community user pastes
ONE prompt to their existing Hermes agent, and everything from reading
the pinned instructions through the Hello World result happens with
explicit approvals at every boundary. No iOS, no named phone client,
no live-phone claim anywhere.

## The path under test
User prompt → Hermes reads the pinned Techtree plugin instructions
(techtree.sh/start and/or the pinned GitHub commit) → shows the exact
install plan → explicit approval → installs/enables the plugin → one
Hermes restart → plugin installs/verifies techtree-python → doctor →
Hello World Climb.

## Acceptance (all twelve, from 0024 §3)
1. A user with Hermes already installed can paste one instruction.
2. Hermes reads the exact pinned GitHub release instructions.
3. It explains prerequisites, commands, cost, provider disclosure,
   and local-data policy.
4. It asks before installing anything.
5. It installs/enables the exact plugin release.
6. It tells the user to restart/reset Hermes once.
7. After restart, the plugin offers the pinned CLI installation.
8. It asks before installing the CLI.
9. It runs release verification and doctor.
10. It starts Hello World only after the paid-run approval.
11. Every CLI/plugin response includes the useful next step.
12. No command uses `main`, `latest`, or an unpinned package
    coordinate.

## Notes
- Pre-Gate-2, the "pinned GitHub release" is the local candidate
  commit served/read locally; the journey must not pretend the public
  repo exists yet. The public-path repeat is WP11-postpublish.
- Paid runs inside the journey follow the same budget rule as WP11e
  (estimate first; STOP on shortfall).
- Channel hygiene from the old contract still applies where output
  flows through a conversation: bounded pull-based status, no ANSI,
  no raw logs, the model can never approve its own action,
  duplicate/replayed approvals never start duplicate runs, session
  loss never kills the worker, a later session recovers by run ID.

## Outputs
release/acceptance/onboarding-e2e.json · onboarding-e2e.md · the
scrubbed conversation transcript · run/proof IDs for any paid legs.

## Stop conditions
Any auto-install without approval · any unpinned coordinate in any
surfaced command · any claim of a certified phone path · budget
shortfall.
