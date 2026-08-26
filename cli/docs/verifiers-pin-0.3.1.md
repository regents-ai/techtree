# Verifiers pin — released v0.3.1 preflight findings

Ticket: `techtree-python-0a8` (move the pinned engine off a development commit).
Successor to `docs/verifiers-pin.md`, which recorded the same contract against
`0.3.1.dev21`. Read that document first if you need the original reasoning; this
one records only what is true of the released tag and, where the two disagree,
says so explicitly.

```text
PrimeIntellect-ai/verifiers
b2e4e8157783b2c0dffc7821044c87f29f1c3ccf        (release v0.3.1)
supersedes 7e1c47d24d055aae587ee8259f77a3e8e193513a  (0.3.1.dev21)
```

Everything below was observed against that commit and nothing else. Resolved
distribution: `verifiers 0.3.1`, `Requires-Python: <3.14,>=3.11`, installed into
a throwaway `uv` venv on Python 3.12 (macOS arm64).

Reproduce with `make verifiers-preflight`
(`tests/preflight/test_verifiers_contract.py`, 24 checks, all green).

Recorded VCS metadata, which is how the preflight proves the pin offline:

```json
{"url":"https://github.com/PrimeIntellect-ai/verifiers","vcs_info":{"vcs":"git","commit_id":"b2e4e8157783b2c0dffc7821044c87f29f1c3ccf","requested_revision":"b2e4e8157783b2c0dffc7821044c87f29f1c3ccf"}}
```

---

## The headline

The **data** contract did not move. The **filesystem and CLI** contract did.

Task hashes, `summary.json`, `results.jsonl`, the outcome vocabulary, the exit
status semantics, the console-script names, taskset iteration order and
`head(n)` are all byte-for-byte what `docs/verifiers-pin.md` recorded. What
changed is where a run's files land, what the resolved configuration is called
and in what format, and — for `eval` only — whether the run is hosted in-process
or through a worker pool by default.

Proof that the hashes did not move, since it is the only fact that could have
invalidated the committed membership on its own: the 36 task hashes of
`procedure-transfer-v1` were computed under both commits and compared against
the certified catalog.

```text
dev21 hashes == v0.3.1 hashes                          : True (36)
v0.3.1 hashes == catalog/validation-evidence/hello-world-climb.json : True (36)
```

The four fixture-taskset hashes recorded in `docs/verifiers-pin.md` §4 also
reproduce unchanged, and the hashed wire data still carries the same ten keys
in the same shape.

---

## CRITICAL — deviations from what `docs/verifiers-pin.md` recorded

### D0. `verifiers.v1.utils.install` no longer exists

This is the import that broke the whole preflight, and it is the reason this
ticket exists at all. The old module exported three things:

```python
env_name(env_id)        # strip a Hub org/ and @version
env_module(env_id)      # env_name, hyphens -> underscores
ensure_installed(env_id)  # install a Hub id on demand, return the module name
```

Both `verifiers/v1/utils/install.py` and `verifiers/v1/utils/install_utils.py`
are gone from the released tag, and nothing in `verifiers.v1.__all__` replaces
them by name. What happened to each:

* `env_module` — the rule survives, **inlined** in the plugin importer.
  `verifiers/v1/utils/loaders.py::_import_plugin`:

  ```python
  name = plugin_id.rsplit("/", 1)[-1].split("@", 1)[0]
  module = name.replace("-", "_").lower()
  ```

  The public observable is `verifiers.v1.import_taskset(id)`, which returns the
  module actually imported. The preflight now asserts on that instead of on a
  computed string — a stronger check than the one it replaces.

* `env_name` — **removed as a concept.** `TasksetConfig.name` used to be
  `env_name(self.id)`; it is now `self.id`, verbatim. A Hub-style
  `org/name@version` id therefore keeps its org and version in every display
  string and in the auto-generated run name. Techtree only ever uses local ids,
  so nothing of ours depends on the stripping.

* `ensure_installed` and the whole Hub auto-install path — **gone from v1.**
  `TasksetConfig.id`'s own docstring changed from "Local package or Hub
  `org/name[@version]`" to "Installed taskset package". A v1 taskset must
  already be installed; `_import_plugin` raises `ModuleNotFoundError` with an
  authoring hint rather than fetching anything. Techtree installs its taskset
  into the engine venv itself, so this is a capability we never used.

