# Execution contract — WP11f (ndq.3.6): reference gateway E2E

Binding: decision 0023; spec wp9-wp11 §4.4, §9.9.
Blocked by: WP11e AND the wp11-gateway-profile founder decision.

## Purpose
Certify one named mobile/gateway journey, or honestly scope the claim
to contract replay — never an unnamed "phone journey works".

## Precondition — the gateway profile
No work starts until the founder decision (ticket
wp11-gateway-profile) records: gateway name · gateway version/commit ·
Host Hermes version · approval mechanism · message-size limits ·
tool-call capabilities · session-reconnect behavior · supported phone
client. Spec §4.4: the selected gateway is a release-test target, not
a protocol field; other gateways are not called certified until
tested.

## Live vs replay — declare which
- LIVE full gateway journey (preferred for any public "phone journey"
  claim), or
- CONTRACT REPLAY against canonical run fixtures, in which case
  release copy says "Gateway rendering and approvals are
  contract-tested against canonical runs" and never claims a certified
  live path.

## Journey requirements (live mode)
1. User initiates from the phone gateway. 2. Plugin detects/validates
CLI. 3. Long work returns a run ID immediately. 4. Status is
pull-based and bounded. 5. No ANSI. 6. No large tables. 7. No raw
logs. 8. The approval prompt cannot be approved by the model itself.
9. Duplicate/replayed approval messages do not start duplicate runs.
10. Session loss does not kill the worker. 11. A later session
recovers status by run ID. 12. First result compact and honest.
13. Guided proposal explicitly requested. 14. Provider disclosure
before the host-model request. 15. Diff bounded but sufficient to
approve. 16. Full local diff path provided. 17. Second approval
explicit. 18. Second result + proof path returned.

Paid note: a live journey re-runs paid comparisons — same budget rule
as WP11e (estimate first; STOP if the remainder does not cover it).

## Outputs
release/acceptance/gateway-profile.json · gateway-e2e.json ·
gateway-e2e.md · bounded screenshots or message transcript · run/proof
IDs when live.

## Stop conditions
No pinned gateway profile · model-approvable approval prompt observed
· duplicate-run on replayed approval · any ANSI/unbounded output on
the gateway channel · budget shortfall.
