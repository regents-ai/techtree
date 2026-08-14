# Execution contract — WP11h (ndq.3.8): docs, runbooks, founder launch gate

Binding: decisions 0013 s5, 0022 item 4, 0023; spec wp9-wp11
§9.14–9.18, §15. Blocked by: WP11f, WP11g, WP11-budget, WP11-claims.

## Purpose
Assemble the Gate-2 release approval packet and stop for the founder.

## Gate-2 packet contents (exact values, no placeholders)
approval packet digest · release ID · ReleaseCore bytes+digest ·
BootstrapRelease bytes+digest (the inactive false-valued candidate) ·
CLI source commit · wheel filename+SHA-256 · plugin repository + full
commit · engine digest · catalog digest · Climb digest · Campaign
digest · TasksetLock digest · TasksetValidationReceipt digest ·
DataPolicy digest · starter Skill file AND tree digests ·
skill-improver digest · runtime image index/platform digests ·
model/provider profile · accepted model-revision warning · budget
contract · exact install argv · exact doctor argv · website origin ·
starter asset URL · placeholder_release = false.

Reject any coordinate that is: latest · main · TBD · empty · a short
commit · an unpinned package range · a mutable image tag without
digest · a missing wheel hash · a missing Skill digest ·
placeholder_release omitted. Also reject if rich_output_skill_digest
is present, rich-terminal-output is registered/packaged, or the public
Climb reference is not hello-world-climb@1.

## Post-rehearsal change classification (0022 item 4)
List EVERY commit after certified 1ad6ecf, classified: scientific ·
non_scientific_copy · release_packaging · documentation · test_only.
For every non-scientific class, prove the certified scientific
fingerprint (release/certified-scientific-fingerprint.json) is
unchanged. The wdc doctor fix appears here as non-scientific
onboarding behavior with its battery evidence.

## Documentation truths (every public surface)
no Techtree account required · provider account/credentials may be
required · model calls go to the selected provider · Techtree uploads
no evaluation artifacts · participant-attested local evidence · not
independently reproduced · synthetic toy mechanism demonstration ·
same-benchmark guided iteration, not held-out generalization · guided
revision is single-SKILL.md in v0.1 (0023 §4) · no measured-uplift
claim for the guided revision (Gate-1 packet §7c).

## Attach evidence
all three repo quality gates · generated-file drift checks · fresh
wheel installation · plugin doctor · clean terminal journey ·
reference gateway journey (or its declared replay scope) · first and
second proof verification · no-upload network assertion · plugin
disable/remove test · CLI uninstall/data-retention test ·
privacy/security review · budget-contract audit ·
claim-to-evidence matrix.

## Post-approval execution plan (recorded in the packet)
1. Publish exact wheel. 2. Verify public wheel hash. 3. Push/tag exact
plugin commit. 4. Activate the exact approved BootstrapRelease
(pointer switch — no rebuild). 5. Verify served bootstrap digest.
6. Public-coordinate install smoke (WP11-postpublish). 7. No paid
scientific rerun unless artifact bytes differ from certified bytes.
8. Launch report with URLs, digests, rollback commands.

## Stop point
STOP at the exact phrase (FOUNDER_APPROVAL_PHRASES.md, "Final Release
Approval"): `APPROVE CLIMB V0.1 RELEASE` + approval_packet_digest +
release_id + release_core_digest + bootstrap_release_digest. Any
changed byte after approval invalidates it and requires a new packet
digest.
