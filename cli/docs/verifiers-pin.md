# Verifiers pin — PI0 preflight findings

Ticket: `techtree-python-3jj.5.1` (PI0 — Verify the pinned Verifiers contract).
Blocks PR9–PR12. Spec sections §2.1, §11.9, §21.4, §22.5.

```text
PrimeIntellect-ai/verifiers
7e1c47d24d055aae587ee8259f77a3e8e193513a
```

Everything below was observed against that commit and nothing else. Resolved
distribution: `verifiers 0.3.1.dev21`, `Requires-Python: <3.14,>=3.11`,
installed into a throwaway `uv` venv on Python 3.12 (macOS arm64).

Reproduce with `make verifiers-preflight`
(`tests/preflight/test_verifiers_contract.py`, 23 checks, all green).

---

## CRITICAL — four deviations from the spec's assumptions

These reshape PR9–PR12. Read them before writing `tasksets/verifiers_cli.py`.

### C0. `results.jsonl` row order is completion order, not task order

Rows are appended as each isolated validation check finishes, so the line
order varies between otherwise identical runs (observed directly: two runs of
the same 2-task fixture produced the two rows in opposite orders). Every row
carries `task_key` (the raw 64-char hash) and `task_position`; consumers must
join on those fields and must never rely on line position. This also means
the raw bytes of `results.jsonl` are NOT reproducible across runs — relevant
to any byte-level artifact digesting or regeneration check.

### C1. `summary.json` is nested, not flat

Spec §11.9 models `UpstreamValidationSummary` with `valid`, `invalid`, `error`,
`timeout` and `missing` as **top-level** fields. The pin nests all five under an
`outcomes` object and adds two fields the spec does not model (`terminal`,
`owed`) plus a `checks` block.

`VerifiersValidationRunner.parse_summary` must **project** the persisted JSON
into `UpstreamValidationSummary`. It must not `model_validate` the file
directly — every one of the five count fields is at the wrong depth, and the
extra keys would be rejected or silently swallowed depending on the
`ProtocolModel` extras policy.

The exact projection (asserted by
`test_summary_supplies_every_field_the_parser_contract_needs`):

```python
outcomes = summary["outcomes"]
UpstreamValidationSummary(
    mode=summary["mode"],
    total=summary["total"],
    recorded=summary["recorded"],
    valid=outcomes["valid"],
    invalid=outcomes["invalid"],
    error=outcomes["error"],
    timeout=outcomes["timeout"],
    missing=outcomes["missing"],
    valid_rate=summary["valid_rate"],
)
```

Good news: no field is *missing*. All nine values the spec's parser contract
needs are present, with matching types and matching `mode` literals
(`"all" | "gold" | "setup"`), and `valid_rate` really is `float | None`
(`None` only when `total == 0`; otherwise `round(valid / total, 6)`).

### C2. `validate` exits 0 even when every task fails

The runner's exit status reports *runner health*, not validation outcome. A run
in which every task is invalid, errored, or timed out still exits `0`.
Only an unresolvable taskset id, a bad config, or an interrupt (`130`) is
non-zero.

`VerifiersValidationRunner.run` must therefore never treat
`EngineProcessResult.returncode == 0` as "the taskset is valid". Validity comes
from `summary.json` alone. Observed directly:

```text
$ validate techtree-preflight-taskset --num-tasks 2 --runtime.type subprocess \
      --output-dir outbad --rich false
EXIT=0
{"outcomes": {"error": 1, "invalid": 1, "missing": 0, "timeout": 0, "valid": 0}, ...}
```

### C3. The console script is bare `validate`, not `vf-validate`

The pin installs unprefixed console scripts into the engine venv's `bin/`:

```text
[console_scripts]
debug    = verifiers.v1.cli.debug:main
eval     = verifiers.v1.cli.eval.main:main
gepa     = verifiers.v1.cli.gepa:main
init     = verifiers.v1.cli.init:main
replay   = verifiers.v1.cli.replay:main
validate = verifiers.v1.cli.validate:main
vf-build, vf-eval, vf-gepa, vf-init, vf-install, vf-setup, vf-tui  → verifiers.legacy.*
```

`validate`, `eval`, `debug`, `init` and `replay` are names generic enough to
collide with anything already on `PATH`. The `vf-` prefixed scripts are the
**legacy** v0 CLI and are not the ones Techtree wants.

`EngineRunner` must invoke the scripts by absolute path inside the engine venv
(`<engine-venv>/bin/validate`) and must never rely on `PATH` resolution.

---

## Claim-by-claim results

