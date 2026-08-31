# Orphan-bound fix — technical specification (author-countersigned, 0029)

The binding ruling is docs/decisions/0029. This file carries the
implementation-level specification, including the author's
illustrative supervisor code. Where this file and 0029 disagree, 0029
wins.

## 1. Config schema (src/techtree/verifiers/config.py)

Add:

    class TimeoutToml(TomlModel):
        """Per-rollout Verifiers lifecycle limits."""
        setup: float | None = Field(default=None, gt=0.0)
        rollout: float | None = Field(default=None, gt=0.0)
        finalize: float | None = Field(default=None, gt=0.0)
        scoring: float | None = Field(default=None, gt=0.0)

SubjectAgentToml gains: max_turns, max_input_tokens,
max_output_tokens, max_total_tokens (all `int | None`, ge=1) and
`timeout: TimeoutToml = Field(default_factory=TimeoutToml)`. Export
TimeoutToml; serialization + golden tests.

## 2. Compiler (src/techtree/verifiers/compiler.py)

Compile every declared release limit:

    maximum_input = campaign.budgets.maximum_input_tokens
    maximum_output = campaign.budgets.maximum_output_tokens
    maximum_turns = campaign.budgets.maximum_model_calls
    maximum_total = (
        maximum_input + maximum_output
        if maximum_input is not None and maximum_output is not None
        else None
    )
    ...
    max_turns=maximum_turns,
    max_input_tokens=maximum_input,
    max_output_tokens=maximum_output,
    max_total_tokens=maximum_total,
    timeout=TimeoutToml(rollout=float(campaign.execution.timeout_seconds)),

Binding v0.1 interpretation (comment it): one Verifiers model turn is
the supported Hermes model-call budget unit — VALID ONLY IF the
conformance check (below) passes.

Scope clarification: timeout_seconds = maximum duration of ONE
subject rollout, not of the whole variant. The variant bound is the
supervisor's 1800-second deadline.

## 3. Executable-budget validator

    def require_executable_budget(campaign: CampaignSpec) -> None:
        missing: list[str] = []
        if campaign.execution.timeout_seconds <= 0:
            missing.append("execution.timeout_seconds")
        if campaign.budgets.maximum_model_calls is None:
            missing.append("budgets.maximum_model_calls")
        if campaign.budgets.maximum_input_tokens is None:
            missing.append("budgets.maximum_input_tokens")
        if campaign.budgets.maximum_output_tokens is None:
            missing.append("budgets.maximum_output_tokens")
        if missing:
            raise PrerequisiteError(
                "this public Campaign has unenforced or missing "
                "execution limits",
                code="campaign_budget_not_enforced",
                details={"missing": missing},
            )

Wired into the run-start preflight for executable public Campaigns.
maximum_usd becomes a real precondition:

    calculated_bound = calculate_release_cost_bound(campaign, price_profile)
    if calculated_bound > campaign.budgets.maximum_usd:
        raise PrerequisiteError(..., code="campaign_cost_bound_exceeded")

Cost-bound math (conservative, one-turn soft overshoot):
episode input exposure ≤ I + C (context ceiling); output ≤ O + S
(per-call cap); comparison bound ≤ N × V × ((I+C)·Pi + (O+S)·Po).
Highest uncached rates; price profile is a small release-time record
(prices, source, timestamp).

## 4. Supervisor (new: src/techtree/verifiers/supervisor.py)

One small process per evaluation variant, own session, launched by
VerifiersChild; monitors: parent-liveness pipe (worker owns write
end; EOF = worker died, incl. SIGKILL), hard monotonic deadline,
SIGTERM/SIGINT forwarding, eval exit. Exit codes: 124 deadline, 125
supervisor failure, 130 cancelled. SIGTERM to the eval group first,
SIGKILL after grace. Grace invariant: supervisor internal grace 20s <
outer VerifiersChild grace 30s (assert in a test). Private structured
supervision record (dir 0700, file 0600), schema
techtree.eval-supervision.v1: schema_version, variant, reason
(completed | cancelled | deadline_exceeded | parent_lost |
launch_failed), started/finished, deadline/grace, pids, exit codes.
NO argv, NO credentials, NO prompts/responses in the record. The
author's illustrative implementation (selectors loop, killpg,
atomic_write_json in finally) is the reference shape — adapt to repo
idioms, keep it that small.

## 5. VerifiersChild changes

Constructor gains hard_deadline_seconds, supervision_record_path,
supervisor_grace_seconds=20.0. start() creates the pipe, launches
`python -m techtree.verifiers.supervisor --parent-fd R --record P
--deadline-seconds D --grace-seconds G -- <eval argv>` with
start_new_session=True, pass_fds=(read_fd,), closes read end in the
worker, keeps write end as the liveness handle; _close_parent_liveness
on start-failure / _record_exit / context cleanup.
argv_digest stays the UNDERLYING eval argv digest. Eval keeps its own
process group under the supervisor.

## 6. Docker cleanup policy

The ONLY cleanup path: SIGTERM to the eval → pinned Verifiers
finally/atexit cleanup → containers removed. NO docker rm -f sweeps,
NO image-filtered kills, ever. If the kill injection shows a
container surviving the graceful stop: STOP the release (the fix is a
run-specific container-identity mechanism, not a sweep).

## 7. Tests

Unit: normal exit preserves native code · deadline kills the whole
group · parent EOF kills immediately · SIGTERM forwards · inner grace
< outer grace invariant · record is 0600 · record carries no
argv/credential · eval argv digest unchanged · supervisor argv
carries no credential value.
Parent-death test: helper worker process starts a supervised fake
eval + grandchild, test SIGKILLs the HELPER (not terminate()),
asserts supervisor sees EOF, eval + grandchild exit, record says
parent_lost.
Compiler: baseline and candidate resolved configs carry identical
max_turns/max_input/max_output/max_total/timeout.rollout;
mutation-test each assignment (delete → a test fails).
Conformance: intercepted subject generations == Trace.num_turns on
recorded canonical fixtures (live probe in the recert phase). If it
fails: add maximum_turns, leave maximum_model_calls unsupported (no
silent mapping).

## 8. Limit selection (calibration, then predeclare)

From every successful canonical episode in the durable evidence:
turns, input/output/total tokens, elapsed seconds; split
baseline/starter/reference/v1/v2; median/p95/p99/max + task hash at
max. Formulas (0029): turns = ceil(1.25 × max observed); input = 1.5
× max observed rounded up; output = 8000 if comfortably above all
observed; rollout timeout 600; variant deadline 1800. Same values
both variants; new Campaign digest; included in the budget audit and
release/orphan-bound-analysis.json (prices used, source, timestamp,
maximums, overshoot, variants, deadline, token exposure, cost bound,
observed kill-injection residuals).

## 9. Kill injection (real, isolated, evidence-captured)

Snapshot docker IDs → start one real comparison → wait for both
subject containers → record exact new IDs + worker/supervisor/eval
PIDs → SIGKILL the WORKER only → supervision records say parent_lost
→ eval trees exit → the exact recorded container IDs disappear →
elapsed cleanup time recorded → no UpliftReport → residual provider
cost recorded. Container identification by before/after ID diff with
timestamps (or isolated docker context) — never by image.

## 10. Recertification + stops

Per 0029: full cascade regeneration; paid re-runs (2 stability, 1
reference, 1 v1-vs-frozen-v2; no host proposal); founder journey
after. STOP if: worker death does not trigger prompt shutdown ·
containers survive · any declared cap inert · any canonical run
REACHES a new limit (never auto-raise) · finite exposure not
derivable from enforced limits.