How this was established: by reading the installed package, not the release
notes. `verifiers/v1/utils/` no longer lists `install.py` or `install_utils.py`;
`grep` for `env_name`/`env_module`/`ensure_installed` across the released
distribution finds them only under `verifiers/legacy/`; and the diff of
`configs/taskset.py` between the two commits shows the `env_name` call being
deleted from `TasksetConfig.name`.

### D1. A run's four files are still four, but two of them moved

`docs/verifiers-pin.md` §7 recorded a flat run directory:

```text
config.toml
results.jsonl
summary.json
validate.log
```

The released tag writes:

```text
configs/resolved/validate.json
logs/validate.log
results.jsonl
summary.json
```

Two consequences, both for `validation_artifacts`:

1. **The resolved configuration is JSON, not TOML, and it is nested two levels
   down.** Upstream's reason (`verifiers/v1/cli/output.py`) is that JSON keeps
   nulls, so an explicitly-`None` setting round-trips on re-parse. The file is
   re-readable with `@ <run-dir>/configs/resolved/validate.json`.
2. **The log moved under `logs/`.** For `validate` it is a single
   `logs/validate.log`. (`eval` goes further — see D5.)

`shuffle` is still recorded, and still `false`; it is now
`"shuffle": false` in the JSON rather than `shuffle = false` in the TOML.
Decision 0001's prohibition is unaffected.

The `.tmp`-sibling-then-`replace` write is unchanged, so a `.tmp` file is still
transient and never present after the process exits.

### D2. `--output-dir` no longer names the directory a run writes into

This is the change most likely to bite silently. `--output-dir` now names the
directory runs are **grouped** under; the run itself lands in
`<output-dir>/<run.dir>`. `run.dir` defaults to `run.name`, which
auto-generates as `<taskset>--validate--<8 random hex>`:

```text
$ validate techtree-preflight-taskset -n 2 --runtime.type subprocess \
      --output-dir out1 --rich false
INFO results: out1/techtree-preflight-taskset--validate--86c1933d
```

An engine that keeps passing `--output-dir <run-dir>` and then reads
`<run-dir>/summary.json` finds nothing, and never finds the same path twice.
**`EngineRunner` must pass `--run.name` explicitly.** With it the layout is
exactly what Techtree wants:

```bash
<engine-venv>/bin/validate <taskset-id> \
  --num-tasks <n> \
  --runtime.type subprocess \
  --output-dir <parent> \
  --run.name <run-dir-name> \
  --rich false
```

`run.name` also appears in the saved configuration, so pinning it is what makes
`configs/resolved/validate.json` reproducible run-to-run; left unset, the random
suffix lands in the file and every digest differs.

### D3. A run directory that already holds results is refused

New behaviour, and a good one:

```text
run directory out3/run already contains results - append --resume to re-run
its missing/errored tasks, overwrite it with --clean, or pick another --run.name
```

Because Techtree now names its run directories (D2), it will meet this every
time it validates the same taskset into the same run tree twice. The engine
must either use a fresh directory per validation or pass `--clean`.

`--resume` also changed shape: it was `--resume <output-dir>` and took no other
arguments; it is now a boolean applied to a config file,
`validate @ <run-dir>/configs/resolved/validate.json --resume`. Note that the
CLI's own usage line prints `<run-dir>/configs/validate.json`, which does not
exist — the resolved config is one level deeper, under `resolved/`. Observed:
the documented path fails with "Config file not found", the real one resumes
and exits 0.

### D4. The default runtime is now `prime`, for both `validate` and every agent

`docs/verifiers-pin.md` recorded "`--runtime.type` … The default is **docker**".
It is now **prime**:

* `ValidateConfig.runtime` moved from `DockerConfig()` to `PrimeConfig()`;
* `AgentConfig.runtime` moved from `SubprocessConfig()` to `PrimeConfig()`.

This is the release note "prime sandboxes is the default runtime, not docker /
subprocess", and it is a change of *default only*. See the Docker section below
for what it does and does not mean for us.

### D5. `eval` — the Techtree-compiled configuration is REJECTED as it stands

`validate` ports cleanly. `eval` does not, and one field blocks everything:

```text
╭─ Config file error ──────────────────────────────────────────────────────────╮
│ Failed to validate config:                                                   │
│ 1 validation error for EvalConfig                                            │
│ --rich                                                                       │
│ Input should be a valid dictionary or instance of RichConfig (got False)     │
╰──────────────────────────────────────────────────────────────────────────────╯
```

`EvalConfig.rich` changed from `bool` to `RichConfig | None`. TOML has no null
literal, so **the dashboard can no longer be turned off from a TOML
configuration file at all**. That directly contradicts
`src/techtree/verifiers/config.py`, whose locked-down `rich` exists precisely
so that "leave the dashboard on" cannot be spelled.

**SETTLED, and the guarantee did not have to move.** The problem was the file
*format*, not the control surface. The engine picks its parser from the file's
extension and reads JSON as readily as TOML — its own usage line resumes a run
from `@ <run-dir>/configs/resolved/eval.json` — and JSON has a null literal. So
Techtree now compiles to `input.json` with `"rich": null`, the setting stays
unspellable-except-safely in a file, and nothing was added to argv.

Three things were measured against the released engine before this was
decided, and each one matters:

```text
rich key omitted        -> resolved "rich": {"show_logs": false}   dashboard ON, logs suppressed
"rich": null in a file  -> resolved "rich": null                   dashboard off, logs to console
"rich": false in a file -> REFUSED at parse time
```

The dangerous case is therefore an **omitted** key, not a `true` one, which is
why `config_to_json_bytes` writes this one null explicitly while every other
unset optional stays absent. `push` is untouched by all of this: still a plain
`bool`, still defaulting to `True`, still honouring the `false` Techtree
writes, and still refused by the compiler as anything else.

What is already known to have moved on the `eval` side, from reading the
released `EvalConfig` and from one hand-run model-free evaluation:

* `serve` is now the **default** path (`serve: ServeConfig | None`, elastic
  worker pool); `--server` is gone and `--no-serve` selects the in-process run
  Techtree has always used. A run that does not say `--no-serve` is hosted
  through a worker pool.
* `output_dir`/`run.dir` split exactly as in D2, with the same random suffix.
* The run's files are no longer `{config.toml, traces.jsonl, eval.log}`.
  Observed from a real model-free run:

  ```text
  configs/eval.toml              <- the launch @ TOML, copied verbatim (new)
  configs/resolved/eval.json     <- the resolved config
  logs/attempt_1/eval.log
  logs/latest -> attempt_1       <- a SYMLINK inside the run tree
  traces.jsonl
  ```

  Two of those are new hazards for artifact digesting: a verbatim copy of the
  launch file, and a symlink.
* `EvalConfig.env_id` and `EvalConfig.worker_max_concurrent` were removed.
* `TraceTask` gained `key` alongside `hash`; a hand-built `Trace` should pass
  both. `Task.key` defaults to `Task.hash` and is equal to it for every task we
  own.
* `push` is unchanged: still `bool`, still defaults to `True`, still honours
  `push = false` in the file.
* The credential still does not leak. A full model-free run with
  `PRIME_API_KEY=sk-preflight-secret-value` left that string in none of the
  files the run wrote.

---

## What did NOT change

Everything in this section was re-observed, not assumed.

### C0 holds — `results.jsonl` row order is completion order

Two-task run, rows persisted with `task_position` 1 before 0. Consumers must
still join on `task_key`/`task_position` and never on line position, and the
raw bytes of `results.jsonl` are still not reproducible across runs.

### C1 holds — `summary.json` is still nested

Byte-identical shape to what `docs/verifiers-pin.md` recorded, including the
two fields the spec does not model:

```json
{
  "checks": {
    "gold":  {"error": 0, "invalid": 0, "missing": 0, "timeout": 0, "valid": 2},
    "setup": {"error": 0, "invalid": 0, "missing": 0, "timeout": 0, "valid": 2}
  },
  "mode": "all",
  "outcomes": {"error": 0, "invalid": 0, "missing": 0, "timeout": 0, "valid": 2},
  "owed": 0,
  "recorded": 2,
  "terminal": 2,
  "total": 2,
  "valid_rate": 1.0
}
```