| # | Claim (spec §2.1) | Result |
|---|---|---|
| 1 | The pinned commit installs | verified |
| 2 | `TaskData`, `Task`, `Taskset` import from `verifiers.v1` | verified |
| 3 | A tiny package exported through `__all__` loads as a Taskset | verified |
| 4 | Two loads produce identical task hashes | verified |
| 5 | Base `Task.validate()` returns True by default | verified |
| 6 | `validate` accepts the pinned command form | verified, verbatim |
| 7 | Validation creates exactly the four expected files | verified |
| 8 | Persisted summary matches the §11.9 parser contract | **refuted** — see C1 |

### 1. The pinned commit installs

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python \
  "verifiers @ git+https://github.com/PrimeIntellect-ai/verifiers@7e1c47d24d055aae587ee8259f77a3e8e193513a"
```

Installs clean, no build steps, no manual system dependencies. The commit is
recorded in the installed distribution and can be asserted offline afterwards —
this is how the preflight test proves the pin rather than trusting the caller:

`.venv/lib/python3.12/site-packages/verifiers-0.3.1.dev21.dist-info/direct_url.json`

```json
{"url":"https://github.com/PrimeIntellect-ai/verifiers","vcs_info":{"vcs":"git","commit_id":"7e1c47d24d055aae587ee8259f77a3e8e193513a","requested_revision":"7e1c47d24d055aae587ee8259f77a3e8e193513a"}}
```

### 2. Core types import from `verifiers.v1`

All three are re-exported from the `verifiers.v1` package root and listed in its
`__all__`. Canonical locations:

```text
verifiers.v1.task.Task
verifiers.v1.task.TaskData
verifiers.v1.taskset.Taskset
```

`import verifiers.v1 as vf` is the idiomatic form the upstream CLI itself uses.
`vf.Runtime`, `vf.Trace`, `vf.TasksetConfig`, `vf.SubprocessConfig` and
`vf.reward` are all likewise available from that root.

### 3. A package exported through `__all__` loads as a Taskset

Resolution path is `vf.load_taskset(TasksetConfig(id=...))` →
`taskset_class(id)` → `_import_plugin` → `_plugin_class`.

Rules observed in `verifiers/v1/utils/loaders.py` and `utils/install.py`:

- A **local** id (no `/`) is assumed already importable. Nothing is fetched.
  Only a Hub id of the form `org/name[@version]` triggers a network install.
- The id is a **distribution name**; the module name is the id with hyphens
  normalized to underscores. `techtree-preflight-taskset` →
  `techtree_preflight_taskset`. So spec §22.7's `procedure-transfer-v1`
  distribution correctly imports as `procedure_transfer_v1`.
- The module must define `__all__`, and exactly **one** name in it may be a
  `Taskset` subclass. Zero raises `TypeError`, two or more raises `ValueError`.
  Spec §22.6's `__init__.py` sketch is exactly right.
- A first-party `verifiers.v1.tasksets.<module>` shadows a same-named
  standalone package, so avoid names that collide with bundled tasksets.

The fixture (`tests/preflight/fixture_taskset/`) loads as `PreflightTaskset`,
`isinstance(..., Taskset)` is true, `task_type()` resolves to `PreflightTask`,
and `INFINITE` is `False`.

### 4. Two loads produce identical task hashes

Two independent `load_taskset` calls yielded byte-identical hash lists, all
unique. Observed hashes for the four fixture tasks:

```text
9b93b68596a34061b6019fe58c689c0ca312d69c03b87e9bed170dd610dde9a4
5d856f3da51813abe5e5f850b2e972ac0a7512d11cdea200e736cf41da0b0a08
a9fe01dd003d2ab82c335714f75b9d7631c212607982e08121c825e397be759e
28ae4000e36a6b5a159babec84fd2ac011b757672f215e0e149662275aeb7575
```

### 5. Base `Task.validate()` returns True

```python
async def validate(self, runtime: Runtime) -> bool:
    return True
```

It is a **coroutine**, so it must be awaited. `Task(BareData(idx=0))` then
`await task.validate(None)` returns `True`; `runtime` is accepted as `None` on
the base implementation because the base never touches it.

The same is true of `setup` and `finalize` (both `async`, both return `None`).

### 6. The pinned command form

The conceptual form from the ticket works **verbatim**, no adjustment needed:

```bash
<engine-venv>/bin/validate techtree-preflight-taskset \
  --num-tasks 2 \
  --runtime.type subprocess \
  --output-dir <tmp>
