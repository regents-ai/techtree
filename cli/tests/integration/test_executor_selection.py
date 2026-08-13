"""Which executor a run gets, and why. Spec section 16, WP6 row 12.

"The fake executor is no longer the default for a real Campaign" is a rule
about a decision the worker makes before it does anything, and the decision
cannot be read off the run's request: a request names the Climb that was
entered, and whether that Climb's subject is a real model on a real image or
the placeholder pair this build ships is a fact about the Campaign. So the
worker reads the run's own staged Campaign, and the same predicate that
``techtree doctor --for-evaluation`` uses answers it.

Nothing here executes anything. Both runs are staged for real and then only
asked which executor they would be handed, because constructing the answer is
the whole of what is under test and running it would cost a container and a
provider.
"""

from __future__ import annotations

import stat
from pathlib import Path
from typing import Final

import pytest

from fixtures.runs.support import run_harness
from fixtures.verifiers.support import local_campaign, local_run
from techtree.errors import PrerequisiteError, RunError
from techtree.models.run import RunRequest
from techtree.paths import paths_from_root
from techtree.runs.fake import FakeRunExecutor
from techtree.runs.real import (
    REAL_EXECUTION_UNSUPPORTED,
    RealVerifiersExecutor,
    campaign_is_executable,
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
_SUBJECT_IMAGE: Final = "python@sha256:" + "0" * 64


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
    run = local_run(home, campaign=local_campaign(image=_SUBJECT_IMAGE).campaign)

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


def test_the_selection_reads_the_campaign_rather_than_the_request(
    tmp_path: Path,
) -> None:
    """Two runs with identical request shapes route differently by Campaign."""
    placeholder = run_harness(tmp_path / "fake-home")
    placeholder_id = placeholder.start().state.run_id
    real = local_run(
        tmp_path / "real-home", campaign=local_campaign(image=_SUBJECT_IMAGE).campaign
    )

    fake_request: RunRequest = placeholder.request(placeholder_id)
    assert fake_request.executor_kind == real.request.executor_kind == "fake"
    assert isinstance(
        executor_for(fake_request, paths=placeholder.paths), FakeRunExecutor
    )
    assert isinstance(
        executor_for(real.request, paths=paths_from_root(tmp_path / "real-home")),
        RealVerifiersExecutor,
    )


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


def test_a_run_with_no_staged_inputs_cannot_be_routed(tmp_path: Path) -> None:
    """The Campaign is read from the run's own copy, so it has to be there."""
    from techtree.errors import NotFoundError

    harness = run_harness(tmp_path / "home")
    run_id = harness.start().state.run_id
    from techtree.fs import remove_tree

    remove_tree(harness.artifacts.inputs_dir(run_id))

    with pytest.raises((NotFoundError, RunError)):
        executor_for(harness.request(run_id), paths=harness.paths)
