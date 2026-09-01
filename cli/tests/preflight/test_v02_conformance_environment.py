"""Model-free conformance for the exact environment proposed by WP0.2."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from engine_environment import check_engine_command

from techtree.canonical import sha256_digest_bytes

pytestmark = pytest.mark.preflight

CLI_ROOT = Path(__file__).parents[2]
MONOREPO_ROOT = CLI_ROOT.parent
ENVIRONMENT_ROOT = CLI_ROOT / "tests" / "conformance" / "prime_environment"
MANIFEST_PATH = MONOREPO_ROOT / "docs" / "v0.2" / "PRIME_CONFORMANCE_ENVIRONMENT.json"
INSPECTOR = (
    CLI_ROOT
    / "src"
    / "techtree"
    / "resources"
    / "engines"
    / "default"
    / "tools"
    / "inspect_taskset.py"
)
TASKSET_ID = "techtree-v02-conformance"
RUN_NAME = "run"


def scrubbed_environment(home: Path, executable_dir: Path) -> dict[str, str]:
    """Expose process basics but no credentials or unrelated environment state."""
    inherited_path = os.environ.get("PATH", "")
    return {
        "HOME": str(home),
        "PATH": f"{executable_dir}{os.pathsep}{inherited_path}",
        "PYTHONNOUSERSITE": "1",
    }


def uv_sync_environment(home: Path, venv: Path) -> dict[str, str]:
    """Give uv only the state needed to build the throwaway environment."""
    return {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", ""),
        "PYTHONNOUSERSITE": "1",
        "UV_CACHE_DIR": str(home / ".cache" / "uv"),
        "UV_PROJECT_ENVIRONMENT": str(venv),
    }


@pytest.fixture(scope="session")
def conformance_python(
    tmp_path_factory: pytest.TempPathFactory,
    built_wheel: Path,
) -> Path:
    """Install the exact locked dependencies and built wheel into one venv."""
    root = tmp_path_factory.mktemp("v02-prime-conformance")
    venv = root / ".venv"
    environment = uv_sync_environment(root / "home", venv)
    check_engine_command(
        "uv",
        "sync",
        "--project",
        ENVIRONMENT_ROOT,
        "--frozen",
        "--python",
        "3.12",
        "--no-install-project",
        "--no-build-package",
        "verifiers",
        env=environment,
    )
    python = venv / "bin" / "python"
    assert python.exists()
    check_engine_command(
        "uv",
        "pip",
        "install",
        "--python",
        python,
        "--no-deps",
        built_wheel,
        env=environment,
    )
    return python


@pytest.fixture(scope="session")
def manifest() -> dict[str, Any]:
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


@pytest.fixture(scope="session")
def inspected(
    conformance_python: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("v02-prime-inspection")
    output = root / "inspection.json"
    check_engine_command(
        conformance_python,
        INSPECTOR,
        "--taskset-id",
        TASKSET_ID,
        "--num-tasks",
        "4",
        "--output",
        output,
        env=scrubbed_environment(root / "home", conformance_python.parent),
    )
    document = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


@pytest.fixture(scope="session")
def validation_summary(
    conformance_python: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("v02-prime-validation")
    validate = conformance_python.parent / "validate"
    check_engine_command(
        validate,
        TASKSET_ID,
        "--num-tasks",
        "4",
        "--runtime.type",
        "subprocess",
        "--output-dir",
        root / "output",
        "--run.name",
        RUN_NAME,
        "--rich",
        "false",
        env=scrubbed_environment(root / "home", conformance_python.parent),
    )
    document = json.loads(
        (root / "output" / RUN_NAME / "summary.json").read_text(encoding="utf-8")
    )
    assert isinstance(document, dict)
    return document


@pytest.fixture(scope="session")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the unpublished artifact deterministically into a temporary path."""
    root = tmp_path_factory.mktemp("v02-prime-wheel")
    environment = {
        "HOME": str(root / "home"),
        "PATH": os.environ.get("PATH", ""),
        "PYTHONNOUSERSITE": "1",
    }
    environment["SOURCE_DATE_EPOCH"] = "1704067200"
    check_engine_command(
        "uv",
        "build",
        "--project",
        ENVIRONMENT_ROOT,
        "--wheel",
        "--out-dir",
        root,
        env=environment,
    )
    wheel = root / "techtree_v02_conformance-0.1.0-py3-none-any.whl"
    assert wheel.is_file()
    return wheel


def test_the_locked_stable_wheel_is_the_running_engine(
    conformance_python: Path,
) -> None:
    version = check_engine_command(
        conformance_python,
        "-c",
        "from importlib.metadata import version; print(version('verifiers'))",
    ).strip()
    assert version == "0.3.1"

    installed_package = Path(
        check_engine_command(
            conformance_python,
            "-c",
            "import techtree_v02_conformance as p; print(p.__file__)",
        ).strip()
    ).resolve()
    assert ENVIRONMENT_ROOT.resolve() not in installed_package.parents
    assert "site-packages" in installed_package.parts


