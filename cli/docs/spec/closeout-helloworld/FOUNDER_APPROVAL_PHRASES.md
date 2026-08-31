# Founder Approval Phrases

## Skill Approval

```text
APPROVE CLIMB V0.1 FOUNDER SKILLS
packet_digest: sha256:<complete-digest>
starter_skill_digest: sha256:<complete-digest>
skill_improver_digest: sha256:<complete-digest>
```

## Final Release Approval

```text
APPROVE CLIMB V0.1 RELEASE
approval_packet_digest: sha256:<complete-digest>
release_id: climb-v0.1.0
release_core_digest: sha256:<complete-digest>
bootstrap_release_digest: sha256:<complete-digest>

Authorized:
- publish the exact CLI wheel in this packet
- publish/tag the exact plugin commit in this packet
- set placeholder_release to false
- deploy the read-only Hello World bootstrap/catalog release at techtree.sh

Not authorized:
- upload user receipts, Episodes, Traces, proof bundles, or Skill proposals
- enable a leaderboard or submission endpoint
- add Relay, remote execution, or training export
```
