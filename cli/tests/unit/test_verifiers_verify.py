"""Asking the engine what it thinks of a compiled config. Spec section 6.14.

The dry run is a subprocess, so these tests stand a recording engine in its
place: it captures the argv it was handed and writes whatever resolved
configuration the test wants to reason about. That keeps the questions here
about Techtree's own logic — is the invocation shaped correctly, is a resolved
document compared as a projection rather than byte for byte, is the push
setting checked in the document the engine actually read — and leaves "does the
pinned engine accept this" to the preflight suite, where a real engine answers.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import tomli_w
from pydantic import ValidationError as PydanticValidationError

from fixtures.drafts.support import synthetic_graph
from techtree.canonical import digest_object
from techtree.engines.runner import EngineProcessResult, EngineRunner
from techtree.errors import ValidationError
from techtree.manifests.builder import build_baseline_manifest
from techtree.models.base import ArtifactRef
from techtree.models.campaign import ModelSpec
from techtree.models.engine import EngineDescriptor
from techtree.models.experiment import ExperimentManifest
from techtree.models.validation import TasksetLock
from techtree.verifiers.child import (
    CONFIG_ARGUMENT_MARKER,
    DRY_RUN_FLAG,
    EVAL_EXECUTABLE,
    PUSH_DISABLED_FLAG,
    dry_run_argv,
)
from techtree.verifiers.config import (
    DockerRuntimeToml,
    EnvToml,
    EvalClientToml,
    EvalToml,
    HermesHarnessToml,
    SamplingToml,
    SubjectAgentToml,
    TasksetToml,
    config_to_toml_bytes,
)
from techtree.verifiers.models import (
    ChildProcessOutcome,
    NormalizedEpisode,
    NormalizedReward,
    NormalizedRuntime,
    NormalizedTrace,
    SubjectImageResolution,
    VariantExecutionResult,
    VariantName,
)
from techtree.verifiers.verify import (
    dry_run_variant_config,
    verify_compiled_config,
    verify_variant_execution,
)

PINNED_IMAGE = f"ghcr.io/techtree/subject@sha256:{'a' * 64}"


def compiled(output_dir: Path) -> EvalToml:
    return EvalToml(
        model="vendor/small-instruct",
        client=EvalClientToml(api_key_var="PRIME_API_KEY"),
        sampling=SamplingToml(temperature=0.0, max_tokens=512),
        env=EnvToml(
            taskset=TasksetToml(id="procedure-transfer-v1"),
            subject=SubjectAgentToml(
                harness=HermesHarnessToml(version="0.19.0", skills=[]),
                runtime=DockerRuntimeToml(image=PINNED_IMAGE, cpu=2.0, memory=4.0),
            ),
        ),
        num_tasks=4,
        max_concurrent=1,
        output_dir=str(output_dir),
    )


def resolved_document(config: EvalToml, **overrides: Any) -> dict[str, Any]:
    """Return what the engine would write back for ``config``.

    Modelled on the real thing: every default Techtree never mentioned is
    filled in, ``client.base_url`` is resolved from the Prime configuration,
    and a routing header may be added.
    """
    document = config.model_dump(mode="json", exclude_none=True)
    document["verbose"] = False
    document["server"] = False
    document["client"]["base_url"] = "https://api.pinference.ai/api/v1"
    document["client"]["headers"] = {"X-Prime-Team-ID": "team-42"}
    document["env"]["interception"] = {"type": "elastic", "multiplex": 32}
    document["env"]["subject"]["runtime"]["workdir"] = "/app"
    document.update(overrides)
    return document


class RecordingEngine(EngineRunner):
    """An engine whose ``eval`` writes a chosen resolved config."""

    def __init__(
        self, *, document: dict[str, Any] | None, exit_code: int = 0, stderr: str = ""
    ) -> None:
        self.document = document
        self.exit_code = exit_code
        self.stderr = stderr
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def run(
        self,
        executable: str,
        args: Sequence[str],
        *,
        timeout: float,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> EngineProcessResult:
        self.calls.append((executable, tuple(args)))
        if self.document is not None:
            # --output-dir on argv overrides the file, so the engine records
            # the directory it was pointed at rather than the compiled one.
            document = {**self.document, "output_dir": str(args[-1])}
            destination = Path(args[-1]) / "config.toml"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(tomli_w.dumps(document))
        return EngineProcessResult(
            argv=(executable, *args),
            exit_code=self.exit_code,
            stdout="",
            stderr=self.stderr,
            duration_seconds=0.01,
        )


@pytest.fixture
def written_config(tmp_path: Path) -> tuple[EvalToml, Path, Path]:
    """A compiled config on disk, plus its input path and dry-run directory."""
    config = compiled(tmp_path / "verifiers" / "baseline" / "run")
    input_path = tmp_path / "verifiers" / "baseline" / "input.toml"
    input_path.parent.mkdir(parents=True)
    input_path.write_bytes(config_to_toml_bytes(config))
    return config, input_path, tmp_path / "verifiers" / "baseline" / "dry-run"


# ---------------------------------------------------------------------------
# The invocation
# ---------------------------------------------------------------------------


def test_the_config_file_is_passed_as_its_own_argv_marker(tmp_path: Path) -> None:
    argv = dry_run_argv(
        input_config_path=tmp_path / "input.toml", dry_run_dir=tmp_path / "dry-run"
    )

    assert argv[0] == CONFIG_ARGUMENT_MARKER
    assert argv[1] == str(tmp_path / "input.toml")
    assert DRY_RUN_FLAG in argv


def test_the_upload_is_also_disabled_on_the_command_line(tmp_path: Path) -> None:
    # push defaults to true upstream, so the flag is belt and braces alongside
    # push = false in the compiled document.
    argv = dry_run_argv(
        input_config_path=tmp_path / "input.toml", dry_run_dir=tmp_path / "dry-run"
    )
    assert PUSH_DISABLED_FLAG in argv


def test_no_credential_can_appear_in_the_invocation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret = "sk-verify-unit-test-secret"
    monkeypatch.setenv("PRIME_API_KEY", secret)

    argv = dry_run_argv(
        input_config_path=tmp_path / "input.toml", dry_run_dir=tmp_path / "dry-run"
    )

    assert not any(secret in argument for argument in argv)


def test_the_engines_own_eval_script_is_the_one_asked_for(
    written_config: tuple[EvalToml, Path, Path],
) -> None:
    config, input_path, dry_run_dir = written_config
    engine = RecordingEngine(document=resolved_document(config))

    dry_run_variant_config(
        engine_runner=engine,
        variant=VariantName.BASELINE,
        compiled=config,
        input_config_path=input_path,
        dry_run_dir=dry_run_dir,
    )

    assert engine.calls[0][0] == EVAL_EXECUTABLE


def test_the_validation_leaves_a_record_beside_what_it_validated(
    written_config: tuple[EvalToml, Path, Path],
) -> None:
    # Spec section 6.19. A reviewer should be able to read what was asked and
    # what came back, rather than infer it from the resolved document.
    config, input_path, dry_run_dir = written_config
    engine = RecordingEngine(document=resolved_document(config))

    dry_run_variant_config(
        engine_runner=engine,
        variant=VariantName.BASELINE,
        compiled=config,
        input_config_path=input_path,
        dry_run_dir=dry_run_dir,
    )

    written = (dry_run_dir / "command.log").read_text()
    assert "variant: baseline" in written
    assert "--dry-run" in written
    assert "exit-code: 0" in written


def test_a_failed_validation_still_leaves_its_record(
    written_config: tuple[EvalToml, Path, Path],
) -> None:
    config, input_path, dry_run_dir = written_config
    engine = RecordingEngine(document=None, exit_code=1, stderr="unknown key")

    dry_run_variant_config(
        engine_runner=engine,
        variant=VariantName.BASELINE,
        compiled=config,
        input_config_path=input_path,
        dry_run_dir=dry_run_dir,
    )

    written = (dry_run_dir / "command.log").read_text()
    assert "exit-code: 1" in written
    assert "unknown key" in written


def test_a_config_that_was_never_written_is_refused_before_the_engine_runs(
    tmp_path: Path,
) -> None:
    config = compiled(tmp_path / "run")
    engine = RecordingEngine(document=None)

    with pytest.raises(ValidationError) as caught:
        dry_run_variant_config(
            engine_runner=engine,
            variant=VariantName.BASELINE,
            compiled=config,
            input_config_path=tmp_path / "absent.toml",
            dry_run_dir=tmp_path / "dry-run",
        )
    assert caught.value.code == "variant_dry_run_failed"
    assert engine.calls == []


# ---------------------------------------------------------------------------
# Reading the verdict
# ---------------------------------------------------------------------------


def test_a_clean_dry_run_passes_every_check(
    written_config: tuple[EvalToml, Path, Path],
) -> None:
    config, input_path, dry_run_dir = written_config
    engine = RecordingEngine(document=resolved_document(config))

    outcome = dry_run_variant_config(
        engine_runner=engine,
        variant=VariantName.BASELINE,
        compiled=config,
        input_config_path=input_path,
        dry_run_dir=dry_run_dir,
    )

    assert outcome.ok is True
    assert outcome.failures == ()
    assert {check.id for check in outcome.checks} >= {
        "engine_eval_accepted_config",
        "resolved_config_written",
        "resolved_config_matches_compiled",
        "platform_push_disabled",
        "named_subject_seat_resolved",
        "runtime_image_digest_pinned",
        "output_directory_is_run_owned",
    }


def test_a_real_run_writing_outside_the_run_tree_is_a_failure(
    tmp_path: Path,
) -> None:
    # The dry run is redirected by argv, so the directory the real run would
    # use is checked on the compiled document rather than the resolved one.
    config = compiled(tmp_path / "somewhere-else")
    input_path = tmp_path / "input.toml"
    input_path.write_bytes(config_to_toml_bytes(config))
    engine = RecordingEngine(document=resolved_document(config))

    outcome = dry_run_variant_config(
        engine_runner=engine,
        variant=VariantName.BASELINE,
        compiled=config,
        input_config_path=input_path,
        dry_run_dir=tmp_path / "dry-run",
    )

    assert "output_directory_is_run_owned" in {check.id for check in outcome.failures}


def test_a_rejected_config_reports_the_engines_own_complaint(
    written_config: tuple[EvalToml, Path, Path],
) -> None:
    config, input_path, dry_run_dir = written_config
    engine = RecordingEngine(
        document=None,
        exit_code=1,
        stderr=(
            "╭─ Config file error ──────────╮\n"
            "│ --env.subject                │\n"
            "│ Extra inputs are not permitted│\n"
            "╰──────────────────────────────╯\n"
        ),
    )

    outcome = dry_run_variant_config(
        engine_runner=engine,
        variant=VariantName.BASELINE,
        compiled=config,
        input_config_path=input_path,
        dry_run_dir=dry_run_dir,
    )

    assert outcome.ok is False
    failed = {check.id for check in outcome.failures}
    assert "engine_eval_accepted_config" in failed
    invocation = next(
        check for check in outcome.checks if check.id == "engine_eval_accepted_config"
    )
    assert "Extra inputs are not permitted" in invocation.detail


def test_the_engines_own_defaults_are_not_treated_as_disagreements(
    written_config: tuple[EvalToml, Path, Path],
) -> None:
    config, _, _ = written_config

    checks = verify_compiled_config(compiled=config, resolved=resolved_document(config))

    match = next(
        check for check in checks if check.id == "resolved_config_matches_compiled"
    )
    assert match.status == "passed"


def test_a_value_the_engine_changed_is_a_disagreement(
    written_config: tuple[EvalToml, Path, Path],
) -> None:
    config, _, _ = written_config
    document = resolved_document(config)
    document["num_tasks"] = 3

    checks = verify_compiled_config(compiled=config, resolved=document)

    match = next(
        check for check in checks if check.id == "resolved_config_matches_compiled"
    )
    assert match.status == "failed"
    assert "num_tasks" in match.detail


def test_a_resolved_config_that_would_upload_fails_the_push_check(
    written_config: tuple[EvalToml, Path, Path],
) -> None:
    config, _, _ = written_config
    document = resolved_document(config)
    document["push"] = True

    checks = verify_compiled_config(compiled=config, resolved=document)

    push = next(check for check in checks if check.id == "platform_push_disabled")
    assert push.status == "failed"


def test_an_environment_that_seats_an_agent_rather_than_a_subject_fails(
    written_config: tuple[EvalToml, Path, Path],
) -> None:
    config, _, _ = written_config
    document = resolved_document(config)
    document["env"]["agent"] = document["env"].pop("subject")

    checks = verify_compiled_config(compiled=config, resolved=document)

    seat = next(check for check in checks if check.id == "named_subject_seat_resolved")
    assert seat.status == "failed"


def test_an_unpinned_runtime_image_warns_rather_than_failing(tmp_path: Path) -> None:
    # The shipped development Campaign is deliberately not digest-pinned, so
    # this is a release gate rather than a compilation error.
    run_dir = tmp_path / "verifiers" / "baseline" / "run"
    config = compiled(run_dir).model_copy(
        update={
            "env": compiled(run_dir).env.model_copy(
                update={
                    "subject": compiled(run_dir).env.subject.model_copy(
                        update={"runtime": DockerRuntimeToml(image="python:3.12-slim")}
                    )
                }
            )
        }
    )
    input_path = tmp_path / "input.toml"
    input_path.write_bytes(config_to_toml_bytes(config))
    engine = RecordingEngine(document=resolved_document(config))

    outcome = dry_run_variant_config(
        engine_runner=engine,
        variant=VariantName.BASELINE,
        compiled=config,
        input_config_path=input_path,
        dry_run_dir=tmp_path / "dry-run",
    )

    pinning = next(
        check for check in outcome.checks if check.id == "runtime_image_digest_pinned"
    )
    assert pinning.status == "warning"
    assert outcome.ok is True


def test_the_credential_is_a_separate_verdict_from_the_configuration(
    written_config: tuple[EvalToml, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    config, input_path, dry_run_dir = written_config
    monkeypatch.delenv("PRIME_API_KEY", raising=False)
    monkeypatch.setenv("HOME", str(dry_run_dir.parent))
    engine = RecordingEngine(document=resolved_document(config))

    outcome = dry_run_variant_config(
        engine_runner=engine,
        variant=VariantName.BASELINE,
        compiled=config,
        input_config_path=input_path,
        dry_run_dir=dry_run_dir,
        model=ModelSpec(
            provider="prime",
            model_id="vendor/small-instruct",
            revision=None,
            credential_env="PRIME_API_KEY",
        ),
    )

    configuration = next(
        check
        for check in outcome.checks
        if check.id == "resolved_config_matches_compiled"
    )
    credential = next(
        check
        for check in outcome.checks
        if check.id == "evaluation_credential_available"
    )
    assert configuration.status == "passed"
    assert credential.status == "failed"


# ---------------------------------------------------------------------------
# After the run: verify_variant_execution
# ---------------------------------------------------------------------------


VERIFIERS_VERSION = "0.3.1.dev21"
VERIFIERS_REVISION = "7e1c47d24d055aae587ee8259f77a3e8e193513a"


def execution_fixture(
    **trace_overrides: Any,
) -> tuple[VariantExecutionResult, ExperimentManifest, TasksetLock, EngineDescriptor]:
    """A complete, valid baseline execution of the synthetic Campaign."""
    graph = synthetic_graph()
    campaign = graph.campaign
    manifest = build_baseline_manifest(
        campaign=campaign,
        campaign_digest=graph.campaign_digest,
        public_context=None,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    committed = list(campaign.taskset.membership.ordered_task_hashes)
    subject = campaign.subject

    episodes = []
    for position, task_hash in enumerate(committed):
        fields: dict[str, Any] = {
            "trace_id": f"trace-{position}",
            "agent_role": "subject",
            "task_hash": task_hash,
            "ok": True,
            "verifiers_version": VERIFIERS_VERSION,
            "verifiers_revision": VERIFIERS_REVISION,
            "model_id": subject.model.model_id,
            "sampling": {
                "max_tokens": subject.sampling.max_tokens,
                "temperature": subject.sampling.temperature,
            },
            "harness_id": subject.harness.id,
            "harness_version": subject.harness.version,
            "use_bundled_skill": False,
            "skill_root_digests": [a.digest for a in subject.harness.skills],
            "runtime": NormalizedRuntime(
                kind="docker",
                runtime_id=f"container-{position}",
                image=subject.runtime.image,
                image_index_digest=subject.runtime.image_index_digest,
                cpu=subject.runtime.cpu,
                memory_gb=subject.runtime.memory_gb,
            ),
            "tools": [],
            "rewards": [
                NormalizedReward(
                    name=campaign.scoring.primary_reward,
                    score=1.0,
                    weight=1.0,
                    value=1.0,
                )
            ],
            "metrics": {},
            "usage": None,
            "model_calls": 1,
            "num_turns": 1,
            "last_reply": "BRANCH-01",
            "errors": [],
            "raw_trace_digest": f"sha256:{'2' * 64}",
        }
        fields.update(trace_overrides)
        episodes.append(
            NormalizedEpisode(
                episode_id=f"episode-{position}",
                env_id=campaign.taskset.ref.id,
                task_hash=fields["task_hash"],
                task_position=position,
                ok=True,
                traces=[NormalizedTrace.model_validate(fields)],
                errors=[],
                raw_episode_digest=f"sha256:{'3' * 64}",
            )
        )

    artifact = ArtifactRef(
        digest=f"sha256:{'4' * 64}",
        media_type="text/plain",
        size=1,
        relative_path=None,
    )
    result = VariantExecutionResult(
        variant=VariantName.BASELINE,
        experiment_manifest_digest=digest_object(manifest),
        resolved_verifiers_config=artifact,
        raw_traces=artifact,
        eval_log=artifact,
        normalized_episodes=artifact,
        child_outcome=ChildProcessOutcome(
            variant=VariantName.BASELINE,
            argv_digest=f"sha256:{'5' * 64}",
            exit_code=0,
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
            finished_at=datetime(2026, 1, 1, tzinfo=UTC),
            stdout_artifact=artifact,
            stderr_artifact=artifact,
            cancelled=False,
        ),
        image_resolution=SubjectImageResolution(
            variant=VariantName.BASELINE,
            image=subject.runtime.image,
            index_digest=subject.runtime.image_index_digest,
            platform=sorted(subject.runtime.image_platform_digests)[0],
        ),
        episodes=episodes,
    )
    lock = TasksetLock(
        schema_version="techtree.taskset-lock.v1alpha1",
        taskset_ref=campaign.taskset.ref,
        engine_digest=f"sha256:{'6' * 64}",
        resolved_package_digest=campaign.taskset.ref.package.digest,
        ordered_task_hashes=committed,
        membership_digest=campaign.taskset.membership.membership_digest,
        task_count=len(committed),
    )
    descriptor = EngineDescriptor(
        schema_version="techtree.engine.v1alpha1",
        name="default",
        python_version="3.12",
        verifiers_version=VERIFIERS_VERSION,
        verifiers_revision=VERIFIERS_REVISION,
        supported_hosts=["darwin/arm64"],
        packages=[],
    )
    return result, manifest, lock, descriptor


def verdicts(
    result: VariantExecutionResult,
    manifest: ExperimentManifest,
    lock: TasksetLock,
    descriptor: EngineDescriptor,
) -> dict[str, str]:
    checks = verify_variant_execution(
        result=result,
        experiment=manifest,
        taskset_lock=lock,
        primary_reward="synthetic_reward",
        engine=descriptor,
    )
    return {check.id: check.status for check in checks}


def test_a_complete_execution_passes_every_check() -> None:
    statuses = verdicts(*execution_fixture())
    assert set(statuses.values()) == {"passed"}


def test_a_cancelled_execution_is_reported_as_cancelled_not_invalid() -> None:
    result, manifest, lock, descriptor = execution_fixture()
    cancelled = result.model_copy(
        update={
            "child_outcome": result.child_outcome.model_copy(
                update={"cancelled": True, "exit_code": 130}
            )
        }
    )

    statuses = verdicts(cancelled, manifest, lock, descriptor)

    assert statuses["child_completed"] == "failed"
    # Everything the run did produce is still sound; only completion failed.
    assert statuses["ordered_task_membership"] == "passed"


def test_a_missing_committed_task_fails_the_membership_checks() -> None:
    result, manifest, lock, descriptor = execution_fixture()
    short = result.model_copy(update={"episodes": result.episodes[:-1]})

    statuses = verdicts(short, manifest, lock, descriptor)

    assert statuses["episode_count"] == "failed"
    assert statuses["ordered_task_membership"] == "failed"


def test_a_trace_scored_under_another_role_fails() -> None:
    # Unrepresentable by construction, so the guard is the model itself.
    with pytest.raises(PydanticValidationError):
        execution_fixture(agent_role="agent")


def test_a_missing_primary_reward_fails() -> None:
    result, manifest, lock, descriptor = execution_fixture(
        rewards=[
            NormalizedReward(name="something_else", score=1.0, weight=1.0, value=1.0)
        ]
    )

    statuses = verdicts(result, manifest, lock, descriptor)

    assert statuses["primary_reward_present"] == "failed"


def test_a_bundled_skill_catalogue_in_the_evidence_fails() -> None:
    result, manifest, lock, descriptor = execution_fixture(use_bundled_skill=True)
    assert verdicts(result, manifest, lock, descriptor)["bundled_skills_disabled"] == (
        "failed"
    )


def test_a_model_other_than_the_declared_one_fails() -> None:
    result, manifest, lock, descriptor = execution_fixture(model_id="vendor/something")
    assert verdicts(result, manifest, lock, descriptor)["model_id_matches"] == "failed"


def test_evidence_from_another_verifiers_build_fails_the_pin_check() -> None:
    result, manifest, lock, descriptor = execution_fixture(verifiers_revision="0" * 40)
    assert (
        verdicts(result, manifest, lock, descriptor)["verifiers_pin_matches_engine"]
        == "failed"
    )


def test_a_manifest_with_no_subject_cannot_be_verified_at_all() -> None:
    result, manifest, lock, _ = execution_fixture()
    configuration = manifest.configuration.model_copy(update={"agents": {}})
    headless = manifest.model_copy(update={"configuration": configuration})

    with pytest.raises(ValidationError) as caught:
        verify_variant_execution(
            result=result,
            experiment=headless,
            taskset_lock=lock,
            primary_reward="synthetic_reward",
        )
    assert caught.value.code == "variant_execution_uncheckable"
