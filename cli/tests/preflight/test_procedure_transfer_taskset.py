"""PR10 — the reference taskset, proven against the pinned Verifiers commit.

Companion to `test_verifiers_contract.py`. That module proves what the pinned
commit *does*; this one proves that
`src/techtree/resources/engines/default/packages/procedure-transfer-v1/`
behaves correctly when loaded by it.

The harness (throwaway engine venv, pin verification from the installed
distribution's VCS metadata, an in-process probe) is deliberately duplicated
rather than shared: `test_verifiers_contract.py` is the PI0 record and is not
this ticket's to edit.

## Running it

    make verifiers-preflight

Marked `preflight` and excluded from the default run: it builds a virtualenv
and reaches github.com and PyPI. To reuse an already-built engine venv:

    TECHTREE_PREFLIGHT_ENGINE_PYTHON=/path/to/engine/.venv/bin/python \
        uv run pytest -m preflight tests/preflight

The reference package is reinstalled into that interpreter on every session, so
a stale build cannot pass for a fresh one.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.preflight

VERIFIERS_REPO = "https://github.com/PrimeIntellect-ai/verifiers"
VERIFIERS_PIN = "7e1c47d24d055aae587ee8259f77a3e8e193513a"
"""Binding (docs/decisions/0001). Never bump this here; a bump is its own ticket."""

TASKSET_ID = "procedure-transfer-v1"
"""Spec 22.7 distribution name. Verifiers imports it as `procedure_transfer_v1`."""

ENGINE_PYTHON_ENV = "TECHTREE_PREFLIGHT_ENGINE_PYTHON"

PACKAGE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "techtree"
    / "resources"
    / "engines"
    / "default"
    / "packages"
    / "procedure-transfer-v1"
)

EXPECTED_OUTPUT_FILES = {"config.toml", "results.jsonl", "summary.json", "validate.log"}
OUTCOME_KEYS = {"valid", "invalid", "error", "timeout", "missing"}
RAW_HASH = re.compile(r"^[0-9a-f]{64}$")

HEAD = 5
"""How many tasks the probe takes with `head()`, for the membership check."""

PROMPT_TEMPLATE = (
    "Apply BranchCode v1 to this input:\n"
    "\n"
    "{input_text}\n"
    "\n"
    "Return only the final BRANCH-XX token."
)
"""Spec 22.5, verbatim and independently restated here."""

PROCEDURE_TERMS = (
    "modul",
    "97",
    "distinct",
    "position",
    "alphabet",
    "letter",
    "multiply",
    "seven",
    "sum",
    "weight",
    "index",
    "count",
    "a=1",
    "z=26",
)
"""Words that would leak BranchCode v1. None may appear in any prompt."""

EXPECTED: tuple[tuple[str, str], ...] = (
    ("alder", "BRANCH-85"),
    ("aspen", "BRANCH-18"),
    ("beech", "BRANCH-10"),
    ("cedar", "BRANCH-57"),
    ("hazel", "BRANCH-09"),
    ("larch", "BRANCH-58"),
    ("rowan", "BRANCH-32"),
    ("pinyon", "BRANCH-79"),
    ("poplar", "BRANCH-96"),
    ("spruce", "BRANCH-82"),
    ("willow", "BRANCH-75"),
    ("cypress", "BRANCH-02"),
    ("dogwood", "BRANCH-77"),
    ("hemlock", "BRANCH-33"),
    ("juniper", "BRANCH-27"),
    ("sequoia", "BRANCH-58"),
    ("chestnut", "BRANCH-68"),
    ("hornbeam", "BRANCH-64"),
    ("ironwood", "BRANCH-45"),
    ("laburnum", "BRANCH-93"),
    ("magnolia", "BRANCH-68"),
    ("mangrove", "BRANCH-30"),
    ("mulberry", "BRANCH-25"),
    ("sycamore", "BRANCH-71"),
    ("tamarack", "BRANCH-21"),
    ("buckthorn", "BRANCH-04"),
    ("jacaranda", "BRANCH-11"),
    ("persimmon", "BRANCH-90"),
    ("sassafras", "BRANCH-43"),
    ("whitebeam", "BRANCH-11"),
    ("blackthorn", "BRANCH-85"),
    ("cottonwood", "BRANCH-54"),
    ("elderberry", "BRANCH-20"),
    ("eucalyptus", "BRANCH-14"),
    ("sandalwood", "BRANCH-79"),
    ("bristlecone", "BRANCH-93"),
)
"""The frozen dataset and its oracle codes, restated independently of the package."""

EXPECTED_INPUTS = tuple(entry for entry, _ in EXPECTED)
EXPECTED_ANSWERS = tuple(code for _, code in EXPECTED)
EXPECTED_NAMES = tuple(f"branch-code-{index:03d}" for index in range(len(EXPECTED)))
TASK_COUNT = len(EXPECTED)

PROBE_SOURCE = r'''
"""In-process probe of the reference taskset, run with the engine interpreter."""

import asyncio
import json
import re

import verifiers.v1 as vf
from verifiers.v1 import Taskset
from verifiers.v1.utils.install import env_module, env_name

TASKSET_ID = "procedure-transfer-v1"
RAW_HASH = re.compile(r"^[0-9a-f]{64}$")
HEAD = 5


def trace_with(task, reply):
    """A hand-built trace carrying one sampled assistant reply.

    `vf.Trace` needs an `agent`, and `last_reply` reads the last *sampled*
    assistant message, so the reply has to arrive as a MessageNode.
    """
    return vf.Trace(
        task=vf.TraceTask(type=type(task).__name__, data=task.data, hash=task.hash),
        state=vf.State(),
        agent=vf.AgentInfo(config=vf.AgentConfig(), name="pr10", trainable=False),
        nodes=[
            vf.MessageNode(
                parent=None,
                message=vf.AssistantMessage(content=reply),
                sampled=True,
            )
        ],
    )


def reward_for(task, reply):
    trace = trace_with(task, reply)
    asyncio.run(task.score(trace, None))
    return {name: reward.score for name, reward in trace.rewards.items()}


def near_miss(answer):
    """A well-formed but wrong token: the next code in the modular sequence."""
    return "BRANCH-%02d" % ((int(answer.removeprefix("BRANCH-")) + 1) % 97)


def probe():
    import procedure_transfer_v1 as package

    first = vf.load_taskset(vf.TasksetConfig(id=TASKSET_ID))
    second = vf.load_taskset(vf.TasksetConfig(id=TASKSET_ID))
    tasks = list(first)
    hashes = [task.hash for task in tasks]
    exported = [getattr(package, name) for name in package.__all__]
    task = tasks[0]

    return {
        "taskset_class": type(first).__name__,
        "taskset_module": type(first).__module__,
        "is_taskset": isinstance(first, Taskset),
        "task_type": type(first).task_type().__name__,
        "infinite": type(first).INFINITE,
        "env_name": env_name(TASKSET_ID),
        "env_module": env_module(TASKSET_ID),
        "all": list(package.__all__),
        "exported_taskset_count": sum(
            1
            for obj in exported
            if isinstance(obj, type) and issubclass(obj, Taskset)
        ),
        "count": len(tasks),
        "names": [t.data.name for t in tasks],
        "idxs": [t.data.idx for t in tasks],
        "input_texts": [t.data.input_text for t in tasks],
        "answers": [t.data.answer for t in tasks],
        "prompts": [t.data.prompt for t in tasks],
        "hashes": hashes,
        "hashes_reloaded": [t.hash for t in second],
        "hashes_are_raw_hex64": all(bool(RAW_HASH.match(h)) for h in hashes),
        "head_hashes": [t.hash for t in first.head(HEAD)],
        "head_idx": [t.data.idx for t in first.head(HEAD)],
        "validate_all": [asyncio.run(t.validate(None)) for t in tasks],
        "score_correct": [t.score_reply(t.data.answer) for t in tasks],
        "score_near_miss": [t.score_reply(near_miss(t.data.answer)) for t in tasks],
        "score_malformed": [t.score_reply("BRANCH-XX") for t in tasks],
        "score_lowercased": [t.score_reply(t.data.answer.lower()) for t in tasks],
        "score_padded": [t.score_reply("  " + t.data.answer + "\n") for t in tasks],
        "score_in_prose": [
            t.score_reply("The answer is " + t.data.answer) for t in tasks
        ],
        "score_empty": [t.score_reply("") for t in tasks],
        "reward_hooks": [fn.__name__ for fn in task.hooks("reward")],
        "reward_correct": reward_for(task, task.data.answer),
        "reward_near_miss": reward_for(task, near_miss(task.data.answer)),
        "data_type": type(task).data_type().__name__,
        "config_type": type(task).config_type().__name__,
    }


print(json.dumps(probe(), sort_keys=True))
'''


def _run(*argv: str | Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(arg) for arg in argv],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _check(*argv: str | Path, env: dict | None = None) -> str:
    result = _run(*argv, env=env)
    if result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(str(a) for a in argv)}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )
    return result.stdout


def _installed_pin(python: Path) -> dict:
    """The VCS metadata pip/uv records for a git install, read with `python`."""
    source = (
        "import json;"
        "from importlib.metadata import distribution;"
        "print(distribution('verifiers').read_text('direct_url.json') or '{}')"
    )
    return json.loads(_check(python, "-c", source).strip())


@pytest.fixture(scope="session")
def engine_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An interpreter holding the pinned commit and the reference package."""
    supplied = os.environ.get(ENGINE_PYTHON_ENV)
    if supplied:
        # Not resolve(): a venv's bin/python is a symlink to the base interpreter,
        # and following it would drop the venv's site-packages.
        python = Path(supplied).expanduser().absolute()
        if not python.exists():
            pytest.fail(f"{ENGINE_PYTHON_ENV}={supplied} does not exist")
    else:
        venv = tmp_path_factory.mktemp("reference-engine") / ".venv"
        _check("uv", "venv", "--python", "3.12", venv)
        python = venv / "bin" / "python"
        _check(
            "uv",
            "pip",
            "install",
            "--python",
            python,
            f"verifiers @ git+{VERIFIERS_REPO}@{VERIFIERS_PIN}",
        )

    recorded = _installed_pin(python)
    assert recorded.get("vcs_info", {}).get("commit_id") == VERIFIERS_PIN, (
        f"engine venv does not hold the pin {VERIFIERS_PIN}: {recorded}"
    )

    # Always reinstall: a supplied venv may hold a stale build of the package.
    _check(
        "uv",
        "pip",
        "install",
        "--python",
        python,
        "--reinstall-package",
        TASKSET_ID,
        PACKAGE_DIR,
    )
    return python


