"""Which executor a run gets, and why. Spec section 16, WP6 row 12.

"The fake executor is no longer the default for a real Campaign" is a rule
about a decision the worker makes before it does anything, and the Campaign is
what decides it: whether a Climb's subject is a real model on a real image or
the placeholder pair this build ships is a fact about the Campaign, not about
who entered it. So the worker reads the run's own staged Campaign, and the same
predicate that ``techtree doctor --for-evaluation`` uses answers it.

The run's request records that answer as ``executor_kind``, decided from the
Campaign when the run is created — which is the moment a person is told what is
about to happen. Recording it is not the same as being believed: the worker
asks the Campaign again and refuses a request that disagrees, so a hand-edited
request cannot talk the real executor into running, or out of it.

Nothing here executes anything. Both runs are staged for real and then only
asked which executor they would be handed, because constructing the answer is
the whole of what is under test and running it would cost a container and a
provider.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from fixtures.runs.support import run_harness
from fixtures.verifiers.support import local_run
from techtree.errors import PrerequisiteError, RunError
from techtree.models.run import RunRequest
from techtree.paths import paths_from_root
from techtree.runs.fake import FakeRunExecutor
from techtree.runs.real import (
    REAL_EXECUTION_UNSUPPORTED,
    RealVerifiersExecutor,
    campaign_is_executable,
    executor_kind_for,
    real_execution_result_path,
    require_live_campaign,
)
from techtree.worker.execute import (
    REPORT_STAGE_UNAVAILABLE,
    execute_run,
    executor_for,
)

pytestmark = pytest.mark.integration

#: A digest-pinned reference that names no development placeholder. Fixed
#: rather than read from the local daemon: nothing here starts a container, so
#: requiring Docker to answer a routing question would be a cost with no
#: evidence attached to it.


def test_a_development_placeholder_campaign_still_gets_the_fake_executor(
    tmp_path: Path,
) -> None:
    """Everything this build ships is a placeholder, and stays development-only."""
    home = tmp_path / "home"
    harness = run_harness(home)
    run_id = harness.start().state.run_id

    executor = executor_for(harness.request(run_id), paths=harness.paths)
    assert isinstance(executor, FakeRunExecutor)
    assert not campaign_is_executable(harness.inputs(run_id).campaign)


def test_a_campaign_with_real_subject_coordinates_gets_the_real_executor(
    tmp_path: Path,
) -> None:
    """A Campaign that names a real model on a real image is evaluated for real."""
    home = tmp_path / "home"
    run = local_run(home)

    executor = executor_for(run.request, paths=paths_from_root(home))
    assert isinstance(executor, RealVerifiersExecutor)
    assert campaign_is_executable(run.campaign)


def test_the_real_executor_refuses_a_placeholder_campaign_outright(
    tmp_path: Path,
) -> None:
    """The converse rule: a placeholder Campaign is never executed by accident."""
    harness = run_harness(tmp_path / "home")
    run_id = harness.start().state.run_id

    with pytest.raises(PrerequisiteError) as raised:
        require_live_campaign(harness.inputs(run_id).campaign)
    assert raised.value.code == REAL_EXECUTION_UNSUPPORTED


def test_evidence_without_a_report_fails_the_run_and_names_the_evidence(
    tmp_path: Path,
) -> None:
    """An executor that produces neither shape fails, rather than inventing one.

    The worker finishes a run from one of exactly two things: a report, or the
    complete evaluation evidence the report stage turns into one. Anything else
    is a build defect, and it is recorded as a failure that points at the file
    the report stage would have read rather than as a report nobody measured.
    """
    home = tmp_path / "home"
    harness = run_harness(home)
    run_id = harness.start().state.run_id

    class EvidenceOnlyExecutor:
        """An executor that produces results rather than a report."""

        def execute(self, context: object) -> object:
            """Return something that is not a report."""
            return {"execution_backend": "verifiers"}

    exit_code = execute_run(
        run_id,
        paths=harness.paths,
        executor_factory=lambda _request: EvidenceOnlyExecutor(),  # type: ignore[arg-type,return-value]
    )

    assert exit_code != 0
    state = harness.run_store.state(run_id)
    assert state.error is not None
    assert state.error.code == REPORT_STAGE_UNAVAILABLE
    assert str(real_execution_result_path(harness.paths.run_dir(run_id))) in str(
        state.error.details
    )


def test_each_run_records_the_executor_its_campaign_will_get(
    tmp_path: Path,
) -> None:
    """The request says which of the two it is, and says it truthfully."""
    placeholder = run_harness(tmp_path / "fake-home")
    placeholder_id = placeholder.start().state.run_id
    real = local_run(tmp_path / "real-home")

    fake_request: RunRequest = placeholder.request(placeholder_id)
    assert fake_request.executor_kind == "fake"
    assert real.request.executor_kind == "verifiers"
    assert isinstance(
        executor_for(fake_request, paths=placeholder.paths), FakeRunExecutor
    )
    assert isinstance(
        executor_for(real.request, paths=paths_from_root(tmp_path / "real-home")),
        RealVerifiersExecutor,
    )


def test_a_request_that_disagrees_with_its_campaign_is_refused(
    tmp_path: Path,
) -> None:
    """Recording the answer does not make the record the authority.

    A request that claims the development executor over a Campaign the real one
    runs is the shape that would quietly turn a paid comparison into invented
    numbers, and the shape that would let a placeholder Campaign be presented as
    a real result. Neither direction is routed; both are refused by name.
    """
    real = local_run(tmp_path / "real-home")
    paths = paths_from_root(tmp_path / "real-home")
    lying = real.request.model_copy(update={"executor_kind": "fake"})

    with pytest.raises(RunError) as raised:
        executor_for(lying, paths=paths)

    assert raised.value.code == "run_executor_mismatch"
    assert raised.value.details["requested"] == "fake"
    assert raised.value.details["campaign"] == "verifiers"


def test_the_recorded_kind_is_the_one_the_campaign_predicate_gives(
    tmp_path: Path,
) -> None:
    """One question, one answer, wherever it is asked from."""
    placeholder = run_harness(tmp_path / "fake-home")
    placeholder_id = placeholder.start().state.run_id
    real = local_run(tmp_path / "real-home")

    assert executor_kind_for(placeholder.inputs(placeholder_id).campaign) == "fake"
    assert executor_kind_for(real.campaign) == "verifiers"
    assert placeholder.request(placeholder_id).executor_kind == executor_kind_for(
        placeholder.inputs(placeholder_id).campaign
    )
    assert real.request.executor_kind == executor_kind_for(real.campaign)


def test_the_engines_own_output_is_made_private_after_it_is_written(
    tmp_path: Path,
) -> None:
    """Raw subject transcripts are the participant's. Spec section 6.19.

    Techtree's own capture files are created ``0600``, but ``traces.jsonl``,
    ``eval.log`` and the resolved configuration are written by the engine under
    whatever umask the operator happens to have, and ``traces.jsonl`` is every
    subject conversation in full. Tightening them is the last thing an
    execution does, successful or not.
    """
    from techtree.runs.real import keep_evaluation_private
    from techtree.verifiers.models import RunPaths, VariantName

    paths = RunPaths(root=tmp_path / "runs" / "run_x")
    for variant in (VariantName.BASELINE, VariantName.CANDIDATE):
        output = paths.variant_output_dir(variant)
        output.mkdir(parents=True)
        for name in ("config.toml", "traces.jsonl", "eval.log"):
            written = output / name
            written.write_text("{}\n")
            written.chmod(0o644)

    keep_evaluation_private(paths)

    for variant in (VariantName.BASELINE, VariantName.CANDIDATE):
        for written in paths.variant_output_dir(variant).iterdir():
            assert stat.S_IMODE(written.stat().st_mode) == 0o600, written


def test_making_an_evaluation_private_tolerates_a_run_that_never_started(
    tmp_path: Path,
) -> None:
    """A run that failed before compiling anything has nothing to tighten."""
    from techtree.runs.real import keep_evaluation_private
    from techtree.verifiers.models import RunPaths

    keep_evaluation_private(RunPaths(root=tmp_path / "runs" / "run_x"))


def test_the_validator_output_is_tightened_with_everything_else(
    tmp_path: Path,
) -> None:
    """WP11g S6: ``taskset/validation`` was left at the operator's umask.

    The engine writes the validator's summary there the same way it writes
    transcripts under ``verifiers/``, and only the second tree was being swept.
    Directories are swept too, because one the engine created carries the
    umask exactly as its contents do.
    """
    from techtree.runs.real import keep_evaluation_private
    from techtree.verifiers.models import RunPaths

    paths = RunPaths(root=tmp_path / "runs" / "run_x")
    validation = paths.root / "taskset" / "validation"
    engine_made = validation / "artifacts"
    engine_made.mkdir(parents=True)
    for directory in (paths.root / "taskset", validation, engine_made):
        directory.chmod(0o755)
    for name in ("summary.json", "artifacts/tasks.jsonl"):
        written = validation / name
        written.write_text("{}\n")
        written.chmod(0o644)

    keep_evaluation_private(paths)

    for path in (paths.root / "taskset").rglob("*"):
        expected = 0o700 if path.is_dir() else 0o600
        assert stat.S_IMODE(path.stat().st_mode) == expected, path


def test_the_privacy_sweep_does_not_follow_a_link_out_of_the_run(
    tmp_path: Path,
) -> None:
    """Chmod through a symlink would tighten a file that is not the run's."""
    from techtree.runs.real import keep_evaluation_private
    from techtree.verifiers.models import RunPaths

    outsider = tmp_path / "somebody-elses.txt"
    outsider.write_text("theirs\n")
    outsider.chmod(0o644)

    paths = RunPaths(root=tmp_path / "runs" / "run_x")
    paths.verifiers_dir.mkdir(parents=True)
    (paths.verifiers_dir / "link.txt").symlink_to(outsider)

    keep_evaluation_private(paths)

    assert stat.S_IMODE(outsider.stat().st_mode) == 0o644


def test_a_run_with_no_staged_inputs_cannot_be_routed(tmp_path: Path) -> None:
    """The Campaign is read from the run's own copy, so it has to be there."""
    from techtree.errors import NotFoundError

    harness = run_harness(tmp_path / "home")
    run_id = harness.start().state.run_id
    from techtree.fs import remove_tree

    remove_tree(harness.artifacts.inputs_dir(run_id))

    with pytest.raises((NotFoundError, RunError)):
        executor_for(harness.request(run_id), paths=harness.paths)
