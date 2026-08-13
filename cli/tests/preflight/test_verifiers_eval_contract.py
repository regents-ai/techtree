"""WP6a — the pinned Verifiers ``eval`` contract, proven against the pin.

Every assertion here records observed behaviour of
`PrimeIntellect-ai/verifiers@7e1c47d24d055aae587ee8259f77a3e8e193513a`. When
the pin is bumped this module is the gate: rerun it, and update
``docs/verifiers-eval.md`` with whatever moved. The five deviations from the
specification's assumptions are written up there, at the top, under CRITICAL.

## No model is called

WP6a is forbidden from making real model calls. Two things make that true
rather than merely intended:

* every configuration check is a ``--dry-run``, which upstream resolves and
  validates without constructing an environment or opening a client; and
* the one full ``eval`` run uses ``tests/preflight/fixture_subject_env``, whose
  harness accepts the interception endpoint and returns without opening it.

Where a credential appears below it is the literal string
``sk-preflight-secret-value``, set purely so the suite can prove it reaches no
output file.

## What is being proven

The last section compiles a configuration with Techtree's own compiler and
dry-runs it against the pinned engine, so the shape this repository emits is
checked against the real thing rather than against a description of it.

## Running it

    make verifiers-preflight
"""

from __future__ import annotations

import json
import os
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from engine_environment import (
    check_engine_command,
    install_fixture_package,
    run_engine_command,
)

from techtree.constants import SKILL_SCHEMA_VERSION
from techtree.manifests.builder import (
    build_baseline_manifest,
    build_candidate_manifest,
    skill_content_digest,
)
from techtree.models.campaign import CampaignSpec
from techtree.models.skill import SkillArtifact, SkillFile
from techtree.verifiers.compiler import compile_variant_config, write_variant_config
from techtree.verifiers.config import config_to_toml_bytes
from techtree.verifiers.models import RunPaths, VariantName

pytestmark = pytest.mark.preflight

PREFLIGHT_DIR = Path(__file__).parent
FIXTURE_DIR = PREFLIGHT_DIR / "fixture_subject_env"
TASKSET_ID = "techtree-preflight-subject"
DISTRIBUTION = "techtree-preflight-subject"

SECRET = "sk-preflight-secret-value"
"""Never a real credential. The real PRIME_API_KEY is never read by this suite."""

STAGGER_ENV = "TECHTREE_PREFLIGHT_STAGGER"
TASK_COUNT = 4
PINNED_TIME = datetime(2026, 1, 1, tzinfo=UTC)

RUN_OUTPUT_FILES = {"config.toml", "traces.jsonl", "eval.log"}
"""Spec 6.3 — what a completed run leaves behind, and nothing else."""


# ---------------------------------------------------------------------------
# The environment and the configurations under test
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def eval_engine(pinned_engine_python: Path) -> Path:
    """The shared pinned interpreter with the named-subject fixture installed."""
    install_fixture_package(pinned_engine_python, DISTRIBUTION, FIXTURE_DIR)
    return pinned_engine_python


@pytest.fixture(scope="session")
def eval_cli(eval_engine: Path) -> Path:
    """The ``eval`` console script the engine environment exposes."""
    script = eval_engine.parent / "eval"
    assert script.exists(), f"no `eval` console script next to {eval_engine}"
    return script


def scrubbed_environment(**extra: str) -> dict[str, str]:
    """A child environment with a decoy credential and nothing borrowed."""
    return {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PRIME_API_KEY": SECRET,
        **extra,
    }