@pytest.fixture(scope="session")
def validate_cli(engine_python: Path) -> Path:
    """The `validate` console script (a bare name — PI0 finding C3)."""
    script = engine_python.parent / "validate"
    assert script.exists(), f"no `validate` console script next to {engine_python}"
    return script


@pytest.fixture(scope="session")
def probe(engine_python: Path) -> dict:
    """The reference taskset, inspected inside the engine venv."""
    return json.loads(_check(engine_python, "-c", PROBE_SOURCE))


@pytest.fixture(scope="session")
def validated(validate_cli: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Output directory of a full pinned `validate` run over every task."""
    out = tmp_path_factory.mktemp("reference-validate") / "run"
    _check(
        validate_cli,
        TASKSET_ID,
        "--num-tasks",
        str(TASK_COUNT),
        "--runtime.type",
        "subprocess",
        "--output-dir",
        out,
        "--rich",
        "false",
    )
    return out


@pytest.fixture(scope="session")
def rows(validated: Path) -> list[dict]:
    """`results.jsonl` rows, keyed by task position — never by line order (C0)."""
    lines = (validated / "results.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


# --------------------------------------------------------------------------
# Loading through the plugin mechanism
# --------------------------------------------------------------------------


def test_pin_is_never_edited() -> None:
    assert VERIFIERS_PIN == "7e1c47d24d055aae587ee8259f77a3e8e193513a"


def test_package_loads_as_a_taskset(probe: dict) -> None:
    assert probe["is_taskset"] is True
    assert probe["taskset_class"] == "ProcedureTransferTaskset"
    assert probe["task_type"] == "ProcedureTransferTask"
    assert probe["infinite"] is False


def test_loaded_class_comes_from_this_package_not_a_bundled_one(probe: dict) -> None:
    """A first-party `verifiers.v1.tasksets.<module>` would shadow the package."""
    assert probe["taskset_module"] == "procedure_transfer_v1.taskset"


def test_taskset_id_normalizes_to_the_package_module(probe: dict) -> None:
    assert probe["env_name"] == TASKSET_ID
    assert probe["env_module"] == "procedure_transfer_v1"


def test_package_exports_exactly_one_taskset(probe: dict) -> None:
    """Spec 22.6. Zero raises TypeError upstream; two or more raises ValueError."""
    assert probe["all"] == ["ProcedureTransferTaskset"]
    assert probe["exported_taskset_count"] == 1


def test_task_generics_resolve(probe: dict) -> None:
    assert probe["data_type"] == "ProcedureTransferData"
    assert probe["config_type"] == "TaskConfig"


# --------------------------------------------------------------------------
# One deterministic task per proving input, in dataset order
# --------------------------------------------------------------------------


def test_taskset_yields_one_task_per_proving_input(probe: dict) -> None:
    assert probe["count"] == TASK_COUNT


def test_tasks_follow_the_frozen_dataset_order(probe: dict) -> None:
    assert tuple(probe["input_texts"]) == EXPECTED_INPUTS


def test_task_names_are_zero_padded_and_sequential(probe: dict) -> None:
    assert tuple(probe["names"]) == EXPECTED_NAMES
    assert probe["idxs"] == list(range(TASK_COUNT))


def test_stored_answers_are_the_oracle_codes(probe: dict) -> None:
    assert tuple(probe["answers"]) == EXPECTED_ANSWERS


# --------------------------------------------------------------------------
# Hash determinism and membership
# --------------------------------------------------------------------------


def test_two_loads_produce_identical_hashes(probe: dict) -> None:
    assert probe["hashes"] == probe["hashes_reloaded"]
    assert len(probe["hashes"]) == TASK_COUNT


def test_task_hashes_are_unique(probe: dict) -> None:
    assert len(set(probe["hashes"])) == TASK_COUNT


def test_task_hashes_are_raw_lowercase_hex64(probe: dict) -> None:
    """Techtree normalizes these to `sha256:<hex>` at the boundary (decision 0001)."""
    assert probe["hashes_are_raw_hex64"] is True
    for task_hash in probe["hashes"]:
        assert RAW_HASH.match(task_hash), task_hash
        assert not task_hash.startswith("sha256:")


def test_membership_is_the_first_n_in_load_order(probe: dict) -> None:
    """Decision 0001: membership is the first `num_tasks` in iteration order."""
    assert probe["head_hashes"] == probe["hashes"][:HEAD]
    assert probe["head_idx"] == list(range(HEAD))


# --------------------------------------------------------------------------
# The prompt carries the task, never the procedure
# --------------------------------------------------------------------------


def test_prompt_matches_the_spec_template_exactly(probe: dict) -> None:
    for input_text, prompt in zip(EXPECTED_INPUTS, probe["prompts"], strict=True):
        assert prompt == PROMPT_TEMPLATE.format(input_text=input_text)


@pytest.mark.parametrize("term", PROCEDURE_TERMS)
def test_prompt_never_leaks_the_procedure(probe: dict, term: str) -> None:
    """Spec 22.5: the procedure arrives only via the candidate skill."""
    for prompt in probe["prompts"]:
        assert term not in prompt.lower(), f"{term!r} leaked into {prompt!r}"


def test_prompt_never_contains_the_answer(probe: dict) -> None:
    for answer, prompt in zip(probe["answers"], probe["prompts"], strict=True):
        assert answer not in prompt


def test_prompt_contains_only_the_input_and_the_two_fixed_lines(probe: dict) -> None:
    for input_text, prompt in zip(EXPECTED_INPUTS, probe["prompts"], strict=True):
        assert prompt.splitlines() == [
            "Apply BranchCode v1 to this input:",
            "",
            input_text,
            "",
            "Return only the final BRANCH-XX token.",
        ]


# --------------------------------------------------------------------------
# Model-free validation and scoring
# --------------------------------------------------------------------------


def test_validate_passes_for_every_task(probe: dict) -> None:
    """Overriding `validate` is what makes the WP5 gold check real."""
    assert probe["validate_all"] == [True] * TASK_COUNT


def test_correct_answer_scores_one_for_every_task(probe: dict) -> None:
    assert probe["score_correct"] == [1.0] * TASK_COUNT


def test_known_wrong_reply_scores_zero_for_every_task(probe: dict) -> None:
    assert probe["score_near_miss"] == [0.0] * TASK_COUNT
    assert probe["score_malformed"] == [0.0] * TASK_COUNT
    assert probe["score_empty"] == [0.0] * TASK_COUNT


def test_reply_normalization_accepts_case_and_surrounding_whitespace(
    probe: dict,
) -> None:
    assert probe["score_lowercased"] == [1.0] * TASK_COUNT
    assert probe["score_padded"] == [1.0] * TASK_COUNT


def test_a_token_buried_in_prose_is_not_accepted(probe: dict) -> None:
    """The prompt asks for the token alone, so exact match stays exact."""
    assert probe["score_in_prose"] == [0.0] * TASK_COUNT


def test_reward_hook_is_discovered_and_scores_the_last_reply(probe: dict) -> None:
    assert probe["reward_hooks"] == ["exact_match"]
    assert probe["reward_correct"] == {"exact_match": 1.0}
    assert probe["reward_near_miss"] == {"exact_match": 0.0}


# --------------------------------------------------------------------------
# The real `validate` CLI over the whole taskset
# --------------------------------------------------------------------------


def test_validation_creates_exactly_the_four_expected_files(validated: Path) -> None:
    assert {p.name for p in validated.iterdir()} == EXPECTED_OUTPUT_FILES


def test_every_task_validates_under_the_pinned_runner(validated: Path) -> None:
    summary = json.loads((validated / "summary.json").read_text())
    outcomes = summary["outcomes"]
    assert set(outcomes) == OUTCOME_KEYS
    assert outcomes["valid"] == TASK_COUNT
    assert outcomes["invalid"] == 0
    assert outcomes["error"] == 0
    assert outcomes["timeout"] == 0
    assert outcomes["missing"] == 0
    assert summary["total"] == TASK_COUNT
    assert summary["recorded"] == TASK_COUNT
    assert summary["valid_rate"] == 1.0


def test_gold_and_setup_both_pass_for_every_task(validated: Path) -> None:
    summary = json.loads((validated / "summary.json").read_text())
    assert summary["mode"] == "all"
    assert summary["checks"]["gold"]["valid"] == TASK_COUNT
    assert summary["checks"]["setup"]["valid"] == TASK_COUNT


def test_results_rows_join_on_task_key_not_line_order(
    rows: list[dict], probe: dict
) -> None:
    """PI0 finding C0: rows land in completion order, which varies per run."""
    assert len(rows) == TASK_COUNT
    assert {row["task_position"] for row in rows} == set(range(TASK_COUNT))
    by_position = {row["task_position"]: row["task_key"] for row in rows}
    assert [by_position[i] for i in range(TASK_COUNT)] == probe["hashes"]


def test_every_result_row_is_valid(rows: list[dict]) -> None:
    assert all(row["valid"] for row in rows)
    assert all(row["reason"] == "valid" for row in rows)
    assert all(row["error"] is None for row in rows)


def test_result_rows_carry_the_expected_task_names(rows: list[dict]) -> None:
    by_position = {row["task_position"]: row["name"] for row in rows}
    assert [by_position[i] for i in range(TASK_COUNT)] == list(EXPECTED_NAMES)


def test_config_toml_records_shuffle_false(validated: Path) -> None:
    """Decision 0001: shuffle is false only; the runner must never reorder."""
    config = (validated / "config.toml").read_text()
    assert "shuffle = false" in config
    assert f'id = "{TASKSET_ID}"' in config
    assert 'type = "subprocess"' in config


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-m", "preflight", "-p", "no:cacheprovider"]))
