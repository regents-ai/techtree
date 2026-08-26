"""PI0 — the pinned Verifiers contract, proven against the pinned commit.

Every assertion here records observed behaviour of
`PrimeIntellect-ai/verifiers@b2e4e8157783b2c0dffc7821044c87f29f1c3ccf`.
When the pin is bumped this module is the gate: rerun it, and write up
whatever moved.

Findings for the current pin are in `docs/verifiers-pin-0.3.1.md`; the
superseded `0.3.1.dev21` record is `docs/verifiers-pin.md`.

## Running it

    make verifiers-preflight

The suite is marked `preflight` and is excluded from the default test run: it
builds a throwaway virtualenv and reaches github.com and PyPI.

By default it creates its own temporary venv (uv, Python 3.12) per pytest
session and installs the pin plus the fixture taskset into it. To reuse an
already-built engine venv instead, point this at its interpreter:

    TECHTREE_PREFLIGHT_ENGINE_PYTHON=/path/to/engine/.venv/bin/python \
        uv run pytest -m preflight tests/preflight

The supplied interpreter must already have the pinned commit installed, and the
fixture taskset is installed into it on first use. The pin is verified from the
distribution's recorded VCS metadata either way, so a mismatched venv fails
loudly rather than silently proving the wrong thing.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from engine_environment import VERIFIERS_PIN, install_fixture_package

pytestmark = pytest.mark.preflight

TASKSET_ID = "techtree-preflight-taskset"

PREFLIGHT_DIR = Path(__file__).parent
FIXTURE_DIR = PREFLIGHT_DIR / "fixture_taskset"
PROBE = PREFLIGHT_DIR / "verifiers_probe.py"

EXPECTED_OUTPUT_FILES = {
    "configs/resolved/validate.json",
    "logs/validate.log",
    "results.jsonl",
    "summary.json",
}
"""Spec 2.1 claim 7 — exactly these, nothing else.

Still four files, but no longer four flat names: v0.3.1 moved the resolved
configuration into ``configs/resolved/`` (as JSON, not TOML) and the log into
``logs/``. See docs/verifiers-pin-0.3.1.md, deviation D1.
"""

RUN_DIR = "run"
"""The run directory Techtree names explicitly.

``--output-dir`` no longer names the directory a run writes into: it names the
directory runs are *grouped* under, and each run lands in
``<output-dir>/<run.dir>``. Left unset, ``run.dir`` auto-generates with a random
suffix, so the engine must always pass ``--run.name``. Deviation D2.
"""

OUTCOME_KEYS = {"valid", "invalid", "error", "timeout", "missing"}
RAW_HASH = re.compile(r"^[0-9a-f]{64}$")


def _run(*argv: str | Path, cwd: Path | None = None, env: dict | None = None):
    result = subprocess.run(
        [str(arg) for arg in argv],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result


def _check(*argv: str | Path, cwd: Path | None = None, env: dict | None = None) -> str:
    result = _run(*argv, cwd=cwd, env=env)
    if result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(str(a) for a in argv)}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )
    return result.stdout


@pytest.fixture(scope="session")
def engine_python(pinned_engine_python: Path) -> Path:
    """The shared pinned interpreter, with this suite's fixture taskset in it.

    The environment itself is built once per session by
    ``tests/preflight/conftest.py``; installing the fixture package is what
    makes it this suite's interpreter.
    """
    install_fixture_package(
        pinned_engine_python, "techtree-preflight-taskset", FIXTURE_DIR
    )
    return pinned_engine_python


@pytest.fixture(scope="session")
def validate_cli(engine_python: Path) -> Path:
    """The `validate` console script the engine venv exposes (a bare name)."""
    script = engine_python.parent / "validate"
    assert script.exists(), f"no `validate` console script next to {engine_python}"
    return script


@pytest.fixture(scope="session")
def probe(engine_python: Path) -> dict:
    """Claims 2-5 and the spec 22.5 sketch, probed inside the engine venv."""
    return json.loads(_check(engine_python, PROBE, cwd=PREFLIGHT_DIR))


def _validate_argv(out: Path, *extra: str) -> tuple[str, ...]:
    """The invocation Techtree pins, rooted at `out`.

    ``--run.name`` is not decoration: without it the run directory carries a
    random suffix and neither the engine nor a digest can name the artifacts it
    just produced.
    """
    return (
        TASKSET_ID,
        "--num-tasks",
        "2",
        "--runtime.type",
        "subprocess",
        "--output-dir",
        str(out),
        "--run.name",
        RUN_DIR,
        "--rich",
        "false",
        *extra,
    )


@pytest.fixture(scope="session")
def validated(validate_cli: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run directory of the pinned validate invocation (claims 6-8)."""
    out = tmp_path_factory.mktemp("validate")
    _check(validate_cli, *_validate_argv(out))
    return out / RUN_DIR


