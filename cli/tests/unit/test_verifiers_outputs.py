"""What a finished evaluation must have left on disk. Spec section 6.13.

Three properties are worth testing here and two are easy to get wrong. The easy
one is that the three upstream files exist. The first that matters is *where*:
two of the three live in subdirectories the released engine writes
(``docs/verifiers-pin-0.3.1.md``, deviations D1 and D5), and a run directory is
laid out here the way the engine lays it out — the ``logs/latest`` symlink
included — rather than the way Techtree would find convenient. The second is
that a partially written normalized file is refused rather than parsed: a JSONL
reader that stops at the last complete line silently drops an episode, and a
comparison missing one task still looks like a comparison.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from techtree.canonical import sha256_digest_bytes
from techtree.errors import ValidationError
from techtree.verifiers.models import (
    NormalizedEpisode,
    NormalizedReward,
    NormalizedRuntime,
    NormalizedTrace,
    NormalizedUsage,
)
from techtree.verifiers.outputs import (
    EVAL_LOG_PATH,
    RESOLVED_CONFIG_PATH,
    TRACES_FILENAME,
    artifact_for,
    read_normalized_episodes,
    require_output_files,
    required_output_paths,
)

TASK_HASH = f"sha256:{'1' * 64}"
VERIFIERS_VERSION = "0.3.1.dev21"
VERIFIERS_REVISION = "7e1c47d24d055aae587ee8259f77a3e8e193513a"
RAW_DIGEST = f"sha256:{'2' * 64}"
SKILL_DIGEST = f"sha256:{'3' * 64}"
IMAGE_DIGEST = f"sha256:{'4' * 64}"


def normalized_trace(task_hash: str = TASK_HASH) -> NormalizedTrace:
    return NormalizedTrace(
        trace_id="trace-0",
        agent_role="subject",
        task_hash=task_hash,
        ok=True,
        verifiers_version=VERIFIERS_VERSION,
        verifiers_revision=VERIFIERS_REVISION,
        model_id="vendor/small-instruct",
        sampling={"max_tokens": 512, "temperature": 0.0},
        harness_id="hermes-agent",
        harness_version="0.19.0",
        use_bundled_skill=False,
        skill_root_digests=[SKILL_DIGEST],
        runtime=NormalizedRuntime(
            kind="docker",
            runtime_id="container-1",
            image=f"ghcr.io/techtree/subject@{IMAGE_DIGEST}",
            image_index_digest=IMAGE_DIGEST,
            cpu=2.0,
            memory_gb=4.0,
        ),
        tools=[],
        rewards=[
            NormalizedReward(name="exact_match", score=1.0, weight=1.0, value=1.0)
        ],
        metrics={},
        usage=NormalizedUsage(input_tokens=10, output_tokens=4, total_tokens=14),
        model_calls=1,
        num_turns=1,
        last_reply="BRANCH-01",
        errors=[],
        raw_trace_digest=RAW_DIGEST,
    )


def normalized_episode(position: int = 0) -> NormalizedEpisode:
    return NormalizedEpisode(
        episode_id=f"episode-{position}",
        env_id="procedure-transfer-v1",
        task_hash=TASK_HASH,
        task_position=position,
        ok=True,
        traces=[normalized_trace()],
        errors=[],
        raw_episode_digest=RAW_DIGEST,
    )


def write_run_output(directory: Path, *, traces: bytes = b"{}\n") -> Path:
    """Lay out a run directory exactly as the released engine leaves one.

    Including ``logs/latest``, which is a relative symlink to the attempt
    directory. It is here so that every assertion below is made in its
    presence: the engine writes it and Techtree has to be indifferent to it.
    """
    directory.mkdir(parents=True, exist_ok=True)
    config = directory / RESOLVED_CONFIG_PATH
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('{"push": false, "rich": null, "serve": null}\n')

    (directory / TRACES_FILENAME).write_bytes(traces)

    log = directory / EVAL_LOG_PATH
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("INFO results\n")
    (log.parent.parent / "latest").symlink_to(log.parent.name)
    return directory


# ---------------------------------------------------------------------------
# The upstream files
# ---------------------------------------------------------------------------


def test_the_three_upstream_files_are_the_ones_required(tmp_path: Path) -> None:
    relative = {
        path.relative_to(tmp_path).as_posix()
        for path in required_output_paths(tmp_path).values()
    }
    assert relative == {
        "configs/resolved/eval.json",
        "traces.jsonl",
        "logs/attempt_1/eval.log",
    }


def test_the_required_files_are_the_ones_a_run_directory_holds(tmp_path: Path) -> None:
    """The paths are the engine's, not a restatement of them.

    ``write_run_output`` builds the directory from the same constants, so this
    asserts against a directory laid out the way the engine lays one out and
    would catch a required path that names a file no run produces.
    """
    output = write_run_output(tmp_path / "run")

    for name, path in required_output_paths(output).items():
        assert path.is_file(), name
        assert not path.is_symlink(), name


def test_a_complete_run_directory_is_accepted(tmp_path: Path) -> None:
    output = write_run_output(tmp_path / "run")
    assert set(require_output_files(output)) == {"config", "traces", "eval_log"}


@pytest.mark.parametrize(
    "removed", [RESOLVED_CONFIG_PATH, TRACES_FILENAME, EVAL_LOG_PATH]
)
def test_a_missing_upstream_file_is_refused(tmp_path: Path, removed: str) -> None:
    output = write_run_output(tmp_path / "run")
    (output / removed).unlink()

    with pytest.raises(ValidationError) as caught:
        require_output_files(output)
    assert caught.value.code == "variant_output_incomplete"


def test_a_dry_run_directory_is_not_a_run_directory(tmp_path: Path) -> None:
    # A dry run writes the resolved configuration and nothing else, so treating
    # it as a run would report a truncated run where none was ever attempted.
    dry_run = tmp_path / "dry-run"
    config = dry_run / RESOLVED_CONFIG_PATH
    config.parent.mkdir(parents=True)
    config.write_text('{"push": false}\n')

    with pytest.raises(ValidationError):
        require_output_files(dry_run)


def test_an_empty_traces_file_means_no_episode_completed(tmp_path: Path) -> None:
    output = write_run_output(tmp_path / "run", traces=b"")

    with pytest.raises(ValidationError) as caught:
        require_output_files(output)
    assert caught.value.details["missing"] == ["episodes"]


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


def test_an_artifact_is_hashed_from_the_exact_bytes_on_disk(tmp_path: Path) -> None:
    path = tmp_path / "traces.jsonl"
    data = b'{"id":"episode-0"}\n'
    path.write_bytes(data)

    reference = artifact_for(path, "application/x-ndjson")

    assert reference.digest == sha256_digest_bytes(data)
    assert reference.size == len(data)
    assert reference.media_type == "application/x-ndjson"
    assert reference.relative_path is None


def test_an_empty_artifact_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "eval.log"
    path.write_bytes(b"")

    with pytest.raises(ValidationError):
        artifact_for(path, "text/plain")


# ---------------------------------------------------------------------------
# Normalized episodes
# ---------------------------------------------------------------------------


def test_every_record_of_a_complete_file_is_parsed(tmp_path: Path) -> None:
    path = tmp_path / "normalized-episodes.jsonl"
    records = [normalized_episode(0), normalized_episode(1)]
    path.write_text(
        "".join(record.model_dump_json() + "\n" for record in records),
        encoding="utf-8",
    )

    parsed = read_normalized_episodes(path)

    assert [episode.task_position for episode in parsed] == [0, 1]


def test_a_file_whose_last_record_is_truncated_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "normalized-episodes.jsonl"
    complete = normalized_episode(0).model_dump_json()
    path.write_text(f"{complete}\n{complete[:40]}", encoding="utf-8")

    with pytest.raises(ValidationError) as caught:
        read_normalized_episodes(path)
    assert caught.value.code == "variant_output_incomplete"


def test_a_malformed_record_is_refused_with_its_line_number(tmp_path: Path) -> None:
    path = tmp_path / "normalized-episodes.jsonl"
    complete = normalized_episode(0).model_dump_json()
    path.write_text(f'{complete}\n{{"episode_id": "no-fields"}}\n', encoding="utf-8")

    with pytest.raises(ValidationError) as caught:
        read_normalized_episodes(path)
    assert caught.value.details["line"] == 2


def test_an_empty_normalized_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "normalized-episodes.jsonl"
    path.write_bytes(b"")

    with pytest.raises(ValidationError):
        read_normalized_episodes(path)


# ---------------------------------------------------------------------------
# The normalized models themselves
# ---------------------------------------------------------------------------


def test_an_episode_whose_trace_scores_another_task_is_unrepresentable() -> None:
    with pytest.raises(ValueError, match="own task"):
        NormalizedEpisode(
            episode_id="episode-0",
            env_id="procedure-transfer-v1",
            task_hash=TASK_HASH,
            task_position=0,
            ok=True,
            traces=[normalized_trace(task_hash=f"sha256:{'9' * 64}")],
            errors=[],
            raw_episode_digest=RAW_DIGEST,
        )


def test_a_reward_carrying_a_non_finite_number_is_unrepresentable() -> None:
    with pytest.raises(ValueError, match="finite"):
        NormalizedReward(name="exact_match", score=float("nan"), weight=1.0, value=0.0)