def techtree_shaped_config(
    output_dir: Path,
    *,
    skills: list[str] | None = None,
    harness_id: str = "hermes-agent",
    restricted: bool = True,
    **overrides: Any,
) -> dict[str, Any]:
    """A configuration shaped exactly like the one Techtree compiles."""
    document: dict[str, Any] = {
        "model": "stub/preflight-model",
        "num_tasks": 2,
        "num_rollouts": 1,
        "shuffle": False,
        "max_concurrent": 1,
        "rich": False,
        "push": False,
        "output_dir": str(output_dir),
        "client": {"type": "eval", "api_key_var": "PRIME_API_KEY"},
        "sampling": {"temperature": 0.0, "max_tokens": 64},
        "env": {
            "max_concurrent_agents": 1,
            "taskset": {"id": TASKSET_ID},
            "subject": {
                "harness": {
                    "id": harness_id,
                    "version": "0.19.0",
                    "use_bundled_skill": False,
                    "skills": skills or [],
                },
                "runtime": {
                    "type": "docker",
                    "image": f"python:3.12-slim@sha256:{'a' * 64}",
                    "allow": [] if restricted else ["*"],
                    "block": [],
                    "cpu": 2.0,
                    "memory": 4.0,
                },
            },
        },
    }
    document.update(overrides)
    return document


def write_toml(path: Path, document: dict[str, Any]) -> Path:
    """Write one configuration for the engine to read."""
    import tomli_w

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(document))
    return path


def dry_run(
    eval_cli: Path, config: Path, output_dir: Path, **environment: str
) -> tuple[int, Path, str]:
    """Dry-run one configuration and return its exit code, output dir and stderr."""
    result = run_engine_command(
        eval_cli,
        "@",
        config,
        "--dry-run",
        "--output-dir",
        output_dir,
        env=scrubbed_environment(**environment),
    )
    return result.returncode, output_dir, result.stderr


@pytest.fixture(scope="session")
def resolved_config(
    eval_cli: Path, tmp_path_factory: pytest.TempPathFactory
) -> dict[str, Any]:
    """The configuration the engine writes back for a Techtree-shaped input."""
    root = tmp_path_factory.mktemp("eval-dry-run")
    code, output, stderr = dry_run(
        eval_cli,
        write_toml(root / "input.toml", techtree_shaped_config(root / "run")),
        root / "dry-run",
    )
    assert code == 0, stderr
    with (output / "config.toml").open("rb") as handle:
        document: dict[str, Any] = tomllib.load(handle)
    return document