# --------------------------------------------------------------------------
# Claim 1 — the pinned commit installs
# --------------------------------------------------------------------------


def test_pin_is_never_edited() -> None:
    assert VERIFIERS_PIN == "b2e4e8157783b2c0dffc7821044c87f29f1c3ccf"


def test_pinned_commit_installs(engine_python: Path) -> None:
    # The engine_python fixture asserts the recorded commit; this proves the
    # resulting interpreter can actually import the package.
    version = _check(
        engine_python,
        "-c",
        "from importlib.metadata import version; print(version('verifiers'))",
    ).strip()
    assert version, "verifiers reports no version"


# --------------------------------------------------------------------------
# Claim 2 — TaskData, Task and Taskset import from verifiers.v1
# --------------------------------------------------------------------------


def test_core_types_import_from_verifiers_v1(probe: dict) -> None:
    assert probe["imports"] == {
        "Task": "verifiers.v1.task.Task",
        "TaskData": "verifiers.v1.task.TaskData",
        "Taskset": "verifiers.v1.taskset.Taskset",
    }


# --------------------------------------------------------------------------
# Claim 3 — a package exported through __all__ loads as a Taskset
# --------------------------------------------------------------------------


def test_fixture_package_loads_as_a_taskset(probe: dict) -> None:
    assert probe["is_taskset"] is True
    assert probe["taskset_class"] == "PreflightTaskset"
    assert probe["task_type"] == "PreflightTask"
    assert probe["infinite"] is False


def test_taskset_id_normalizes_to_a_module_name(probe: dict) -> None:
    """A taskset id is a distribution name; hyphens become underscores.

    The helpers that used to spell this out (`verifiers.v1.utils.install`)
    are gone in v0.3.1. The rule survives, inlined in the plugin importer, and
    is now observed rather than computed: `import_taskset` returns the module
    actually imported. `TasksetConfig.name` no longer strips a Hub `org/` or
    `@version` — it is the id verbatim. Deviation D0.
    """
    assert probe["taskset_name"] == TASKSET_ID
    assert probe["taskset_module"] == "techtree_preflight_taskset"


# --------------------------------------------------------------------------
# Claim 4 — two loads produce identical task hashes
# --------------------------------------------------------------------------


def test_two_loads_produce_identical_hashes(probe: dict) -> None:
    assert probe["hashes"] == probe["hashes_reloaded"]
    assert len(probe["hashes"]) == 4


def test_task_hashes_are_unique(probe: dict) -> None:
    assert len(set(probe["hashes"])) == len(probe["hashes"])


def test_task_hash_is_raw_lowercase_hex64(probe: dict) -> None:
    """Techtree normalizes these to `sha256:<hex>` at the boundary (decision 0001)."""
    assert probe["hashes_are_raw_hex64"] is True
    for task_hash in probe["hashes"]:
        assert RAW_HASH.match(task_hash), task_hash
        assert not task_hash.startswith("sha256:")