```

The form Techtree should actually pin adds `--rich false`:

```bash
<engine-venv>/bin/validate <taskset-id> \
  --num-tasks <n> \
  --runtime.type subprocess \
  --output-dir <run-dir> \
  --rich false
```

`--rich` defaults to `true`, which paints a live dashboard. With
`--rich false` the runner emits one plain log line per task instead, which is
what a captured subprocess wants.

Streams, for `EngineProcessResult` handling:

- **stdout**: `results: <output-dir>`, then the full `summary.json` pretty-printed.
- **stderr**: the log lines (`INFO validating 2/2 task(s) from … (gold+setup)`,
  then `INFO idx=0 valid=True reason=valid (0.0s)` per task).

Argument details worth knowing:

- The taskset id is **positional**; `--taskset.id <id>` is the equivalent
  explicit flag. Both were confirmed working.
- `--num-tasks` accepts the aliases `-n`, `--num-examples`, `--batch-size`.
  It is `ge=1`; `None` means all tasks. An infinite taskset without `-n` raises.
- `--output-dir` accepts the alias `-o`. When omitted, output lands in
  `outputs/<taskset-name>--validate/<uuid>` relative to the **current working
  directory** — always pass it explicitly.
- `--runtime.type` selects a discriminated union of
  `subprocess | docker | prime | modal`. The default is **docker**, so
  `--runtime.type subprocess` is required, not optional. A taskset whose tasks
  set `NEEDS_CONTAINER` or `data.image` refuses the subprocess runtime with a
  clear `SystemExit`.
- `--shuffle` (alias `-s`) defaults to `false` and is recorded as
  `shuffle = false` in `config.toml`. Decision 0001 forbids ever setting it.
- `--max-concurrent` (alias `-c`) defaults to `128`.
- `--only-gold` and `--only-setup` are mutually exclusive; passing neither runs
  both checks (`mode = "all"`).
- `--resume <output-dir>` replays the saved `config.toml` and takes no other
  arguments. Not needed by Techtree, but it explains why `config.toml` exists.

### 7. Validation output files

Exactly four, no more:

```text
config.toml
results.jsonl
summary.json
validate.log
```

`summary.json` and `results.jsonl` are written through a `.tmp` sibling and
atomically replaced, so a `.tmp` file is transient and never present after the
process exits. `validate.log` is created by the logging setup before the run
starts, so it exists even on an early failure.

`config.toml` is the resolved run config in re-readable form:

```toml
only_setup = false
only_gold = false
num_tasks = 2
shuffle = false
max_concurrent = 128
verbose = false
rich = true
output_dir = "out1"

[taskset]
id = "techtree-preflight-taskset"

[taskset.task]
judges = []

[taskset.task.stops]

[taskset.task.metrics]

[taskset.task.rewards]

[runtime]
type = "subprocess"