@pytest.fixture(scope="session")
def finished_run(
    eval_cli: Path, tmp_path_factory: pytest.TempPathFactory
) -> dict[str, Any]:
    """One complete model-free evaluation, with its files and captured stdio.

    The subject seat runs the fixture's own harness rather than Hermes: this
    suite proves the *pipeline*, and installing Hermes into a container would
    make every assertion here depend on Docker and a network.
    """
    root = tmp_path_factory.mktemp("eval-run")
    output = root / "run"
    document = techtree_shaped_config(output, harness_id=TASKSET_ID)
    document["num_tasks"] = TASK_COUNT
    document["max_concurrent"] = TASK_COUNT
    del document["env"]["subject"]["harness"]["version"]
    del document["env"]["subject"]["harness"]["use_bundled_skill"]
    document["env"]["subject"]["runtime"] = {"type": "subprocess"}

    result = run_engine_command(
        eval_cli,
        "@",
        write_toml(root / "input.toml", document),
        env=scrubbed_environment(**{STAGGER_ENV: "0.4"}),
    )
    assert result.returncode == 0, result.stderr

    episodes = [
        json.loads(line)
        for line in (output / "traces.jsonl").read_text().splitlines()
        if line.strip()
    ]
    return {
        "dir": output,
        "episodes": episodes,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


# ---------------------------------------------------------------------------
# E0 / 6.5 — the named subject role
# ---------------------------------------------------------------------------


def test_one_package_can_export_a_taskset_an_env_and_a_harness(
    eval_engine: Path,
) -> None:
    # Spec 6.5 relies on Verifiers filtering exports by base type, which is what
    # lets one reference package carry both the taskset and its environment.
    source = (
        "import json;"
        "from verifiers.v1.utils.loaders import ("
        " default_harness_id, env_config_type, environment_class, taskset_class);"
        f"i={TASKSET_ID!r};"
        "print(json.dumps({"
        "'taskset': taskset_class(i).__name__,"
        "'env': environment_class(i).__name__,"
        "'config': env_config_type(i).__name__,"
        "'seats': sorted(env_config_type(i).model_fields),"
        "'harness': default_harness_id(i)}))"
    )
    resolved = json.loads(check_engine_command(eval_engine, "-c", source))

    assert resolved["taskset"] == "SubjectTaskset"
    assert resolved["env"] == "SubjectEnv"
    assert resolved["config"] == "SubjectEnvConfig"
    assert "subject" in resolved["seats"]
    assert "agent" not in resolved["seats"]


def test_the_environment_resolves_from_the_taskset_package(
    resolved_config: dict[str, Any],
) -> None:
    # env.id stays empty; the environment comes from the taskset's own package.
    assert resolved_config["env"]["id"] == ""
    assert "subject" in resolved_config["env"]
    assert "agent" not in resolved_config["env"]


def test_every_trace_records_the_subject_role(finished_run: dict[str, Any]) -> None:
    names = {
        trace["agent"]["name"]
        for episode in finished_run["episodes"]
        for trace in episode["traces"]
    }
    assert names == {"subject"}


def test_a_subject_seat_is_refused_by_an_environment_without_one(
    eval_cli: Path, tmp_path: Path
) -> None:
    # E0. This is the exact failure the shipped reference package produces
    # today, and the reason the named-subject Env is a STOP-AND-NOTE.
    document = techtree_shaped_config(tmp_path / "run")
    document["env"]["taskset"]["id"] = "techtree-preflight-taskset"
    code, _, stderr = dry_run(
        eval_cli,
        write_toml(tmp_path / "input.toml", document),
        tmp_path / "dry-run",
    )

    assert code == 1
    assert "env.subject" in stderr
    assert "Extra inputs are not permitted" in stderr


# ---------------------------------------------------------------------------
# E1 / 6.3 — the platform upload
# ---------------------------------------------------------------------------


def test_the_upload_defaults_to_on_upstream(eval_cli: Path, tmp_path: Path) -> None:
    document = techtree_shaped_config(tmp_path / "run")
    del document["push"]
    code, output, stderr = dry_run(
        eval_cli,
        write_toml(tmp_path / "input.toml", document),
        tmp_path / "dry-run",
    )

    assert code == 0, stderr
    with (output / "config.toml").open("rb") as handle:
        assert tomllib.load(handle)["push"] is True


def test_the_resolved_configuration_records_the_upload_setting(
    resolved_config: dict[str, Any],
) -> None:
    assert resolved_config["push"] is False


def test_the_command_line_flag_overrides_an_upload_in_the_file(
    eval_cli: Path, tmp_path: Path
) -> None:
    document = techtree_shaped_config(tmp_path / "run")
    document["push"] = True
    result = run_engine_command(
        eval_cli,
        "@",
        write_toml(tmp_path / "input.toml", document),
        "--dry-run",
        "--no-push",
        "--output-dir",
        tmp_path / "dry-run",
        env=scrubbed_environment(),
    )

    assert result.returncode == 0, result.stderr
    with (tmp_path / "dry-run" / "config.toml").open("rb") as handle:
        assert tomllib.load(handle)["push"] is False


def _upload_probe(directory: Path) -> Path:
    """Write a ``sitecustomize`` that records whether the uploader was reached.

    The pinned CLI imports ``verifiers.v1.utils.platform`` *inside* the branch
    that uploads, in both the plain and the dashboard code paths, and nothing
    else in the package imports it. So the module's presence in the child's own
    ``sys.modules`` when it exits is a direct observation of whether the upload
    path ran — stronger than reading the source, and it cannot be satisfied by
    a configuration that merely says the right thing.
    """
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "sitecustomize.py").write_text(
        "import atexit, os, sys\n"
        "def _record():\n"
        "    reached = 'verifiers.v1.utils.platform' in sys.modules\n"
        "    with open(os.environ['TECHTREE_UPLOAD_PROBE'], 'w') as handle:\n"
        "        handle.write('reached' if reached else 'not-reached')\n"
        "atexit.register(_record)\n",
        encoding="utf-8",
    )
    return directory