def test_package_exports_the_fixed_taskset_and_subject_environment(
    conformance_python: Path,
) -> None:
    probe = (
        "import json;"
        "from verifiers.v1.utils.loaders import "
        "taskset_class,environment_class,env_config_type;"
        f"i={TASKSET_ID!r};"
        "print(json.dumps({"
        "'taskset':taskset_class(i).__name__,"
        "'env':environment_class(i).__name__,"
        "'config':env_config_type(i).__name__,"
        "'seats':sorted(env_config_type(i).model_fields)}))"
    )
    resolved = json.loads(check_engine_command(conformance_python, "-c", probe))

    assert resolved["taskset"] == "ConformanceTaskset"
    assert resolved["env"] == "SubjectEnv"
    assert resolved["config"] == "SubjectEnvConfig"
    assert "subject" in resolved["seats"]
    assert "agent" not in resolved["seats"]


def test_pinned_environment_runs_subject_once_and_scores_decorated_reward(
    conformance_python: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Probe both executable hooks in the installed, pinned environment."""
    root = tmp_path_factory.mktemp("v02-prime-hook-probe")
    probe = """
import asyncio
import json

import verifiers.v1 as vf
from verifiers.v1.graph import MessageNode
from verifiers.v1.trace import AgentInfo, Trace, TraceTask
from verifiers.v1.types import AssistantMessage

from techtree_v02_conformance.env import SubjectEnv
from techtree_v02_conformance.taskset import ConformanceData, ConformanceTask


class RecordingSubject:
    def __init__(self):
        self.calls = []

    async def run(self, task):
        self.calls.append(task)


class RecordingAgents:
    def __init__(self, subject):
        self.subject = subject


task = ConformanceTask(ConformanceData(
    idx=0, name="amber-17", prompt="x", answer="AMBER-17"
))


def trace_for(reply):
    return Trace(
        task=TraceTask(type=type(task).__name__, data=task.data),
        agent=AgentInfo(config=vf.AgentConfig()),
        nodes=[
            MessageNode(
                message=AssistantMessage(content=reply),
                sampled=True,
            )
        ],
    )


async def main():
    subject = RecordingSubject()
    task_marker = object()
    await object.__new__(SubjectEnv).run(task_marker, RecordingAgents(subject))

    replies = {
        "correct": "AMBER-17",
        "incorrect": "amber-17",
        "whitespace": "\\n AMBER-17 \\t",
    }
    scores = {}
    for label, reply in replies.items():
        trace = trace_for(reply)
        await task.score(trace)
        scores[label] = trace.rewards["exact_match"].score
    print(json.dumps({
        "calls": len(subject.calls),
        "same_task": subject.calls[0] is task_marker,
        "scores": scores,
    }, sort_keys=True))


asyncio.run(main())
"""
    result = check_engine_command(
        conformance_python,
        "-c",
        probe,
        env=scrubbed_environment(root / "home", conformance_python.parent),
    )
    assert json.loads(result) == {
        "calls": 1,
        "same_task": True,
        "scores": {"correct": 1.0, "incorrect": 0.0, "whitespace": 1.0},
    }


def test_real_task_membership_matches_the_committed_manifest(
    inspected: dict[str, Any], manifest: dict[str, Any]
) -> None:
    expected = manifest["taskset"]
    assert inspected["taskset_id"] == expected["id"]
    assert inspected["taskset_class"] == expected["class"]
    assert inspected["task_count"] == expected["task_count"]
    assert [
        {
            "position": task["position"],
            "name": task["name"],
            "task_hash": f"sha256:{task['task_hash']}",
        }
        for task in inspected["tasks"]
    ] == expected["tasks"]


def test_real_model_free_validation_matches_the_committed_result(
    validation_summary: dict[str, Any], manifest: dict[str, Any]
) -> None:
    expected = manifest["local_conformance"]["summary"]
    outcomes = validation_summary["outcomes"]

    assert validation_summary["mode"] == "all"
    assert validation_summary["total"] == expected["total"]
    assert validation_summary["recorded"] == expected["recorded"]
    assert validation_summary["valid_rate"] == expected["valid_rate"]
    for outcome in ("valid", "invalid", "error", "timeout", "missing"):
        assert outcomes[outcome] == expected[outcome]
    assert validation_summary["checks"]["gold"]["valid"] == expected["gold_valid"]
    assert validation_summary["checks"]["setup"]["valid"] == expected["setup_valid"]


def test_the_unpublished_wheel_rebuilds_to_the_committed_artifact(
    built_wheel: Path, manifest: dict[str, Any]
) -> None:
    expected = manifest["package"]["wheel"]
    assert built_wheel.name == expected["filename"]
    assert built_wheel.stat().st_size == expected["size"]
    assert sha256_digest_bytes(built_wheel.read_bytes()) == expected["sha256"]
