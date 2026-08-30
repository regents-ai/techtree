# 0018 — Stronger reference host for the canonical rehearsal; selection protocol; pre-rehearsal blockers

Status: binding (author ruling relayed by the founder, 2026-08-14).

## 1. The two roles are separated

qwen/qwen3.7-flash stays the pinned evaluated subject — its calibration
evidence stands untouched. The canonical guided-revision rehearsal uses
a STRONGER reference host model, which is a candidate producer, not a
Campaign component: recorded in the guided-rehearsal operational
record, Skill v2 provenance, the founder packet, the release
compatibility matrix, and demo documentation — never in the
TasksetLock, subject manifest, comparison invariants, or reward
contract. Public semantics: the optional guided revision uses the
model configured for Host Hermes; proposal quality varies by host
model; Techtree evaluates the proposal and does not guarantee a useful
revision. The acceptance run may name the exact tested host model; no
claim that all Hermes models are certified.

## 2. Selection protocol (no benchmark cherry-picking)

(A) The chief proposes exactly ONE reference host profile before any
call, recording: model ID, provider/profile, Hermes configuration,
structured-output mechanism, retry configuration, one-call cost
estimate, approved maximum, and a CAPABILITY-BASED rationale (reliable
structured output, instruction following, long multiline fields,
sufficient reasoning) — never "we liked its Hello World answer".
(B) One synthetic contract probe, unrelated to Hello World (no
BranchCode inputs, no real failure pattern): identify one obvious
general defect from synthetic pass/fail examples, return one complete
multiline SKILL.md inside the exact committed schema, copy no cases,
one generation request, no retry or repair.
(C) Freeze the host profile (model ID, request-construction code,
improver digest e6bc16c4…, schema, retry settings, plugin commit).
(D) Exactly one fresh canonical Hello World rehearsal. Never run the
real context across multiple models to select a favorable proposal.

## 3. The improver revision stays unspent

The qwen evidence shows host-capability and structured-output
failures, not a prompt-method failure — the model ignored a method the
Skill stated. Attempts 1–4 are disclosed diagnostics with these
classifications: (1) diagnostic_host_failure,
(2) diagnostic_structured_output_failure,
(3) diagnostic_structured_output_failure,
(4) diagnostic_wrong_hypothesis_and_invalid_skill. The `---` output is
an invalid-proposal record, never a SkillArtifact in candidate
lineage. Revise the founder Skill only when a capable host passes the
synthetic probe, receives the exact text and context, and still fails
to apply the stated comparison method — after inspecting the full
preserved request.

## 4. Escalation if the stronger host fails

Case A (diagnoses correctly, cannot emit the file): interface problem
— amend the output transport (prefer a deterministic
revised_skill_lines list joined by the plugin) with the full digest/
guard/test/certification cascade; no more prompt tuning.
Case B (valid file, wrong diagnosis): inspect the preserved request;
a single founder revision may then be justified, or fix the
deterministic context builder (grouping, unambiguous pairs, objective
stated once) without ever adding the answer or a giveaway feature.
Case C (fails both): stop; either change the interface or release
v0.1 with the first controlled comparison only, guided revision
marked experimental.

## 5. Pre-rehearsal release blockers (plugin bytes freeze after)

- Recursive error-detail scrubbing everywhere (messages, details,
  nested dicts/arrays, package-tool stdout/stderr, credential URLs,
  auth headers, quoted secrets, key material); raw diagnostics only in
  a private local log (0700/0600); the host sees code + bounded
  scrubbed explanation + local path + repair action; adversarial tests
  per the author's list.
- EXPLICIT USER CONFIRMATION before the one host completion, showing:
  this step sends the verified starter Skill and a sanitized result
  summary to the model provider configured for Host Hermes; it does
  not send raw Episodes, Traces, hidden answers, proof bundles,
  private keys, or credentials; it makes one model-generation request.
- Copied-case guard: exact normalized membership comparison for the
  revised Skill — a single quoted member input fails the revised-skill
  field (prose fields may keep a count threshold); no minimum-length
  skip.
- All model-authored fields scanned and bounded (secrets, paths,
  ANSI/control, unbounded text, execution commands, hidden material).
- Filesystem modes verified by test: home/state/proposal roots 0700;
  staged SKILL.md, key, logs 0600; snapshots never world-readable.
- Website: mutation methods return 405 (not just 404), bodies unparsed
  on read-only routes, oversized-body behavior tested.
- Plugin removal and CLI uninstall/retention docs + tests (in flight).
- Guided-revision approval copy: "Your Hermes model will propose one
  revision. Techtree will test it. A proposal may be unusable or may
  fail to improve the score." Never "your agent will fix the Skill" /
  "learns from its mistakes" / "will close the gap".

## 6. Gate-1 packet amendments

New sections: host-model certification profile (ID, provider,
rationale, synthetic-probe request/response digests and outcome, retry
and structured-output settings); guided-rehearsal accounting (request
count 1, generation count 1, repair 0, retry 0, candidate 1);
diagnostic attempts with classifications, costs, and the statement
that none was selected as the canonical proposal; candidate provenance
(nine values + Skill v2 digest); security attestations (scrubbing,
guards, modes, disclosure shown and accepted, website methods, removal
and uninstall tests, no upload path observed).

## 7. Sequencing

Security fixes → freeze plugin bytes used by the rehearsal → chief
proposes host → synthetic probe → freeze host profile → one canonical
rehearsal → scan/diff/approval → one v1-vs-v2 comparison → offline
proof verification → Gate-1 packet → STOP for founder approval → only
then ReleaseCore freeze and release coordinates.