def _run_with_upload_probe(
    eval_cli: Path, root: Path, *, push: bool, credential: bool
) -> str:
    """Run one complete evaluation under the probe and return what it saw."""
    output = root / "run"
    document = techtree_shaped_config(output, harness_id=TASKSET_ID)
    document["push"] = push
    del document["env"]["subject"]["harness"]["version"]
    del document["env"]["subject"]["harness"]["use_bundled_skill"]
    document["env"]["subject"]["runtime"] = {"type": "subprocess"}

    probe = root / "probe.txt"
    environment = scrubbed_environment(
        PYTHONPATH=str(_upload_probe(root / "probe-path")),
        TECHTREE_UPLOAD_PROBE=str(probe),
    )
    if not credential:
        # No key anywhere, including the Prime config file a real HOME may
        # hold: the uploader must have nothing to authenticate with, so this
        # test can prove the probe fires without any request being made.
        environment["PRIME_API_KEY"] = ""
        environment["HOME"] = str(root / "empty-home")
        Path(environment["HOME"]).mkdir(parents=True, exist_ok=True)

    result = run_engine_command(
        eval_cli, "@", write_toml(root / "input.toml", document), env=environment
    )
    assert result.returncode == 0, result.stderr
    return probe.read_text(encoding="utf-8")


def test_the_upload_path_is_never_reached_when_push_is_off(
    eval_cli: Path, tmp_path: Path
) -> None:
    """Decisions 0007 R9 item 6, and the release ratification behind it.

    Techtree's compiled configuration disables the upload and its resolved
    configuration is checked to confirm it. This is the third statement, and
    the only one about behaviour: a complete run with ``push = false`` never
    loads the uploader at all. A future pin that ignored the setting, or moved
    the upload out of that branch, fails here.
    """
    assert (
        _run_with_upload_probe(eval_cli, tmp_path / "off", push=False, credential=True)
        == "not-reached"
    )


def test_the_upload_probe_sees_the_path_when_push_is_on(
    eval_cli: Path, tmp_path: Path
) -> None:
    """The control. A probe that can never fire would prove nothing above.

    Run with the upload *on* and with no credential resolvable anywhere, which
    upstream handles by logging and returning before it builds a request. The
    uploader is therefore loaded and observed, and nothing is sent.
    """
    assert (
        _run_with_upload_probe(eval_cli, tmp_path / "on", push=True, credential=False)
        == "reached"
    )


# ---------------------------------------------------------------------------
# E2 / 6.3 — what a dry run writes, and what a real run writes
# ---------------------------------------------------------------------------


def test_a_dry_run_writes_only_the_resolved_configuration(
    eval_cli: Path, tmp_path: Path
) -> None:
    code, output, stderr = dry_run(
        eval_cli,
        write_toml(tmp_path / "input.toml", techtree_shaped_config(tmp_path / "run")),
        tmp_path / "dry-run",
    )

    assert code == 0, stderr
    assert {path.name for path in output.iterdir()} == {"config.toml"}


def test_a_real_run_writes_exactly_the_three_expected_files(
    finished_run: dict[str, Any],
) -> None:
    output: Path = finished_run["dir"]
    assert {path.name for path in output.iterdir()} == RUN_OUTPUT_FILES


def test_the_resolved_configuration_is_a_fixed_point(
    eval_cli: Path, tmp_path: Path, resolved_config: dict[str, Any]
) -> None:
    # A resolved config is re-runnable through `@ config.toml`, so resolving it
    # again must not keep changing it.
    again = dict(resolved_config)
    again["output_dir"] = str(tmp_path / "run")
    code, output, stderr = dry_run(
        eval_cli,
        write_toml(tmp_path / "resolved.toml", again),
        tmp_path / "dry-run",
    )

    assert code == 0, stderr
    with (output / "config.toml").open("rb") as handle:
        document = tomllib.load(handle)
    # --output-dir on argv overrides the file, so the one key the flag owns is
    # normalized away before the documents are compared.
    assert document.pop("output_dir") == str(tmp_path / "dry-run")
    again.pop("output_dir")
    assert document == again


# ---------------------------------------------------------------------------
# E3 / 6.7 — what a dry run does and does not validate
# ---------------------------------------------------------------------------


