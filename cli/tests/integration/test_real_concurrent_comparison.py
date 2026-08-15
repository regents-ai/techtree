"""Both variants of a real Campaign, executed at once. Spec sections 6.15-6.22.

This and its WP6b predecessor are the only tests in the repository that spend
money. This one is the whole of WP6 in one execution: a real draft prepared
from a real Skill directory, a real run started and staged, the real
:class:`~techtree.runs.real.RealVerifiersExecutor` driving two live ``eval``
children side by side in clean Docker runtimes, and the engine's own normalizer
reading back what they wrote.

What it proves that nothing cheaper can:

* the two variants really do overlap, and the gap between their launches is
  small enough to be a fork rather than an episode;
* every committed task is scored on **both** sides, which is the WP6b runaway
  defect's fix observed rather than argued;
* the normalized projection comes back in committed membership order on both
  sides, not in the order the concurrent children happened to finish;
* a Skill that teaches the procedure outscores a baseline that has none, which
  is the entire point of the Climb.

It is marked ``real_model``, excluded from the default selection and from every
``make`` target that runs unattended, and started only by somebody who meant to.
The Campaign it executes is the one this build ships, read from the packaged
catalog: decisions document 0025 put the release coordinates and the budget
contract into the product, so there is no locally derived Campaign left to
execute instead.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

from fixtures.verifiers.support import (
    SUBJECT_INPUT_USD_PER_MTOK,
    SUBJECT_MODEL_ID,
    SUBJECT_OUTPUT_USD_PER_MTOK,
    local_run,
)
from techtree.engines.bundle import default_engine_digest
from techtree.engines.registry import EngineRegistry
from techtree.models.campaign import VariantSchedule
from techtree.models.run import RunPhase
from techtree.paths import default_paths
from techtree.runs.child_registry import ChildRegistry, children_record_path
from techtree.runs.real import RealVerifiersExecutor, real_execution_result_path
from techtree.settings import Settings
from techtree.verifiers.models import (
    RunPaths,
    VariantExecutionResult,
    VariantName,
)
from techtree.verifiers.outputs import TRACES_FILENAME

pytestmark = pytest.mark.real_model

#: Seventy-two agentic rollouts, four at a time, each provisioning a container.
#: Generous, because a timeout that fired would waste the money already spent.
_POLL_SECONDS: Final = 5.0

#: The reward the Campaign is decided on.
_PRIMARY_REWARD: Final = "exact_match"

#: Two launches separated by more than this are not a pair. A fork costs
#: milliseconds; an episode costs a minute.
_MAXIMUM_LAUNCH_SKEW_SECONDS: Final = 5.0


@dataclass(frozen=True)
class Spend:
    """What one variant's own records say it cost."""

    variant: VariantName
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    scored: int
    episodes: int

    @property
    def usd(self) -> float:
        """The full published price of every token this variant used.

        Every prompt token is priced once at the input rate. For this subject
        that is not a pessimistic reading but the only one: the provider
        reports no cached input tokens for it, so there is no second rate the
        bill could be computed under.
        """
        return (
            self.input_tokens / 1_000_000 * SUBJECT_INPUT_USD_PER_MTOK
            + self.output_tokens / 1_000_000 * SUBJECT_OUTPUT_USD_PER_MTOK
        )


@pytest.fixture(scope="module")
def prerequisites() -> None:
    """Refuse to start a paid run on a machine that cannot finish one."""
    if shutil.which("docker") is None:
        pytest.skip("a real subject runs in a container; docker is not on PATH")
    if not os.environ.get("PRIME_API_KEY"):
        pytest.skip("no evaluation credential is exported in this shell")
    registry = EngineRegistry(default_paths(), Settings())
    status = registry.status(default_engine_digest())
    if not status.installed or not status.verified:
        pytest.skip("run `techtree engine install` before the real-model run")