[timeout]
```

`results.jsonl` is one compact, key-sorted JSON object per task. **`task_key` is
the raw Verifiers task hash** — this is the join key between a validation row
and a `TasksetLock.ordered_task_hashes` entry:

```json
{"elapsed":0.0,"error":null,"error_type":null,"gold":{"elapsed":0.0,"error":null,"error_type":null,"index":0,"mode":"gold","name":"preflight-0","reason":"valid","valid":true},"index":0,"mode":"all","name":"preflight-0","reason":"valid","setup":{"elapsed":0.0,"error":null,"error_type":null,"index":0,"mode":"setup","name":"preflight-0","reason":"valid","valid":true},"task_key":"9b93b68596a34061b6019fe58c689c0ca312d69c03b87e9bed170dd610dde9a4","task_position":0,"valid":true}
```

Row fields: `index` (the task's `data.idx`), `name`, `mode`, `valid`, `reason`
(one of `valid | invalid | error | timeout`), `elapsed`, `error`, `error_type`,
`task_key`, `task_position`. In `mode = "all"` the row additionally nests a
`gold` and a `setup` sub-row of the same shape.

`validate.log`:

```text
20:50:23    INFO validating 2/2 task(s) from techtree-preflight-taskset on the subprocess runtime (gold+setup)
20:50:23    INFO results: out1
```

### 8. `summary.json` — REFUTED, see C1

Verbatim sample from the passing two-task run
(`--num-tasks 2 --runtime.type subprocess`, `mode = "all"`):

```json
{
  "checks": {
    "gold": {
      "error": 0,
      "invalid": 0,
      "missing": 0,
      "timeout": 0,
      "valid": 2
    },
    "setup": {
      "error": 0,
      "invalid": 0,
      "missing": 0,
      "timeout": 0,
      "valid": 2
    }
  },
  "mode": "all",
  "outcomes": {
    "error": 0,
    "invalid": 0,
    "missing": 0,
    "timeout": 0,
    "valid": 2
  },
  "owed": 0,
  "recorded": 2,
  "terminal": 2,
  "total": 2,
  "valid_rate": 1.0
}
```

Field meanings, from `verifiers/v1/cli/validate.py::summarize`:

| Field | Type | Meaning |
|---|---|---|
| `mode` | `"all" \| "gold" \| "setup"` | Which checks ran. Matches the spec literal exactly. |
| `total` | `int` | Tasks selected (i.e. `num_tasks`, or the whole taskset). |
| `recorded` | `int` | Result rows actually persisted. |
| `terminal` | `int` | `valid + invalid` — reached a final verdict. **Not in the spec model.** |
| `owed` | `int` | `missing + error + timeout` — what a `--resume` would retry. **Not in the spec model.** |
| `outcomes` | object | The five counts the spec expects at top level. |
| `outcomes.missing` | `int` | `max(0, total - recorded)`; derived, not counted. |
| `valid_rate` | `float \| None` | `round(valid / total, 6)`, or `null` when `total == 0`. |
| `checks` | object | **Present only when `mode == "all"`.** Per-check counts. |

The `checks` block carries the same five outcome keys for `gold` and for
`setup` separately. It is the natural source for the spec §21.5 required checks
`upstream_gold` and `upstream_setup`. The parser must treat it as optional —
`--only-gold` and `--only-setup` runs omit it entirely:

```json
{
  "mode": "gold",
  "outcomes": {
    "error": 0,
    "invalid": 0,
    "missing": 0,
    "timeout": 0,
    "valid": 2
  },
  "owed": 0,
  "recorded": 2,
  "terminal": 2,
  "total": 2,
  "valid_rate": 1.0
}
```

A failing run (every task invalid, one raising) for contrast:

```json
{
  "checks": {
    "gold": {"error": 1, "invalid": 1, "missing": 0, "timeout": 0, "valid": 0},
    "setup": {"error": 0, "invalid": 0, "missing": 0, "timeout": 0, "valid": 2}
  },
  "mode": "all",
  "outcomes": {"error": 1, "invalid": 1, "missing": 0, "timeout": 0, "valid": 0},
  "owed": 1,
  "recorded": 2,
  "terminal": 1,
  "total": 2,
  "valid_rate": 0.0
}
```

Note the outcome classification: a `validate` hook returning `False` is
`invalid`; a hook **raising** is `error`; an `asyncio.TimeoutError` is
`timeout`. So a broken taskset plugin shows up as `error`, cleanly separated
from a taskset that is merely wrong.

---

## Additional recorded facts

### Raw task-hash format

Confirmed **64-character lowercase hex with no `sha256:` prefix**, exactly as
decision 0001 assumes. From `verifiers/v1/task.py`:

```python
def task_key(data: Mapping) -> str:
    """Content identity for task wire data, independent of field order."""
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

@property
def hash(self) -> str:
    return task_key(self.data.model_dump(mode="json", exclude_none=True))