def test_an_unknown_key_is_refused(eval_cli: Path, tmp_path: Path) -> None:
    code, _, stderr = dry_run(
        eval_cli,
        write_toml(
            tmp_path / "input.toml",
            techtree_shaped_config(tmp_path / "run", not_a_key=1),
        ),
        tmp_path / "dry-run",
    )

    assert code == 1
    assert "not-a-key" in stderr or "not_a_key" in stderr


def test_an_unresolvable_taskset_is_refused(eval_cli: Path, tmp_path: Path) -> None:
    document = techtree_shaped_config(tmp_path / "run")
    document["env"]["taskset"]["id"] = "no-such-taskset-anywhere"
    code, _, stderr = dry_run(
        eval_cli,
        write_toml(tmp_path / "input.toml", document),
        tmp_path / "dry-run",
    )

    assert code == 1
    assert "not found" in stderr


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        ("bundled skills", lambda h, _: h.update({"use_bundled_skill": True})),
        ("disabled tools", lambda h, _: h.update({"disabled_tools": ["bash"]})),
        ("absent skill path", lambda h, p: h.update({"skills": [str(p / "gone")]})),
    ],
)
def test_the_dry_run_accepts_settings_techtree_must_reject_itself(
    eval_cli: Path, tmp_path: Path, label: str, mutate: Any
) -> None:
    # E3. Each of these fails mid-run or never, so the compiler's allow-list is
    # the only place they can be caught before Docker is provisioned.
    document = techtree_shaped_config(tmp_path / "run")
    mutate(document["env"]["subject"]["harness"], tmp_path)

    code, _, stderr = dry_run(
        eval_cli,
        write_toml(tmp_path / "input.toml", document),
        tmp_path / "dry-run",
    )

    assert code == 0, f"{label}: {stderr}"


def test_a_hermes_and_docker_configuration_resolves_without_docker(
    resolved_config: dict[str, Any],
) -> None:
    subject = resolved_config["env"]["subject"]
    assert subject["harness"]["id"] == "hermes-agent"
    assert subject["harness"]["version"] == "0.19.0"
    assert subject["harness"]["use_bundled_skill"] is False
    assert "disabled_tools" not in subject["harness"]
    assert subject["runtime"]["type"] == "docker"


def test_an_empty_allow_list_resolves_to_framework_only_egress(
    resolved_config: dict[str, Any],
) -> None:
    # Upstream's default is allow = ["*"]; an empty list is normalized to a
    # wildcard block, which is what a restricted Campaign runtime means.
    runtime = resolved_config["env"]["subject"]["runtime"]
    assert runtime["allow"] == []
    assert runtime["block"] == ["*"]


def test_an_omitted_base_url_is_resolved_by_the_pinned_client(
    resolved_config: dict[str, Any],
) -> None:
    assert resolved_config["client"]["api_key_var"] == "PRIME_API_KEY"
    assert resolved_config["client"]["base_url"].startswith("https://")


# ---------------------------------------------------------------------------
# E4 / 6.11 — traces.jsonl is append-only and ordered by completion
# ---------------------------------------------------------------------------


def test_every_line_is_one_complete_episode(finished_run: dict[str, Any]) -> None:
    episodes = finished_run["episodes"]
    assert len(episodes) == TASK_COUNT
    for episode in episodes:
        assert set(episode) >= {"id", "env", "ok", "errors", "traces"}
        assert len(episode["traces"]) == 1
    assert (finished_run["dir"] / "traces.jsonl").read_bytes().endswith(b"\n")


def test_line_order_is_completion_order_and_not_task_order(
    finished_run: dict[str, Any],
) -> None:
    # The fixture harness delays each task in reverse index order, so a reader
    # that trusted line position would pair every result with the wrong task.
    positions = [
        episode["traces"][0]["task"]["data"]["idx"]
        for episode in finished_run["episodes"]
    ]
    assert positions == sorted(positions, reverse=True)
    assert positions != sorted(positions)