def test_membership_is_the_first_n_in_load_order(probe: dict) -> None:
    """Decision 0001: membership is the first `num_tasks` in iteration order."""
    assert probe["head_two"] == probe["hashes"][:2]
    assert probe["head_two_idx"] == [0, 1]


# --------------------------------------------------------------------------
# Claim 5 — base Task.validate() returns True by default
# --------------------------------------------------------------------------


def test_base_validate_returns_true(probe: dict) -> None:
    assert probe["base_validate_is_async"] is True
    assert probe["base_validate_result"] is True


# --------------------------------------------------------------------------
# Spec 22.5 sketch — Task[TaskData] generics and @vf.reward
# --------------------------------------------------------------------------


def test_task_generic_and_reward_decorator_work(probe: dict) -> None:
    assert probe["data_type"] == "PreflightData"
    assert probe["config_type"] == "TaskConfig"
    assert probe["reward_hooks"] == ["exact_match"]
    assert probe["scored_rewards"] == {"exact_match": 0.0}
    assert probe["score_reply_correct"] == 1.0
    assert probe["score_reply_wrong"] == 0.0


# --------------------------------------------------------------------------
# Claim 6 — validate accepts the pinned command form
# --------------------------------------------------------------------------


def test_validate_console_script_is_named_validate(validate_cli: Path) -> None:
    """Not `vf-validate`: the pin ships bare `validate` and `eval` scripts."""
    assert validate_cli.name == "validate"
    assert (validate_cli.parent / "eval").exists()


def test_pinned_validate_invocation_succeeds(validated: Path) -> None:
    assert (validated / "summary.json").exists()


def test_validate_exits_zero_even_when_every_task_is_invalid(
    validate_cli: Path, tmp_path: Path
) -> None:
    """Exit status reports runner health, not validation outcome.

    The engine must read summary.json to decide pass or fail.
    """
    out = tmp_path / "invalid"
    env = {**os.environ, "TECHTREE_PREFLIGHT_INVALID": "1"}
    result = _run(validate_cli, *_validate_argv(out), env=env)
    assert result.returncode == 0, result.stderr
    summary = json.loads((out / RUN_DIR / "summary.json").read_text())
    assert summary["outcomes"]["invalid"] == 2
    assert summary["outcomes"]["valid"] == 0
    assert summary["valid_rate"] == 0.0


def test_validate_exits_nonzero_on_an_unknown_taskset(
    validate_cli: Path, tmp_path: Path
) -> None:
    result = _run(
        validate_cli,
        "techtree-no-such-taskset",
        "--num-tasks",
        "1",
        "--runtime.type",
        "subprocess",
        "--output-dir",
        tmp_path / "missing",
        "--run.name",
        RUN_DIR,
        "--rich",
        "false",
    )
    assert result.returncode != 0


# --------------------------------------------------------------------------
# Claim 7 — validation creates exactly four files
# --------------------------------------------------------------------------


def test_validation_creates_exactly_the_four_expected_files(validated: Path) -> None:
    written = {
        str(path.relative_to(validated))
        for path in validated.rglob("*")
        if path.is_file()
    }
    assert written == EXPECTED_OUTPUT_FILES


def test_results_jsonl_joins_on_the_raw_task_hash(validated: Path, probe: dict) -> None:
    # Rows land in COMPLETION order, which is not deterministic across runs.
    # Consumers must join on task_key/task_position, never on line position.
    lines = (validated / "results.jsonl").read_text().splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    assert {row["task_key"] for row in rows} == set(probe["hashes"][:2])
    assert {row["task_position"] for row in rows} == {0, 1}
    by_position = {row["task_position"]: row["task_key"] for row in rows}
    assert [by_position[i] for i in (0, 1)] == probe["hashes"][:2]
    assert all(row["mode"] == "all" for row in rows)