```

Two consequences for `normalize_verifiers_task_hash`:

- The hash is over the task's **wire data with `None` fields dropped**
  (`exclude_none=True`) and keys sorted, so it is stable across field
  reordering but **changes if a `TaskData` field gains a non-`None` default**.
- Defaults that are not `None` *are* included. The fixture's wire data shows
  `artifacts`, `network_allow`, `network_block`, `resources` and `timeout`
  all participating in the hash:

```json
{
  "answer": "BRANCH-01",
  "artifacts": [],
  "idx": 0,
  "input_text": "alpha",
  "name": "preflight-0",
  "network_allow": ["*"],
  "network_block": [],
  "prompt": "Apply BranchCode v1 to this input:\n\nalpha\n\nReturn only the final BRANCH-XX token.",
  "resources": {},
  "timeout": {}
}
```

That means a future Verifiers bump adding a non-`None`-defaulted `TaskData`
field changes every task hash in the universe. The preflight test pins the four
fixture hashes indirectly (via the two-load equality and the join to
`results.jsonl`), but a bump ticket should also diff the wire-data shape above.

### Taskset iteration order

Deterministic and fully controlled by the author:

- `Taskset.load()` is the subclass hook and may be a generator. Its yield order
  *is* the iteration order.
- `Taskset.__iter__` wraps `load()`, applying the config-level system-prompt
  override and then any *view transform*. It adds no ordering of its own.
- `head(n)` is `itertools.islice(tasks, n)` — literally the first `n` in load
  order. This is exactly decision 0001's "membership = first `num_tasks` tasks
  in Taskset iteration order", and it is what the CLI uses for `--num-tasks`.
- `shuffle(seed=None)` exists and materializes the taskset before shuffling
  under a module-level `SEED = 0`. **Decision 0001 forbids calling it**, and the
  CLI only reaches it via `--shuffle`, which Techtree must never pass.

Confirmed empirically: `head(2)` yielded task hashes identical to the first two
of the full iteration, with `idx` `[0, 1]`, and the `validate` run recorded
`task_position` `0` and `1` against those same hashes.

### `@vf.reward` and `Task[TaskData]` generics — spec §22.5 works as sketched

Both work at runtime on Python 3.12.

`Task` is declared `Generic[DataT, StateT, ConfigT]`, but `StateT` and `ConfigT`
carry PEP 696 defaults (via `typing_extensions.TypeVar`), so the spec's
single-argument `vf.Task[ProcedureTransferData]` subscription is valid. Likewise
`Taskset` is `Generic[TaskT, TasksetConfigT]`, matching
`vf.Taskset[ProcedureTransferTask, vf.TasksetConfig]` exactly.

`Task.data_type()` and `Task.config_type()` recover the concrete parameters —
observed `PreflightData` and `TaskConfig` respectively.

`@vf.reward` decorates an **async instance method**; it is discovered through
`task.hooks("reward")` and invoked by `await task.score(trace, runtime)`, which
writes into `trace.rewards` as `Reward(score=..., weight=...)` (default weight
`1.0`). `runtime` may be `None`, in which case any reward whose signature has a
non-defaulted `runtime` parameter is skipped with an INFO log.

`vf.Trace` exposes the `last_reply` property the spec's `exact_match` sketch
uses (last assistant message content, stripped, `""` when there is none).

One constructor detail the spec sketch omits: `vf.Trace` requires an `agent`
argument. Constructing one by hand needs
`agent=vf.AgentInfo(config=vf.AgentConfig(), name=..., trainable=False)`. This
only matters for tests that build traces directly; the CLI does it internally.

The spec's `async def validate(self, runtime: vf.Runtime) -> bool` signature is
correct — that is the exact base signature, and the `validate` CLI awaits it
under `config.timeout.total` after awaiting `setup`.

### Console-script names the engine venv exposes

See C3 above. Techtree needs `<engine-venv>/bin/validate`; `<engine-venv>/bin/eval`
is the v1 evaluation entry point for WP6. The `vf-*` scripts are v0 legacy.

---

## What PR9–PR12 must do differently

1. `VerifiersValidationRunner.parse_summary` projects the nested `outcomes`
   object into the flat `UpstreamValidationSummary` (C1). It must tolerate a
   missing `checks` key.
2. `VerifiersValidationRunner.run` derives pass/fail from `summary.json`, never
   from the process exit code (C2).
3. `EngineRunner` invokes `<engine-venv>/bin/validate` by absolute path (C3).
4. The pinned invocation adds `--rich false` so captured output is log lines
   rather than a dashboard.
5. `--runtime.type subprocess` is mandatory — the upstream default is docker.
6. `validation_artifacts` digests exactly `config.toml`, `results.jsonl`,
   `summary.json`, `validate.log`.
7. `results.jsonl.task_key` is the raw task hash and is the join key back to
   `TasksetLock.ordered_task_hashes` (after `normalize_verifiers_task_hash`).
8. `summary["checks"]["gold"]` / `["setup"]` feed the `upstream_gold` and
   `upstream_setup` checks in spec §21.5.

No change is needed to spec §22.5's taskset sketch, to the §22.6 `__init__.py`
export, or to decision 0001's task-hash boundary — all three match the pin.

---

## Rerunning this preflight

`tests/preflight/test_verifiers_contract.py` is marked `preflight` and excluded
from the default test run. It needs network access to github.com and PyPI.

Default mode builds its own throwaway venv per pytest session:

```bash
make verifiers-preflight
```

To reuse an already-built engine venv (faster during engine work):

```bash
TECHTREE_PREFLIGHT_ENGINE_PYTHON=/path/to/engine/.venv/bin/python \
  uv run pytest -m preflight tests/preflight
```

Either way the test reads the installed distribution's `direct_url.json` and
fails unless the recorded commit is exactly the pin, so a stale or wrong venv
cannot silently prove the wrong thing.