`parse_summary` still projects rather than validates, the `checks` block is
still present only in `mode = "all"`, and `--only-gold` / `--only-setup` still
omit it and report `"mode": "gold"` / `"setup"`.

### C2 holds — `validate` still exits 0 when every task fails

Observed with the fixture's failure switch: exit `0`, `outcomes.invalid == 2`,
`valid_rate == 0.0`. An unresolvable taskset id still exits non-zero (`1`).
Validity still comes from `summary.json` alone.

### C3 holds — the console script is still bare `validate`

The released `entry_points.txt` is character-identical to dev21's: `debug`,
`eval`, `gepa`, `init`, `replay`, `validate` on `verifiers.v1.cli.*`, and the
`vf-*` names on `verifiers.legacy.*`. Invoking by absolute path inside the
engine venv is still mandatory.

### Claims 1–7 of the original preflight

| # | Claim (spec §2.1) | v0.3.1 |
|---|---|---|
| 1 | The pinned commit installs | verified — clean install, no build steps |
| 2 | `TaskData`, `Task`, `Taskset` import from `verifiers.v1` | verified, same module paths |
| 3 | A package exported through `__all__` loads as a Taskset | verified (see D0 for how the id resolves) |
| 4 | Two loads produce identical task hashes | verified, and identical to dev21's |
| 5 | Base `Task.validate()` returns True by default | verified, still a coroutine |
| 6 | `validate` accepts the pinned command form | verified **with `--run.name` added** (D2) |
| 7 | Validation creates exactly the four expected files | verified, **at new paths** (D1) |
| 8 | Persisted summary matches the §11.9 parser contract | still refuted in exactly the way C1 describes |

### Task hashing, iteration order, generics and `@vf.reward`

`verifiers/v1/taskset.py` is byte-identical between the two commits, so
`load()`, `__iter__`, `head(n)` and `shuffle()` are unchanged; membership is
still "the first `num_tasks` in load order" and `--shuffle` is still the only
route to a reorder.

`verifiers/v1/task.py` changed in exactly three ways, none of which touches the
hash: the `network_allow` docstring, a new `key` property (defaulting to
`hash`), and a new `runtime_env()` hook returning `{}`. `TaskData`'s fields are
unchanged, which is why every hash reproduces.

`vf.Task[Data]` generics, `data_type()`, `config_type()`, `hooks("reward")`,
`await task.score(trace, runtime)` and `Trace.last_reply` all behave as
recorded.

---

## Docker: still accepted, still refused

The release note that reads worst — "prime sandboxes is the default runtime" —
changes a default we never take. Both halves were re-confirmed against the
released tag rather than assumed, because the refusal is ours and the
acceptance is theirs.

### Theirs: the compiled Docker block is accepted verbatim

`src/techtree/verifiers/compiler.py` emits an explicit `DockerRuntimeToml`.
Dry-running a Techtree-compiled baseline configuration against the released
`eval` resolves it unchanged (re-confirmed after D5 was settled, this time with
the configuration exactly as Techtree compiles it):

```json
{
  "allow": [],
  "block": ["*"],
  "type": "docker",
  "image": "python@sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff",
  "workdir": "/app",
  "cpu": 2.0,
  "memory": 4.0,
  "gpu": null,
  "disk": null
}
```

The discriminated union still accepts `subprocess | docker | prime | modal`, and
`DockerConfig`/`DockerRuntime` are still first-class. Only the default moved.

### Ours: anything that is not Docker is refused before a file is written

`_check_subject_is_executable` in the compiler, exercised against the released
tag with four campaigns identical but for the subject runtime type:

```text
docker      -> COMPILED
prime       -> REFUSED: the subject runtime is Docker
subprocess  -> REFUSED: the subject runtime is Docker
modal       -> REFUSED: the subject runtime is Docker
```

The refusal happens in Techtree, at compile time, and does not depend on
anything upstream chooses to default to.

### What "prime sandboxes as default" means for a participant with no Prime sandbox

Nothing, on the paths Techtree drives — and that is a property of our explicitness,
not of theirs.

* **Validation**: Techtree always passes `--runtime.type subprocess`. The
  default is never consulted.
* **Evaluation**: the compiled configuration always names
  `[env.subject.runtime] type = "docker"`. The default is never consulted.
