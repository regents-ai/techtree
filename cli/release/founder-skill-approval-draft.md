# Founder Skill Approval Packet — DRAFT

Status: DRAFT. All sections FINAL except §7c (canonical-rehearsal
final status) and §8's candidate-provenance paragraph, both BLOCKED
pending the author's ruling on the fourth failure case (re-attempt at
a corrected harness ceiling vs the 0018 s4 Case C fallback). The
final packet and its canonical digest are produced after that ruling.

Frozen lineage: techtree-plugin f8e9226073a3f17dcfe917581be199c110901d60,
techtree-python 1a51487, ReleaseCore
sha256:80807821d3d5b8bcf0a5223c96684b04546b250ff677b3e3bb65f768bde18687
(byte-identical across repos). Spend at draft time: USD 1.6987 of the
3.00 programme cap (decision 0016 s4) within the founder's 5.00 pool.

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
- Release coordinates: campaign 5aef3fb7…, climb 61a7dd46…, policy
  6c532a43…, validation receipt 080895d5…, evidence 9c4959d3…, engine
  874cbae0…, catalog 468e8ab1…. placeholder_release true; remaining
  placeholders: cli_source_commit, cli_version,
  maximum_tested_host_hermes_version, release_id,
  starter_skill_object_url (the starter materialization path is
  certified as stops-with-stated-reason on this freeze).

## §2 Static calibration

36 tasks: 24 agree under both rules, 12 disagree; the agreement set is
exactly the all-distinct set; zero wrong/correct collisions on failed
tasks (7·e mod 97 ≠ 0 for occurring excesses 1–5). Membership
sha256:56f697fb…, unchanged by the cap change.

## §3 Artifact immutability (0015 s7 A)

No run-owned or proof-owned file of any completed paid run was
modified after that run finished (method: last journal event vs every
file mtime, per run; zero later files in cal1, ref, calB, calB2,
calB3, post1, post2, postref; calA's one later file is the product's
own additive improvement/context.json export). Only committed
fixtures were regenerated: the 0012 membership re-issue, the
executor_kind correction, the calA re-record. WP6c probe directories
were a reclaimed pytest temp home.

## §4 Run classification (0015 s7 B)

CANONICAL (post-change, complete, final artifacts; all
controlled-with-warnings, score valid, evidence complete, accepted,
P1, executor_kind verifiers, signed ComparisonExecutionRecord, proof
verifies offline, zero cap-killed episodes; derived campaign
b9e3f00c… tracing to 5aef3fb7…):

| Run | ID | Score | Report | Bundle | Cost |
|---|---|---|---|---|---|
| starter #1 | run_d94094506aec482aa7ed35bad011486f | 0/36 → 23/36 | 47253518… | 19493177… | 0.1780 |
| starter #2 | run_a6c608b910324d6ca84062dc0c4960c2 | 0/36 → 23/36 | 784614a1… | faa8260e… | 0.1709 |
| engine reference | run_6ff833ca941745bcae620df4c6c0dc27 | 0/36 → 36/36 | c1a88d20… | d32c7dca… | 0.1827 |

PRE-CHANGE DIAGNOSTIC (disclosed in full, none canonical): discovery
probe run_0b0b… (10/11, Skill opened 11/11, 0.0083); cal1
run_bfbcf09c… (0→24, 0.1776); pre-change engine ref run_5c24cb72…
(0→36, 0.1782); calA run_6ce5e56a… (0→24, 0.1907); calB run_a8da75d4…
FAILED output-cap (0.1595); calB2 run_af675e08… FAILED closed
stream + upstream 429 (0.1540); calB3 run_8f46f6c9… FAILED output-cap
×2 (0.1902).

Candidate legs, all nine measured: 24, 24, 23, 23(+1 lost), 23
pre-change; 23, 23 post-change; reference 36/36 twice. Every
measurable leg inside 20–27. Release language: "calibrated to the
20–27/36 band" — never an exact score.

## §5 Retry accounting (0015 s7 C)

Three calibration reruns, each score-blind and authorized before the
outcome, each because the prior produced no comparison; post-change
certification restarted per 0016. Host-proposal generation requests:
6 attempts, 1 outbound request each, 0 transport retries, 0 repairs,
0 second completions. No proposal retried; none selected from a set.