def test_both_variants_of_a_real_campaign_run_at_once(
    tmp_path_factory: pytest.TempPathFactory,
    prerequisites: None,
) -> None:
    """Execute the whole comparison for real and check every WP6 claim on it."""
    home = tmp_path_factory.mktemp("real-concurrent-home")
    run = local_run(home)
    campaign = run.campaign
    task_count = len(campaign.taskset.membership.ordered_task_hashes)
    print(f"\nrun {run.run_id} in {home}")
    print(f"subject {SUBJECT_MODEL_ID}, {task_count} tasks x 2 variants")

    executor = RealVerifiersExecutor(
        paths=run.paths,
        engine_registry=EngineRegistry(run.paths, Settings()),
        child_registry=ChildRegistry(),
        poll_interval_seconds=_POLL_SECONDS,
    )
    result = executor.execute(run.context())

    # -- the schedule was concurrent, and the gap was a fork ---------------
    assert result.schedule is VariantSchedule.PARALLEL
    record = json.loads(children_record_path(run.paths.run_dir(run.run_id)).read_text())
    skew = record["launch_skew_seconds"]
    print(f"launch skew: {skew:.3f}s")
    assert skew is not None
    assert skew < _MAXIMUM_LAUNCH_SKEW_SECONDS
    assert [row["variant"] for row in record["children"]] == ["baseline", "candidate"]

    baseline_outcome = result.baseline.child_outcome
    candidate_outcome = result.candidate.child_outcome
    assert baseline_outcome.started_at < candidate_outcome.finished_at
    assert candidate_outcome.started_at < baseline_outcome.finished_at

    # -- sibling cancellation was not triggered ----------------------------
    for outcome in (baseline_outcome, candidate_outcome):
        assert outcome.exit_code == 0
        assert not outcome.cancelled

    # -- every task scored, on both sides, in membership order -------------
    committed = list(campaign.taskset.membership.ordered_task_hashes)
    paths = RunPaths.for_run(run.paths, run.run_id)
    for variant, side in (
        (VariantName.BASELINE, result.baseline),
        (VariantName.CANDIDATE, result.candidate),
    ):
        assert len(side.episodes) == task_count
        assert [episode.task_hash for episode in side.episodes] == committed
        assert [episode.task_position for episode in side.episodes] == list(
            range(task_count)
        )
        for episode in side.episodes:
            assert episode.ok
            assert len(episode.traces) == 1
            trace = episode.traces[0]
            assert trace.agent_role == "subject"
            assert trace.harness_id == "hermes-agent"
            assert trace.harness_version == "0.19.0"
            assert trace.use_bundled_skill is False
            assert trace.runtime.kind == "docker"
            assert trace.model_id == SUBJECT_MODEL_ID
            # The runaway defect's fix, observed: every task has a reward.
            assert trace.reward(_PRIMARY_REWARD) is not None

        # Raw evidence is retained beside the projection that reads it, and
        # every byte of it is the participant's alone. Spec section 6.19.
        output = paths.variant_output_dir(variant)
        for name in ("config.toml", TRACES_FILENAME, "eval.log"):
            assert (output / name).is_file(), f"{variant.value}/{name} was not retained"
        for written in output.iterdir():
            assert stat.S_IMODE(written.stat().st_mode) == 0o600, written
        raw = (output / TRACES_FILENAME).read_text().splitlines()
        assert len(raw) == task_count
        raw_order = [json.loads(line)["traces"][0]["task"]["hash"] for line in raw]
        print(
            f"{variant.value}: completion order equals membership order: "
            f"{raw_order == committed}"
        )

    # -- only the Skill differed -------------------------------------------
    assert result.baseline.episodes[0].traces[0].skill_root_digests == []
    assert len(result.candidate.episodes[0].traces[0].skill_root_digests) == 1

    # -- what WP6 hands WP7 is on disk -------------------------------------
    handover = real_execution_result_path(run.paths.run_dir(run.run_id))
    assert handover.is_file()
    assert json.loads(handover.read_text())["execution_backend"] == "verifiers"

    # The run stopped where WP6 stops. WP7 takes it from building_receipts.
    assert run.run_store.state(run.run_id).phase is RunPhase.RUNNING_VARIANTS

    # -- the science, and the bill -----------------------------------------
    ceiling = campaign.budgets.maximum_usd
    assert ceiling is not None, "the shipped Campaign declares a spend ceiling"
    baseline_spend = _spend(VariantName.BASELINE, result.baseline)
    candidate_spend = _spend(VariantName.CANDIDATE, result.candidate)
    total = baseline_spend.usd + candidate_spend.usd
    print(
        f"\nREAL CONCURRENT RUN\n"
        f"  baseline  {baseline_spend.scored}/{baseline_spend.episodes} scored "
        f"{_PRIMARY_REWARD}, USD {baseline_spend.usd:.4f}\n"
        f"  candidate {candidate_spend.scored}/{candidate_spend.episodes} scored "
        f"{_PRIMARY_REWARD}, USD {candidate_spend.usd:.4f}\n"
        f"  tokens    baseline {baseline_spend.input_tokens} in / "
        f"{baseline_spend.output_tokens} out; candidate "
        f"{candidate_spend.input_tokens} in / {candidate_spend.output_tokens} out\n"
        f"  total     USD {total:.4f} against the Campaign's declared "
        f"ceiling of USD {ceiling:.2f}"
    )

    assert total <= ceiling
    # A candidate that does not outscore a zero baseline would mean the Skill
    # taught nothing, and the comparison would have measured nothing.
    assert candidate_spend.scored > baseline_spend.scored


def _spend(variant: VariantName, result: VariantExecutionResult) -> Spend:
    """Total one variant's own usage records and count what it got right."""
    input_tokens = cached = output_tokens = scored = 0
    for episode in result.episodes:
        for trace in episode.traces:
            reward = trace.reward(_PRIMARY_REWARD)
            scored += int(reward is not None and reward.score > 0)
            if trace.usage is not None:
                input_tokens += trace.usage.input_tokens
                cached += trace.usage.cached_input_tokens or 0
                output_tokens += trace.usage.output_tokens
    return Spend(
        variant=variant,
        input_tokens=input_tokens,
        cached_tokens=cached,
        output_tokens=output_tokens,
        scored=scored,
        episodes=len(result.episodes),
    )


def _tail(path: Path, lines: int = 40) -> str:
    """Return the last lines of a capture file, for a failure message."""
    if not path.is_file():
        return f"{path.name} was never written"
    return "\n".join(path.read_text(errors="replace").splitlines()[-lines:])