* **If the default ever were consulted**, `PrimeRuntime` calls
  `ensure_prime_auth()`, which exits with
  `not authenticated with prime - run 'prime login' or set $PRIME_API_KEY`.
  So the failure mode for a participant without a Prime sandbox is a clear,
  immediate refusal to start — not a silent remote execution and not a
  surprise bill.

The participant's own credential requirement is unchanged: a Prime API key for
the **model**, which decision 0033 already fixes as the single serving provider,
and Docker on their machine for the **subject container**. A Prime *sandbox* is
not required and is never provisioned.

---

## What the engine must change

Ordered by whether the decision is mechanical or not.

Mechanical, and already done in the preflight:

1. Import `verifiers.v1.import_taskset` instead of
   `verifiers.v1.utils.install.{env_name, env_module}`; there is no `env_name`
   equivalent and none is needed (D0).
2. Pass `--run.name` on every `validate` invocation, and read the artifacts
   from `<output-dir>/<run.name>` (D2).
3. Digest `configs/resolved/validate.json`, `logs/validate.log`,
   `results.jsonl`, `summary.json` — the same four artifacts at new paths, one
   of them now JSON rather than TOML (D1).
4. Never write twice into one run directory (D3).

5. **Done** — the compiled configuration is emitted as JSON with `"rich": null`
   rather than TOML with `rich = false`, and the run's compiled input is
   `verifiers/<variant>/input.json` with media type `application/json`. The
   dry run also pins `--run.name`, because `--output-dir` alone leaves the
   resolved configuration under a randomly suffixed directory (D2). No
   guarantee moved to argv (D5).

Not mechanical, and still open:

6. `--no-serve` must be added to the **real** eval invocation, or Techtree
   silently starts running through the env-server worker pool. Confirmed still
   true against the released engine: a dry run of a Techtree-compiled config
   resolves `serve` to an elastic pool (D5).
7. The eval run's artifact set grew a verbatim copy of the launch config, a
   `logs/attempt_<n>/` directory and a `logs/latest` symlink, and the resolved
   configuration moved to `configs/resolved/eval.json` under a named run
   directory. `src/techtree/verifiers/outputs.py` still names the flat
   `config.toml`/`eval.log` layout, and `docs/verifiers-eval.md`'s three-file
   contract needs rewriting with it. This is one change with (6), not two: the
   files can only be found once the real invocation names its run directory
   (D5).

Nothing in decision 0001's task-hash boundary, spec §22.5's taskset sketch or
spec §22.6's `__init__.py` export needs to change. All three still match.

---

## Rerunning this preflight

Unchanged from `docs/verifiers-pin.md`:

```bash
make verifiers-preflight
```

or, against an already-built engine venv:

```bash
TECHTREE_PREFLIGHT_ENGINE_PYTHON=/path/to/engine/.venv/bin/python \
  uv run pytest -m preflight tests/preflight
```

The suite still reads the installed distribution's `direct_url.json` and fails
unless the recorded commit is exactly the pin.

State of the full preflight at the time of writing, so nobody mistakes an
unrelated red for this one:

* `test_verifiers_contract.py` — 24 of 24 green. This document's subject.
* `test_procedure_transfer_taskset.py` — 41 green, 4 red. **Pre-existing and
  unrelated to the pin**: the module restates the frozen dataset independently,
  and that restatement was not updated when the dataset was recalibrated to the
  24/12 split. The certified catalog's 36 task hashes match the package, not
  the test's table, so the test's table is the stale side.
* `test_subject_image_pin.py` — 2 green, 1 red. **Pre-existing and unrelated**:
  Docker Hub has re-pushed `python:3.11-slim`, so the tag no longer resolves to
  the recorded index digest.
* `test_verifiers_eval_contract.py` — still largely red, but no longer behind
  the `rich` blocker. Only the one test that exercises Techtree's own compiler
  and serializer,
  `test_a_techtree_compiled_configuration_is_accepted_by_the_pinned_engine`,
  was ported when D5 was settled. The rest write their own TOML documents
  against the dev21 run layout and belong with items 6 and 7 above; the
  integration suite's
  `tests/integration/test_eval_compile.py` covers the compiled configuration
  against a real installed engine in the meantime, and is green.