## §6 Incomplete-run cost (0015 s7 D)

USD 0.5037, all pre-change — a third of pre-change spend bought no
comparison; that measurement produced decision 0016. Post-change:
zero incomplete comparisons.

## §7 Host certification (0018 s6)

Profile (FINAL, frozen per 0018 s2C): z-ai/glm-5.2 · prime
OpenAI-compatible · temperature 0 · max_completion_tokens 16000 ·
response_format json_schema strict:true · zero retries at every
layer · approved max 0.30/call · plugin f8e9226 · improver e6bc16c4.
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

§7b Canonical rehearsal accounting (FINAL). Source post1 · through
the confirmation gate (step 1: 0 host calls, 0 CLI reads; approval
artifact written before step 2) · response_id a2ae789bbd541f2f-SJC ·
request sha256:482e4202… · response sha256:2d092802… · finish
length · 5124 in / 16000 out (13164 reasoning) · USD 0.0799
provider-reported / 0.0931 pinned. Invocations 1, outbound 1, retries
0, repairs 0, candidates 0.

§7c Rehearsal final status — BLOCKED pending the author's ruling.
Outcome: null content, budget exhausted, no candidate. The preserved
51,635-character reasoning shows the model found the
distinct-character rule and rejected it on a genuine data artifact:
aspen (branch-code-001), the single all-distinct task among post1's
13 failures — the run's known execution slip. It then searched
alternative moduli and exhausted the budget. Classified Case D:
correct hypothesis abandoned on data noise, not covered by 0018 s4.
The improver-revision lever remains unspent; nothing about the
founder Skill's prose caused any attempt's failure.

§7d Diagnostic attempts (FINAL; none selected as canonical): 1
diagnostic_host_failure (bytes lost — harness defect, disclosed;
0.0007) · 2 diagnostic_structured_output_failure (newline-free file;
guard false-positive since fixed; bytes preserved; 0.0009) · 3
diagnostic_structured_output_failure (null content; bytes lost —
harness defect, disclosed; ~0.0010 est, bounded 0.0023) · 4
diagnostic_wrong_hypothesis_and_invalid_skill (the three-character
"---"; an invalid-proposal record, never a SkillArtifact; 0.0011).

## §8 Proof roots (0015 s7 E)

Campaign 5aef3fb7… (derived b9e3f00c…) · membership 56f697fb… ·
engine 874cbae0… · catalog 468e8ab1… · ReleaseCore 80807821… ·
starter tree 596d1368… / file 2aff2707… · improver e6bc16c4….
Report and bundle digests per run in §4; executor public key in each
bundle; verification result verified=True for all three canonical
runs, re-confirmed at draft time. CANDIDATE V2 DIGEST: none exists —
no v2 was staged, scanned, diffed, approved, or evaluated; the nine
provenance values cannot be populated; resolves with §7c.

## §9 Security attestations (as of the frozen commits)

Attested by the certification thread's own observation: the
confirmation gate sends nothing before consent (verified twice); the
disclosure carries all four required sentences including the may-fail
wording; one generation request per attempt, transport retries
provably zero; copied-case guard passes with all task inputs
supplied; the structure guard refuses a newline-free file truthfully;
no upload path observed (push=false in every resolved config); the
committed evidence fixture passes all nine sanitization checks.
Attested by other threads' committed, chief-verified work: recursive
error-detail scrubbing with adversarial tests; filesystem-mode tests;
website 405 method surface; plugin-removal and CLI-uninstall docs and
tests; product-path zero-transport-retry tests (ndq.3.23).

## §10 Spend ledger

Pre-change diagnostic 1.0601 · post-change 0.6386 (post1 .1780,
post2 .1709, postref .1827, rehearsal3 ~.0010 est bounded .0023,
rehearsal4 .0011, probe .0118, canonical rehearsal .0931) · TOTAL
1.6987 of 3.00 (1.3013 remains). Provider-reported where available;
rehearsal 3 is the only estimated entry, disclosed rather than
smoothed.