def test_episodes_are_appended_one_whole_record_at_a_time(
    eval_cli: Path, tmp_path: Path
) -> None:
    output = tmp_path / "run"
    document = techtree_shaped_config(output, harness_id=TASKSET_ID)
    document["num_tasks"] = TASK_COUNT
    document["max_concurrent"] = 1
    del document["env"]["subject"]["harness"]["version"]
    del document["env"]["subject"]["harness"]["use_bundled_skill"]
    document["env"]["subject"]["runtime"] = {"type": "subprocess"}
    config = write_toml(tmp_path / "input.toml", document)

    import subprocess

    child = subprocess.Popen(
        [str(eval_cli), "@", str(config)],
        env=scrubbed_environment(**{STAGGER_ENV: "0.5"}),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    traces = output / "traces.jsonl"
    sizes: list[int] = []
    try:
        while child.poll() is None:
            sizes.append(traces.stat().st_size if traces.exists() else 0)
            time.sleep(0.2)
    finally:
        child.wait(timeout=120)

    assert sizes == sorted(sizes), "traces.jsonl shrank or was rewritten mid-run"
    assert max(sizes) > 0, "the file never grew while the child was running"
    assert len(traces.read_text().splitlines()) == TASK_COUNT


# ---------------------------------------------------------------------------
# 6.14 — what a trace records about the run that produced it
# ---------------------------------------------------------------------------


def test_each_trace_records_the_pinned_verifiers_commit(
    finished_run: dict[str, Any],
) -> None:
    from engine_environment import VERIFIERS_PIN

    commits = {
        trace["verifiers"]["commit"]
        for episode in finished_run["episodes"]
        for trace in episode["traces"]
    }
    assert commits == {VERIFIERS_PIN}


def test_each_trace_records_the_configuration_it_ran_under(
    finished_run: dict[str, Any],
) -> None:
    config = finished_run["episodes"][0]["traces"][0]["agent"]["config"]
    assert config["model"] == "stub/preflight-model"
    assert config["harness"]["id"] == TASKSET_ID
    assert config["client"]["api_key_var"] == "PRIME_API_KEY"


def test_each_trace_records_the_sampling_it_was_run_under(
    finished_run: dict[str, Any],
) -> None:
    """Decisions 0007 R9 item 1: effective sampling travels with the rollout.

    The engine merges the run's sampling onto each agent's own overrides and
    writes the *resolved* settings into the trace, so a consumer holding one
    normalized episode can compare two variants' effective sampling without
    opening the configuration file beside it. Every trace of the run carries
    them, and they are the ones the configuration asked for.
    """
    sampling = [
        trace["agent"]["config"]["sampling"]
        for episode in finished_run["episodes"]
        for trace in episode["traces"]
    ]
    assert sampling, "the run produced no traces to read sampling from"
    for resolved in sampling:
        assert resolved["temperature"] == 0.0
        assert resolved["max_tokens"] == 64


def test_each_trace_counts_the_model_calls_it_made(
    finished_run: dict[str, Any],
) -> None:
    """Decisions 0007 R9 item 7: the call count is per trace, always present.

    The fixture harness answers without opening the interception endpoint, so
    the honest count here is zero. That is the point: ``calls`` is a list every
    trace carries, so a variant always knows how many calls it made even when
    no provider reported any tokens.
    """
    for episode in finished_run["episodes"]:
        for trace in episode["traces"]:
            assert isinstance(trace["calls"], list)


def test_each_trace_carries_its_own_task_hash_to_pair_on(
    finished_run: dict[str, Any],
) -> None:
    hashes = [
        episode["traces"][0]["task"]["hash"] for episode in finished_run["episodes"]
    ]
    assert len(set(hashes)) == TASK_COUNT
    assert all(len(value) == 64 for value in hashes)


# ---------------------------------------------------------------------------
# 6.9 — no credential reaches any artifact
# ---------------------------------------------------------------------------


def test_no_credential_value_reaches_a_dry_runs_output(
    eval_cli: Path, tmp_path: Path
) -> None:
    code, output, stderr = dry_run(
        eval_cli,
        write_toml(tmp_path / "input.toml", techtree_shaped_config(tmp_path / "run")),
        tmp_path / "dry-run",
    )

    assert code == 0, stderr
    assert SECRET not in (output / "config.toml").read_text()


def test_no_credential_value_reaches_a_real_runs_output(
    finished_run: dict[str, Any],
) -> None:
    written = "".join(
        path.read_text(errors="replace") for path in finished_run["dir"].iterdir()
    )
    assert SECRET not in written
    assert SECRET not in finished_run["stdout"]
    assert SECRET not in finished_run["stderr"]
    # The variable's name travels; its value does not.
    assert "PRIME_API_KEY" in (finished_run["dir"] / "config.toml").read_text()


def test_standard_output_is_a_full_transcript_dump(
    finished_run: dict[str, Any],
) -> None:
    # Spec 6.10 forbids streaming raw trace JSON to the host agent. This is why:
    # with rich disabled, every trace is printed to stdout as indented JSON.
    assert '"verifiers"' in finished_run["stdout"]
    assert (
        len(finished_run["stdout"])
        > len((finished_run["dir"] / "traces.jsonl").read_text()) / 2
    )


# ---------------------------------------------------------------------------
# Techtree's own compiler, against the real engine
# ---------------------------------------------------------------------------


def preflight_campaign() -> CampaignSpec:
    """The synthetic Campaign, pointed at this suite's fixture taskset."""
    import sys

    sys.path.insert(0, str(PREFLIGHT_DIR.parent))
    from fixtures.drafts.support import synthetic_graph

    campaign = synthetic_graph().campaign
    reference = campaign.taskset.ref.model_copy(update={"id": TASKSET_ID})
    taskset = campaign.taskset.model_copy(update={"ref": reference})
    return campaign.model_copy(update={"taskset": taskset})


def preflight_skill() -> SkillArtifact:
    files = [
        SkillFile(
            path="SKILL.md",
            media_type="text/markdown",
            size=64,
            digest=f"sha256:{'a' * 64}",
        )
    ]
    return SkillArtifact(
        schema_version=SKILL_SCHEMA_VERSION,
        name="preflight-candidate",
        root_digest=skill_content_digest(files),
        archive_digest=f"sha256:{'c' * 64}",
        files=files,
        source_kind="manual",
        parent_skill_digest=None,
    )


@pytest.mark.parametrize("variant", [VariantName.BASELINE, VariantName.CANDIDATE])
def test_a_techtree_compiled_configuration_is_accepted_by_the_pinned_engine(
    eval_cli: Path, tmp_path: Path, variant: VariantName
) -> None:
    from techtree.canonical import digest_object

    campaign = preflight_campaign()
    digest = digest_object(campaign)
    if variant is VariantName.BASELINE:
        manifest = build_baseline_manifest(
            campaign=campaign,
            campaign_digest=digest,
            public_context=None,
            created_at=PINNED_TIME,
        )
    else:
        manifest = build_candidate_manifest(
            campaign=campaign,
            campaign_digest=digest,
            skill=preflight_skill(),
            public_context=None,
            created_at=PINNED_TIME,
        )

    run_paths = RunPaths(root=tmp_path / "runs" / "run_preflight")
    config = compile_variant_config(
        campaign=campaign,
        experiment=manifest,
        run_paths=run_paths,
        variant=variant,
        variant_max_concurrent=1,
    )
    input_path = run_paths.variant_input_config(variant)
    write_variant_config(config, input_path)

    code, output, stderr = dry_run(
        eval_cli, input_path, run_paths.variant_dry_run_dir(variant)
    )

    assert code == 0, stderr
    with (output / "config.toml").open("rb") as handle:
        resolved = tomllib.load(handle)
    assert resolved["push"] is False
    assert resolved["rich"] is False
    assert resolved["shuffle"] is False
    assert resolved["num_rollouts"] == 1
    # --output-dir on argv points a dry run away from the real run directory.
    assert resolved["output_dir"] == str(run_paths.variant_dry_run_dir(variant))
    assert config.output_dir == str(run_paths.variant_output_dir(variant))
    assert "subject" in resolved["env"]
    assert resolved["env"]["subject"]["harness"]["use_bundled_skill"] is False
    expected_skills = 0 if variant is VariantName.BASELINE else 1
    assert len(resolved["env"]["subject"]["harness"]["skills"]) == expected_skills
    # The bytes the engine read are the bytes the compiler produced.
    assert input_path.read_bytes() == config_to_toml_bytes(config)
