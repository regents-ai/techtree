# Specification Index — ticket to binding source

Every open ticket is executable from this repository alone. "Spec §N"
in a ticket resolves through this table. Decision documents
(docs/decisions/) are binding and supersede contradictory spec
passages; decision 0022 (post-rehearsal change discipline) constrains
every remaining v0.1 ticket. Detailed per-ticket execution contracts
live in docs/release/contracts/. File integrity:
CHECKSUMS.json, verified by tests/unit/test_spec_index.py.

Sources (short name → file): wp0-wp5 = climb-v0.1-wp0-wp5.md ·
pr6-pr8 = climb-v0.1-pr6-pr8.md · wp6-wp8 = climb-v0.1-wp6-wp8.md ·
wp9-wp11 = climb-v0.1-wp9-wp11.md.

| Ticket | Binding spec sections | Binding decisions | Known amendments |
|---|---|---|---|
| ndq.3.2 (WP11b wheel) | wp9-wp11 §9.5–9.6, §16 | 0011, 0022, 0023 | wheel from final post-copy-fix commit; certified-scientific-fingerprint check (contract wp11b.md) |
| ndq.3.3 (WP11c plugin) | wp9-wp11 §9.3–9.4, §16 | 0011, 0022, 0023 | repo coordinate regents-ai/techtree-hermes; no BootstrapRelease digest embedded in plugin (cycle rule) |
| ndq.3.4 (WP11d ash release) | wp9-wp11 §9.3–9.4 | 0007 R10, 0011, 0023 | starter URL keyed by SKILL.md FILE digest; inactive false-valued candidate before approval; pointer-based rollback (contract wp11d.md) |
| ndq.3.5 (WP11e terminal E2E) | wp9-wp11 §9.8, §9.10–9.11 | 0022, 0023 | blocked by wdc (doctor credential truth); prime-login credential path; isolated HOME/TECHTREE_HOME/HERMES_HOME/UV paths |
| ndq.3.6 (WP11f onboarding E2E) | wp9-wp11 §9.9 (channel hygiene) | 0023, 0024 | agent-first Hermes community onboarding replaces the phone/gateway journey (iOS out of v0.1; §4.4 REFERENCE_GATEWAY resolves as none) |
| ndq.3.7 (WP11g security review) | wp9-wp11 §9.12–9.13, §15.8 | 0014, 0015, 0023 | three-part no-upload methodology (static audit + instrumented method log + destination capture) |
| ndq.3.8 (WP11h Gate-2 packet) | wp9-wp11 §9.14–9.18, §15 | 0013 s5, 0022 item 4, 0023 | packet adds post-rehearsal change classification and claim-to-evidence matrix |
| wdc (doctor credential) | wp9-wp11 §9.10 (Doctor) | 0022, 0023 | PROMOTED to v0.1; blocks ndq.3.5 (contract wp11-doctor.md) |
| WP11-budget | wp6-wp8 (budget fields), wp9-wp11 §16 | 0016, 0023 | release audit over existing fields; no new subsystem |
| WP11-claims | — (release assurance) | 0023 | claim-to-evidence matrix for the public product claims |
| WP11-postpublish | wp9-wp11 Phase 7 (closeout directive) | 0023 | activates only after Gate-2 approval |
| 999 (v0.2 state collapse) | pr6-pr8 (run lifecycle) | 0019, 0022 item 1, 0023 | includes the five-state public projection design |
| cwa (v0.2 versioned readers) | — | 0022 item 3 | read-only scope |
| ndq.3.42 (multi-file, deferred) | wp9-wp11 (skills) | 0022 item 2, 0023 | release copy states guided revision is single-SKILL.md in v0.1 |

Closeout directive and founder pack: docs/spec/closeout-helloworld/
(self-verifying; see its own manifest). Approval phrases:
docs/spec/closeout-helloworld/FOUNDER_APPROVAL_PHRASES.md.