def test_resolved_config_records_shuffle_false(validated: Path) -> None:
    """Decision 0001: shuffle is false only; the runner must never reorder.

    v0.3.1 writes the resolved run configuration as JSON under
    ``configs/resolved/`` instead of a flat ``config.toml``. Deviation D1.
    """
    config = json.loads((validated / "configs/resolved/validate.json").read_text())
    assert config["shuffle"] is False
    assert config["taskset"]["id"] == "techtree-preflight-taskset"
    assert config["runtime"]["type"] == "subprocess"
    assert config["run"]["dir"] == RUN_DIR


def test_a_second_run_refuses_to_overwrite_a_run_directory(
    validate_cli: Path, tmp_path: Path
) -> None:
    """New in v0.3.1: a run directory holding results is never written twice.

    Techtree names its run directories, so this is the behaviour it meets every
    time it re-validates the same taskset into the same run tree. Deviation D3.
    """
    out = tmp_path / "twice"
    _check(validate_cli, *_validate_argv(out))
    again = _run(validate_cli, *_validate_argv(out))
    assert again.returncode != 0
    assert "already contains results" in (again.stdout + again.stderr)


# --------------------------------------------------------------------------
# Claim 8 — the persisted summary vs. the Techtree parser contract
# --------------------------------------------------------------------------


def test_summary_json_is_nested_not_flat(validated: Path) -> None:
    """DEVIATION from spec 11.9.

    `UpstreamValidationSummary` names valid/invalid/error/timeout/missing as
    top-level fields. The pin nests all five under `outcomes` and adds
    `terminal` and `owed`. `parse_summary` must project, not model_validate.
    """
    summary = json.loads((validated / "summary.json").read_text())
    assert set(summary) == {
        "checks",
        "mode",
        "outcomes",
        "owed",
        "recorded",
        "terminal",
        "total",
        "valid_rate",
    }
    assert set(summary["outcomes"]) == OUTCOME_KEYS
    for field in OUTCOME_KEYS:
        assert field not in summary


def test_summary_supplies_every_field_the_parser_contract_needs(
    validated: Path,
) -> None:
    """The exact projection `VerifiersValidationRunner.parse_summary` owes."""
    summary = json.loads((validated / "summary.json").read_text())
    outcomes = summary["outcomes"]
    projected = {
        "mode": summary["mode"],
        "total": summary["total"],
        "recorded": summary["recorded"],
        "valid": outcomes["valid"],
        "invalid": outcomes["invalid"],
        "error": outcomes["error"],
        "timeout": outcomes["timeout"],
        "missing": outcomes["missing"],
        "valid_rate": summary["valid_rate"],
    }
    assert projected == {
        "mode": "all",
        "total": 2,
        "recorded": 2,
        "valid": 2,
        "invalid": 0,
        "error": 0,
        "timeout": 0,
        "missing": 0,
        "valid_rate": 1.0,
    }


def test_mode_all_carries_per_check_gold_and_setup_counts(validated: Path) -> None:
    summary = json.loads((validated / "summary.json").read_text())
    assert set(summary["checks"]) == {"gold", "setup"}
    for check in summary["checks"].values():
        assert set(check) == OUTCOME_KEYS
    assert summary["checks"]["gold"]["valid"] == 2
    assert summary["checks"]["setup"]["valid"] == 2


@pytest.mark.parametrize(
    ("flag", "mode"), [("--only-gold", "gold"), ("--only-setup", "setup")]
)
def test_single_check_modes_omit_the_checks_block(
    validate_cli: Path, tmp_path: Path, flag: str, mode: str
) -> None:
    """The `checks` key exists only in mode `all`; the parser must not require it."""
    out = tmp_path / mode
    _check(validate_cli, *_validate_argv(out, flag))
    summary = json.loads((out / RUN_DIR / "summary.json").read_text())
    assert summary["mode"] == mode
    assert "checks" not in summary
    assert summary["outcomes"]["valid"] == 2


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-m", "preflight", "-p", "no:cacheprovider"]))
