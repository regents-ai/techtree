# Founder Skill Approval Packet — FINAL

Status: FINAL, awaiting the founder's Gate-1 approval phrase
(docs/spec/closeout-helloworld/FOUNDER_APPROVAL_PHRASES.md, "Skill
Approval"). Every certification activity is complete; no blocked
statements remain. The canonical packet digest is the sha256 of this
file's bytes as committed.

Frozen lineage (re-freeze v3, decisions 0017/0019): techtree-plugin
1ce5d4e12910d569a5d968eaac1742a0ed0cb40f, techtree-python 1ad6ecf,
ReleaseCore
sha256:80807821d3d5b8bcf0a5223c96684b04546b250ff677b3e3bb65f768bde18687
(byte-identical across repos, verified by content digest). Total spend:
USD 1.9717 of the 3.00 programme cap (decision 0016 s4) within the
founder's 5.00 pool; 1.0283 remains.

Governing decisions: 0009–0021. New since the draft: 0019 (comparison
symmetry, native approvals, four-statement UX), 0020 (Case-D ruling:
one rehearsal reattempt at a predeclared 32,768 ceiling), 0021
(rehearsal v1-vs-v2 execution after the launcher credential failure).

## §0 Deviation-with-cause (disclosed for the author)

0020 instructed "same source run (post1)". The frozen build cannot
read pre-0019 runs: their stored requests carry the deleted
token-machinery fields, and rewriting stored run bytes is forbidden
(0015), as is adding a compatibility branch (hard rules). Resolution:
ONE fresh baseline-vs-starter comparison under the frozen build was
pre-committed as the rehearsal source before its score existed,
whatever its noise profile. It scored 24/36 with a perfectly clean
signal (all 12 failures repeat a character, all 24 wins all-distinct,
no aspen-style outlier) — not selected, pre-committed. The misleading
"run_request_corrupt" message shown for intact pre-upgrade runs is a
release defect, ticketed (ndq.3.43).

## §1 Skill bytes and digests (0013 s5)

- Starter: release/skills/hello-world-starter-v1/SKILL.md — file
  sha256:2aff27070177d9f37b99d5bef6fa372586887e78180005195cb808971ae55a4c,
  1496 bytes; TREE digest (the pin, per 0008)
  sha256:596d1368ac157975accce7ceff835eed6bfb789eaf68528a0aefa25a68793b0b.
  Diff from the founder draft: exactly one line — the 0010 item 3
  description ("Apply BranchCode v1 and return a BRANCH-XX token.").
- Improver: techtree-plugin/skills/skill-improver/SKILL.md — file
  sha256:e6bc16c4d6740a0c3528c7009c78dc3036084fdd218a4934f602234a6dce7097,
  4355 bytes. Diff from the founder draft: the 0010 item 4 prose edit
  (whole-section Prohibited Strategies swap + one requirement bullet).
- Contract-tested: the mounted starter never mentions being
  incomplete; its frontmatter carries no procedure.
- Release coordinates (verified unchanged in the frozen catalog):
  campaign 5aef3fb7…, climb 61a7dd46…, policy 6c532a43…, validation
  receipt 080895d5…, evidence 9c4959d3…, engine 874cbae0…, catalog
  468e8ab1…. ReleaseCore binds starter_skill_digest 596d1368… and
  skill_improver_digest e6bc16c4…. placeholder_release true;
  remaining placeholders: cli_source_commit, cli_version,
  maximum_tested_host_hermes_version, release_id,
  starter_skill_object_url (the starter materialization path is
  certified as stops-with-stated-reason on this freeze).

## §2 Static calibration

36 tasks: 24 agree under both rules, 12 disagree; the agreement set is
exactly the all-distinct set; zero wrong/correct collisions on failed
tasks (7·e mod 97 ≠ 0 for occurring excesses 1–5). Membership
sha256:56f697fb…, unchanged by the cap change and by re-freeze v3.

## §3 Artifact immutability (0015 s7 A)

No run-owned or proof-owned file of any completed run was modified
after that run finished (method: last journal event vs every file
mtime, per run — re-run over the full final run set). The single
exception is calA's improvement/context.json, written additively by
the product's own `uplift context` export. The failed launcher run
(§4) is preserved exactly as written — failed state, honest error, no
rewriting, no relabeling. Only committed fixtures were regenerated:
the 0012 membership re-issue, the executor_kind correction, the calA
re-record. WP6c probe directories were a reclaimed pytest temp home.

## §4 Run classification (0015 s7 B)

CANONICAL (post-change, complete, final artifacts; all
controlled-with-warnings, score valid, evidence complete, accepted,
P1, executor_kind verifiers, signed ComparisonExecutionRecord, proof
verifies offline, zero cap-killed episodes; insertion runs on derived
campaign b9e3f00c…, the replacement run on derived campaign
f2f04ae5…, both tracing to 5aef3fb7…):

| Run | ID | Score | Report | Bundle | Cost |
|---|---|---|---|---|---|
| starter #1 | run_d94094506aec482aa7ed35bad011486f | 0/36 → 23/36 | 47253518… | 19493177… | 0.1780 |
| starter #2 | run_a6c608b910324d6ca84062dc0c4960c2 | 0/36 → 23/36 | 784614a1… | faa8260e… | 0.1709 |
| engine reference | run_6ff833ca941745bcae620df4c6c0dc27 | 0/36 → 36/36 | c1a88d20… | d32c7dca… | 0.1827 |
| rehearsal source | run_9f2a5025bba849e5b8e8e0b15db855c6 | 0/36 → 24/36 | 5668a0f1… | c7b76024… | 0.1702 |
| v1 vs v2 | run_e29f178181bb4a65b0c518d34f72cd50 | 23/36 → 24/36 | 421f1a0b… | 4db83924… | 0.0551 |

The v1-vs-v2 row is the guided-rehearsal measurement: wins/losses/ties
1/0/35. The +1 is noise, not uplift — v1 has scored 23 and 24 across
six measured legs (see below).

DIAGNOSTIC (disclosed in full, none canonical): discovery probe
run_0b0b… (10/11, Skill opened 11/11, 0.0083); cal1 run_bfbcf09c…
(0→24, 0.1776); pre-change engine ref run_5c24cb72… (0→36, 0.1782);
calA run_6ce5e56a… (0→24, 0.1907); calB run_a8da75d4… FAILED
output-cap (0.1595); calB2 run_af675e08… FAILED closed stream +
upstream 429 (0.1540); calB3 run_8f46f6c9… FAILED output-cap ×2
(0.1902); rehearsal attempts 1–4 (§7d; 0.0007/0.0009/~0.0010/0.0011);
16k rehearsal attempt diagnostic_host_completion_truncated (§7b,
0.0931); run_28261de5… infrastructure_failure_no_measurement (§7e,
USD 0.0000 — no episode ran, nothing billed).

Candidate v1 legs, all measured: 24, 24, 23, 23(+1 lost), 23
pre-change; 23, 23, 24 post-change (source run), plus the v1 baseline
arm of the v1-vs-v2 run at 23. Reference 36/36 twice. Every
measurable leg inside 20–27. Release language: "calibrated to the
20–27/36 band" — never an exact score.

## §5 Retry accounting (0015 s7 C)

Four calibration/certification re-executions, each score-blind and
authorized before the outcome, each because the prior produced no
comparison (three pre-change reruns; one post-failure re-preparation
under 0021 after the launcher credential failure billed nothing).
Host-proposal generation requests: 7 attempts, 1 outbound request
each, 0 transport retries, 0 repairs, 0 second completions. Exactly
one completion produced the canonical candidate; no proposal was
retried or selected from a set.

## §6 Incomplete-run cost (0015 s7 D)

USD 0.5037, all pre-change — a third of pre-change spend bought no
comparison; that measurement produced decision 0016. Post-change:
zero incomplete comparisons; the one launcher failure billed 0.0000.

## §7 Host certification (0018 s6, amended by 0020)

Profile (FINAL): z-ai/glm-5.2 · prime OpenAI-compatible ·
temperature 0 · response_format json_schema strict:true · zero
retries at every layer · approved max USD 0.30/call · plugin 1ce5d4e
· improver e6bc16c4. max_completion_tokens: 16,000 for the first
canonical attempt (0018 s2C); 32,768 for the single authorized
reattempt, predeclared and frozen before the call (0020).
Availability and price verified against the free catalog listing
before configuring. Strict json_schema is supported; the
STOP-on-refusal ruling never fired. Founder-directed selection
(glm-5.2 replacing the chief-proposed gpt-5.2) made prospectively,
before any Hello World call.

§7a Synthetic BadgeCode probe — PASS 5/5 (FINAL). response_id
a2ae6f1b78d0cfe1-SJC · request sha256:abb6dfaa… · response
sha256:d4425fea… · finish stop · 3781 in / 1024 out (347 reasoning) ·
USD 0.0103 provider-reported. Found the planted hyphen defect as one
general rule; domain programmatically verified disjoint from the
membership. Fragment ruling of record: the revision quotes "Jean-Luc"
illustrating the rule; no full member input, no answer token; a
fragment illustrating a general rule is explanation, not
memorization.

§7b First canonical attempt — diagnostic_host_completion_truncated
(reclassified by 0020). Source post1 · response_id
a2ae789bbd541f2f-SJC · request sha256:482e4202… · response
sha256:2d092802… · finish length · 5124 in / 16000 out (13164
reasoning) · USD 0.0799 provider-reported / 0.0931 pinned. The
preserved 51,635-character reasoning (local only, per 0020's privacy
rule) shows the model found the distinct-character rule and rejected
it on aspen (branch-code-001), post1's known execution slip — a
correct hypothesis abandoned on honest data noise, then truncated by
the 16k candidate-production ceiling while still reasoning.

§7c Canonical rehearsal — COMPLETE; candidate produced; flow
certified end-to-end. The single 0020-authorized reattempt at the
predeclared 32,768 ceiling, source = the fresh pre-committed run
(§0): before dispatch 0 host calls / 0 outbound / 0 CLI reads; all
twelve frozen values recorded; request digest
sha256:12e1aa49… computed BEFORE the call matched the request
actually sent, exactly. response_id a2b2c61f2a1fb1b4-SJC · response
sha256:69d0657e… · finish stop · 5,139 in / 7,400 out of 32,768
(25,368 to spare) · USD 0.0417 provider-reported. 0020's diagnosis
confirmed: the ceiling, not the model, ended the first attempt.

The proposal passed every guard and produced valid Skill v2
hello-world-v2 (§8). The model identified the failure pattern
correctly — every failing task repeats a character, every shown
passing task is all-distinct — and inverted the causal direction,
amending the Skill to use "the full length, not the count of unique
letters", which reinforces the planted defect; distinct/different/
once appear nowhere. Per 0020 the proposal was measured, not judged:
scan → snapshot → deterministic diff → reviewed approval → one
v1-vs-v2 comparison → second signed receipt. Result: 23/36 → 24/36,
1/0/35 — within v1's own run-to-run noise; no uplift claim is made.

0013 s4 hard gates — all met: structurally valid · one-turn held ·
no copied material · second comparison executed · second proof
verifies offline · ties reported as ties. The 0013 s4 demo target
(≥32/36, ≥6 uplift) was not met; 0013 already designates that a
calibrated aim, not a guarantee. The guarantee — proposed, scanned,
diffed, approved, evaluated, reported honestly — is satisfied in
full. Consequence for release copy: the guided-revision flow is
certified as a FLOW; no marketing claim may state or imply that
guided revision produced measured uplift in this certification.

§7d Diagnostic attempts (FINAL; none canonical): 1
diagnostic_host_failure (bytes lost — harness defect, disclosed;
0.0007) · 2 diagnostic_structured_output_failure (newline-free file;
guard false-positive since fixed; bytes preserved; 0.0009) · 3
diagnostic_structured_output_failure (null content; bytes lost —
harness defect, disclosed; ~0.0010 est, bounded 0.0023) · 4
diagnostic_wrong_hypothesis_and_invalid_skill (the three-character
"---"; an invalid-proposal record, never a SkillArtifact; 0.0011).

§7e Launcher credential failure (0021). The first v2-comparison
launch went through the real detached launcher for the first time in
this programme and failed instantly with model_credentials_missing:
the scrubbed worker environment deliberately does not inherit a
provider credential exported in the operator's shell. Correct,
intentional isolation; nothing billed; run preserved as failed. The
comparison was re-prepared from the identical v2 bytes and executed
in-process — the same path as every canonical run above. Release
findings ticketed: onboarding docs must state an exported variable is
not enough (techtree-python-3ym); misleading corrupt-message for
pre-upgrade runs (ndq.3.43).

## §8 Proof roots (0015 s7 E)

Campaign 5aef3fb7… (derived insertion b9e3f00c…, derived replacement
f2f04ae5…) · membership 56f697fb… · engine 874cbae0… · catalog
468e8ab1… · ReleaseCore 80807821… · starter tree 596d1368… / file
2aff2707… · improver e6bc16c4….

CANDIDATE V2 PROVENANCE (complete): Skill hello-world-v2, root
sha256:b143866e62bae51a140c5d7374a3a75562489c93d5df7144b6ba65b22b622986
· SKILL.md file sha256:7cc03c89…, 1,907 bytes, 47 lines · parent
skill 596d1368… · derived replacement campaign f2f04ae5… · produced
by the §7c completion (request 12e1aa49…, response 69d0657e…) ·
evaluated once in run_e29f1781… (report 421f1a0b…, bundle 4db83924…).
Skill v2 is certification evidence only — it is NOT a release
artifact and ships nowhere.

Report and bundle digests per run in §4; executor public key in each
bundle; proof verification result verified for all five canonical
runs, independently re-confirmed by the chief from the stored bytes
at packet-finalization time.

## §9 Security attestations (as of the frozen commits)

Attested by the certification thread's own observation: the native
approval boundary sends nothing before consent (the approval surface
rendered from the plugin's tool schema; before dispatch: 0 host
calls, 0 outbound, 0 CLI reads — verified again at the 32k attempt);
the disclosure carries all four required sentences including the
may-fail wording; one generation request per attempt, transport
retries provably zero; copied-case guard passes with all task inputs
supplied; the structure guard refuses a newline-free file truthfully;
no upload path observed (push=false in every resolved config); the
committed evidence fixture passes all nine sanitization checks; the
detached launcher's environment scrubbing refuses to inherit shell
credentials (§7e). Attested by other threads' committed,
chief-verified work: recursive error-detail scrubbing with
adversarial tests; filesystem-mode tests; website 405 method surface;
plugin-removal and CLI-uninstall docs and tests; product-path
zero-transport-retry tests (ndq.3.23).

## §10 Spend ledger

Pre-change diagnostic 1.0601 · post-change 0.9116 (post1 .1780,
post2 .1709, postref .1827, rehearsal3 ~.0010 est bounded .0023,
rehearsal4 .0011, probe .0118, 16k rehearsal .0931, source run
.1702, 32k completion .0417, launcher failure .0000, v1-vs-v2
.0551) · TOTAL USD 1.9717 of 3.00 (1.0283 remains). Provider-reported
where available; rehearsal 3 is the only estimated entry, disclosed
rather than smoothed.

## §11 What approval authorizes

The Gate-1 phrase approves the two founder Skill artifacts (§1
digests) as the frozen founder Skills of Climb v0.1 and accepts this
packet as the certification record. It does NOT authorize publishing,
tagging, deploying, or setting placeholder_release false — those
require the separate Gate-2 "Final Release Approval" phrase.
