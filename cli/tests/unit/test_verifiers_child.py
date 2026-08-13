"""One evaluation child process, without an engine. Spec section 6.10.

Every process started here is a shell or a Python one-liner, so the questions
are about Techtree's own behaviour — is the invocation shaped correctly, do the
streams land in files rather than anywhere a reader could see them, does a
termination reach the whole process group — and not about what the pinned engine
does with them. That belongs to the preflight suite and to the real-model run.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from techtree.errors import RunError
from techtree.verifiers.child import (
    CONFIG_ARGUMENT_MARKER,
    PUSH_DISABLED_FLAG,
    VerifiersChild,
    argv_digest,
    eval_argv,
    write_command_log,
)
from techtree.verifiers.models import VariantName


def child(
    tmp_path: Path,
    argv: list[str],
    *,
    variant: VariantName = VariantName.BASELINE,
) -> VerifiersChild:
    """Build a child that captures into ``tmp_path``."""
    return VerifiersChild(
        variant=variant,
        argv=argv,
        cwd=tmp_path / "cwd",
        env={"PATH": os.environ.get("PATH", "")},
        stdout_path=tmp_path / "run" / "stdout.log",
        stderr_path=tmp_path / "run" / "stderr.log",
    )


def wait_for_exit(started: VerifiersChild) -> int:
    """Wait for a child that is expected to finish promptly."""
    return started.wait(timeout=30.0)


# ---------------------------------------------------------------------------
# The invocation
# ---------------------------------------------------------------------------


def test_the_engines_own_eval_is_named_by_absolute_path(tmp_path: Path) -> None:
    executable = tmp_path / "engine" / ".venv" / "bin" / "eval"

    argv = eval_argv(
        eval_executable=executable, input_config_path=tmp_path / "input.toml"
    )

    assert argv[0] == str(executable)
    assert Path(argv[0]).is_absolute()


def test_the_config_travels_as_its_own_argv_marker(tmp_path: Path) -> None:
    argv = eval_argv(
        eval_executable=tmp_path / "eval", input_config_path=tmp_path / "input.toml"
    )

    assert argv[1] == CONFIG_ARGUMENT_MARKER
    assert argv[2] == str(tmp_path / "input.toml")


def test_the_upload_is_disabled_on_the_command_line(tmp_path: Path) -> None:
    # push defaults to true upstream, so the flag backs up push = false in the
    # compiled document rather than replacing it.
    argv = eval_argv(
        eval_executable=tmp_path / "eval", input_config_path=tmp_path / "input.toml"
    )

    assert PUSH_DISABLED_FLAG in argv


def test_the_real_invocation_never_overrides_the_output_directory(
    tmp_path: Path,
) -> None:
    # The compiled config already names an absolute output_dir, and the
    # resolved config is compared against it. A second copy on argv would be a
    # second place the two could disagree.
    argv = eval_argv(
        eval_executable=tmp_path / "eval", input_config_path=tmp_path / "input.toml"
    )

    assert "--output-dir" not in argv


def test_no_credential_can_appear_in_the_invocation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret = "sk-child-unit-test-secret"
    monkeypatch.setenv("PRIME_API_KEY", secret)

    argv = eval_argv(
        eval_executable=tmp_path / "eval", input_config_path=tmp_path / "input.toml"
    )

    assert not any(secret in argument for argument in argv)


def test_two_different_invocations_digest_differently(tmp_path: Path) -> None:
    first = argv_digest(["eval", "@", "a.toml"])
    second = argv_digest(["eval", "@", "b.toml"])
    joined = argv_digest(["eval", "@ a.toml"])

    assert first != second
    # A separator that could appear inside an argument would let two different
    # vectors hash the same; the digest joins on a byte no argv can contain.
    assert first != joined


# ---------------------------------------------------------------------------
# Output redirection
# ---------------------------------------------------------------------------


def test_everything_the_child_prints_lands_in_a_file(tmp_path: Path) -> None:
    started = child(
        tmp_path,
        [sys.executable, "-c", "print('a trace the operator must not see')"],
    )
    started.start()
    wait_for_exit(started)

    assert (
        "a trace the operator must not see"
        in (tmp_path / "run" / "stdout.log").read_text()
    )


def test_the_two_streams_are_captured_separately(tmp_path: Path) -> None:
    started = child(
        tmp_path,
        [
            sys.executable,
            "-c",
            "import sys; print('out'); print('err', file=sys.stderr)",
        ],
    )
    started.start()
    wait_for_exit(started)

    assert "out" in (tmp_path / "run" / "stdout.log").read_text()
    assert "err" in (tmp_path / "run" / "stderr.log").read_text()
    assert "err" not in (tmp_path / "run" / "stdout.log").read_text()


def test_a_capture_file_says_which_variant_and_invocation_produced_it(
    tmp_path: Path,
) -> None:
    started = child(tmp_path, [sys.executable, "-c", "pass"])
    started.start()
    wait_for_exit(started)

    header = (tmp_path / "run" / "stdout.log").read_text().splitlines()[0]
    assert "baseline" in header
    assert started.argv_digest in header


def test_a_silent_stream_still_produces_a_well_formed_artifact(
    tmp_path: Path,
) -> None:
    # An ArtifactRef describes a byte stream and cannot describe an empty one,
    # so a stream that said nothing must still have left a file with content.
    started = child(tmp_path, [sys.executable, "-c", "pass"])
    started.start()
    wait_for_exit(started)

    outcome = started.outcome()

    assert outcome.stderr_artifact.size > 0


def test_capture_files_are_private_to_the_operator(tmp_path: Path) -> None:
    started = child(tmp_path, [sys.executable, "-c", "pass"])
    started.start()
    wait_for_exit(started)

    mode = (tmp_path / "run" / "stdout.log").stat().st_mode & 0o777
    assert mode == 0o600


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_a_child_that_has_not_started_has_no_outcome(tmp_path: Path) -> None:
    with pytest.raises(RunError) as caught:
        child(tmp_path, [sys.executable, "-c", "pass"]).outcome()

    assert caught.value.code == "eval_child_not_started"


def test_a_running_child_has_no_outcome_yet(tmp_path: Path) -> None:
    started = child(tmp_path, [sys.executable, "-c", "import time; time.sleep(30)"])
    started.start()
    try:
        with pytest.raises(RunError) as caught:
            started.outcome()
        assert caught.value.code == "eval_child_still_running"
    finally:
        started.terminate(grace_seconds=1.0)


def test_a_child_cannot_be_started_twice(tmp_path: Path) -> None:
    started = child(tmp_path, [sys.executable, "-c", "pass"])
    started.start()
    wait_for_exit(started)

    with pytest.raises(RunError) as caught:
        started.start()
    assert caught.value.code == "eval_child_start_failed"


def test_a_program_that_does_not_exist_is_a_named_failure(tmp_path: Path) -> None:
    started = child(tmp_path, [str(tmp_path / "no-such-eval")])

    with pytest.raises(RunError) as caught:
        started.start()
    assert caught.value.code == "eval_child_start_failed"


def test_waiting_past_a_deadline_is_a_named_failure(tmp_path: Path) -> None:
    started = child(tmp_path, [sys.executable, "-c", "import time; time.sleep(30)"])
    started.start()
    try:
        with pytest.raises(RunError) as caught:
            started.wait(timeout=0.2)
        assert caught.value.code == "eval_child_still_running"
    finally:
        started.terminate(grace_seconds=1.0)


def test_the_outcome_records_the_exit_code_and_the_clock(tmp_path: Path) -> None:
    started = child(tmp_path, [sys.executable, "-c", "raise SystemExit(3)"])
    started.start()
    wait_for_exit(started)

    outcome = started.outcome()

    assert outcome.exit_code == 3
    assert outcome.variant is VariantName.BASELINE
    assert outcome.finished_at >= outcome.started_at
    assert not outcome.cancelled


def test_the_outcome_carries_a_digest_rather_than_the_command_line(
    tmp_path: Path,
) -> None:
    started = child(tmp_path, [sys.executable, "-c", "pass"])
    started.start()
    wait_for_exit(started)

    outcome = started.outcome()

    assert outcome.argv_digest.startswith("sha256:")
    assert sys.executable not in outcome.model_dump_json()


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


def test_terminating_reaches_the_whole_process_group(tmp_path: Path) -> None:
    # The pinned engine tears its containers down inside the rollout it
    # signalled, and the rollouts are grandchildren. A signal that reached only
    # the direct child would leave them running.
    marker = tmp_path / "grandchild.pid"
    program = (
        "import subprocess, sys, time\n"
        "kid = subprocess.Popen(\n"
        "    [sys.executable, '-c', 'import time; time.sleep(60)']\n"
        ")\n"
        f"open({str(marker)!r}, 'w').write(str(kid.pid))\n"
        "time.sleep(60)\n"
    )
    started = child(tmp_path, [sys.executable, "-c", program])
    started.start()

    deadline = time.monotonic() + 20.0
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert marker.exists(), "the grandchild never announced itself"
    grandchild = int(marker.read_text())

    started.terminate(grace_seconds=2.0)

    assert not _alive(grandchild)


def test_a_terminated_child_records_that_it_was_cancelled(tmp_path: Path) -> None:
    started = child(tmp_path, [sys.executable, "-c", "import time; time.sleep(60)"])
    started.start()
    started.terminate(grace_seconds=1.0)

    assert started.outcome().cancelled


def test_termination_is_gentle_before_it_is_final(tmp_path: Path) -> None:
    # The grace period exists so the engine can run its own teardown. A child
    # that handles SIGTERM must be given the chance to exit on its own terms.
    program = (
        "import signal, sys, time\n"
        "signal.signal(signal.SIGTERM, lambda *_: sys.exit(130))\n"
        "time.sleep(60)\n"
    )
    started = child(tmp_path, [sys.executable, "-c", program])
    started.start()
    time.sleep(0.5)

    started.terminate(grace_seconds=10.0)

    assert started.outcome().exit_code == 130


def test_leaving_the_context_stops_a_child_that_is_still_running(
    tmp_path: Path,
) -> None:
    with child(tmp_path, [sys.executable, "-c", "import time; time.sleep(60)"]) as live:
        pid = live.pid
    assert pid is not None
    assert not _alive(pid)


# ---------------------------------------------------------------------------
# The dry run's record
# ---------------------------------------------------------------------------


def test_a_command_log_records_what_was_asked_and_answered(tmp_path: Path) -> None:
    path = write_command_log(
        tmp_path / "dry-run" / "command.log",
        variant=VariantName.CANDIDATE,
        argv=["/engine/.venv/bin/eval", "@", "/run/input.toml", "--dry-run"],
        exit_code=0,
        stdout="resolved",
        stderr="",
    )

    written = path.read_text()
    assert "candidate" in written
    assert "--dry-run" in written
    assert "exit-code: 0" in written
    assert "resolved" in written


def test_a_command_log_is_private_to_the_operator(tmp_path: Path) -> None:
    path = write_command_log(
        tmp_path / "dry-run" / "command.log",
        variant=VariantName.BASELINE,
        argv=["eval"],
        exit_code=1,
        stdout="",
        stderr="boom",
    )

    assert path.stat().st_mode & 0o777 == 0o600


def _alive(pid: int) -> bool:
    """Whether one process still exists, allowing a moment for it to be reaped."""
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return False
        # A zombie answers signal 0 until its parent reaps it, and this test's
        # parent is gone, so re-parenting to init clears it shortly.
        if _is_zombie(pid):
            return False
        time.sleep(0.05)
    return True


def _is_zombie(pid: int) -> bool:
    """Whether a pid names a process that has exited but not been reaped."""
    completed = subprocess.run(
        ["ps", "-o", "state=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip().startswith("Z")
