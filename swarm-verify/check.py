"""The Swarm Verify checks (README.md beside this file). check.sh runs it.

check.py            every model with Everystate, the reference implementation's two logs and
                    the 128-worker run, each against the result it must give
check.py tlc        every model with TLC as well, and the two checkers' results compared
check.py measure    the measured limits: larger model bounds and larger runs, timed
check.py fixtures   rewrites conformance/*.jsonl from the reference implementation
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from sim import late_commit, swarm

HERE = Path(__file__).resolve().parent
MODELS = HERE / "models"
FIXTURES = HERE / "conformance"
BUILD = HERE / "_build"
EVERYSTATE = HERE / "node_modules" / ".bin" / "everystate"
TLA2TOOLS = "https://github.com/tlaplus/tlaplus/releases/download/v1.7.4/tla2tools.jar"
TLA2TOOLS_SHA256 = "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88"
SEED = 1

# Each model configuration and the result it must give: (spec, configuration, outcome, property).
MODEL_CHECKS = [
    ("TaskLease", "TaskLease", "ok", None),
    ("TaskLease", "TaskLeaseUnfenced", "invariant", "NoStaleOverwrite"),
    ("TaskLease", "TaskLeaseUnfencedCurrent", "invariant", "ResultFromCurrentLease"),
    ("BudgetReserve", "BudgetReserve", "ok", None),
    ("BudgetReserve", "BudgetReserveLimit2", "ok", None),
    ("BudgetReserve", "BudgetReserveCheckThenReserve", "invariant", "WithinLimit"),
    ("BudgetReserve", "BudgetReserveRetryTwice", "invariant", "OnePerLease"),
    ("BudgetReserve", "BudgetReserveLeak", "invariant", "NoReservationOutlivesLease"),
    ("BudgetReserve", "BudgetReserveLeakLiveness", "liveness", "EveryReservationEnds"),
    ("Cancel", "Cancel", "ok", None),
    ("Cancel", "CancelMessageOnly", "liveness", "CancelStopsEveryChild"),
    ("Cancel", "CancelMessageOnlyLate", "invariant", "NoWorkAfterCancel"),
]
EXIT = {"ok": 0, "invariant": 12, "liveness": 13}

# The reference implementation's logs: (log, configuration, exit, line the check stops at).
LATE_COMMIT_CHECKS = [
    ("late-commit-unfenced.jsonl", "TaskLeaseRun", 20, 6),
    ("late-commit-fenced.jsonl", "TaskLeaseRun", 0, None),
    ("late-commit-unfenced.jsonl", "TaskLeaseRunUnfenced", 12, 6),
]

failures = []


def expect(ok, what):
    if not ok:
        failures.append(what)
        print(f"  FAILED: {what}")


def measured(command, cwd=HERE):
    """Runs a command; returns its exit code, output, seconds and peak memory in MB."""
    start = time.perf_counter()
    child = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output = child.stdout.read()
    child.stdout.close()
    _, status, usage = os.wait4(child.pid, 0)
    # ru_maxrss is in bytes on macOS and in kilobytes on Linux.
    peak = usage.ru_maxrss / (1 << 20 if sys.platform == "darwin" else 1 << 10)
    return os.waitstatus_to_exitcode(status), output, time.perf_counter() - start, peak


def last_json(output):
    return json.loads(output.strip().splitlines()[-1])


def everystate(spec, config):
    code, output, seconds, peak = measured(
        [str(EVERYSTATE), "-json", "-workers", "1", "-config", f"{config}.cfg", f"{spec}.tla"], cwd=MODELS
    )
    return code, last_json(output), seconds, peak


def conform(trace, spec, config, *options):
    code, output, seconds, peak = measured(
        [
            str(EVERYSTATE),
            "conform",
            "-json",
            *options,
            "-trace",
            str(trace),
            "-config",
            str(config),
            str(MODELS / f"{spec}.tla"),
        ]
    )
    return code, last_json(output), seconds, peak


def table(header, rows):
    widths = [max(len(str(cell)) for cell in column) for column in zip(header, *rows, strict=True)]
    for row in [header, *rows]:
        print("  " + "  ".join(str(cell).ljust(w) for cell, w in zip(row, widths, strict=True)).rstrip())


def check_models():
    print("Model checking with Everystate")
    rows = []
    for spec, config, outcome, prop in MODEL_CHECKS:
        code, result, seconds, _ = everystate(spec, config)
        # Each configuration has at most one PROPERTY, which Everystate does not always name.
        broken = result.get("name", prop) if result["status"] != "ok" else "-"
        rows.append(
            [
                config,
                result["status"],
                broken,
                result["distinct"],
                result["generated"],
                result["depth"],
                f"{seconds:.2f}",
            ]
        )
        expect(
            code == EXIT[outcome] and result["status"] == outcome,
            f"{config}: expected {outcome}, got {result['status']} (exit {code})",
        )
        if outcome == "invariant":
            expect(result["name"] == prop, f"{config}: expected {prop} broken, got {result['name']}")
    table(["configuration", "outcome", "property broken", "distinct", "generated", "depth", "seconds"], rows)


def check_late_commit():
    print("\nThe reference implementation's late-commit run, against TaskLease")
    for name, fenced in (("late-commit-unfenced.jsonl", False), ("late-commit-fenced.jsonl", True)):
        expect(
            (FIXTURES / name).read_text() == late_commit.run(fenced),
            f"conformance/{name} is not what sim/late_commit.py writes (check.py fixtures rewrites it)",
        )
    rows = []
    for name, config, code_wanted, line_wanted in LATE_COMMIT_CHECKS:
        code, result, seconds, _ = conform(FIXTURES / name, "TaskLease", MODELS / f"{config}.cfg")
        line = result.get("line", "-")
        rows.append([name, config, code, result["status"], line, f"{seconds:.2f}"])
        expect(
            code == code_wanted and (line_wanted is None or line == line_wanted),
            f"{name} against {config}: expected exit {code_wanted} at line {line_wanted}, "
            f"got exit {code} at line {line}",
        )
    table(["log", "configuration", "exit", "result", "line", "seconds"], rows)


def write_config(path, constants, invariants):
    """A configuration like models/*.cfg: a state with no next step is a finished run."""
    lines = ["SPECIFICATION Spec", "CONSTANTS", *(f"  {k} = {v}" for k, v in constants.items())]
    path.write_text("\n".join([*lines, f"INVARIANTS {invariants}", "CHECK_DEADLOCK FALSE", ""]))


def swarm_configs(settings):
    """BudgetReserve for the whole run, and for one task of it, at the run's own bounds."""
    rules = {"AtomicAdmit": "TRUE", "Idempotent": "TRUE", "ReleaseOnExpiry": "TRUE"}
    invariants = "WithinLimit OnePerLease NoReservationOutlivesLease LeaseSafe"
    whole = BUILD / f"BudgetReserveSwarm-{settings.workers}-{settings.tasks}.cfg"
    write_config(
        whole,
        {
            "NumAgents": settings.workers,
            "NumTasks": settings.tasks,
            "MaxEpoch": settings.max_epoch,
            "Limit": settings.limit,
            **rules,
        },
        invariants,
    )
    # One task's leases use at most one unit each, so its own limit is its number of leases.
    one = BUILD / "BudgetReserveSwarmTask.cfg"
    write_config(
        one,
        {
            "NumAgents": settings.workers,
            "NumTasks": 1,
            "MaxEpoch": settings.max_epoch,
            "Limit": settings.max_epoch,
            **rules,
        },
        invariants,
    )
    return whole, one


def project(lines, task):
    """The lines of one task, written as a run of a store holding that task alone (task 1)."""
    out = []
    for line in lines:
        if line["task"] != task:
            continue
        params = {"Claim": [line["params"][0], 1], "Expire": [1]}.get(line["action"], line["params"])
        state = {name: {"1": values[str(task)]} for name, values in line["state"].items()}
        out.append({**line, "params": params, "state": state})
    return out


def write_lines(path, lines):
    path.write_text("".join(json.dumps(line, separators=(",", ":")) + "\n" for line in lines))


def conform_tasks(lines, tasks, config, label, *options):
    """Every task's projection against the one-task model, side by side. Returns
    {task: (exit, result, seconds)} and the wall time."""
    folder = BUILD / label
    folder.mkdir(parents=True, exist_ok=True)
    for t in tasks:
        write_lines(folder / f"task-{t}.jsonl", project(lines, t))
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as pool:
        results = pool.map(
            lambda t: (t, conform(folder / f"task-{t}.jsonl", "BudgetReserve", config, *options)), tasks
        )
        by_task = {t: (code, result, seconds) for t, (code, result, seconds, _) in results}
    return by_task, time.perf_counter() - start


def swarm_run(settings, fenced):
    """The seeded run, checked to be the same when repeated, its log written to _build/."""
    label = "fenced" if fenced else "unfenced"
    run = swarm.run(settings, SEED, fenced)
    text = run.log.text()
    expect(text == swarm.run(settings, SEED, fenced).log.text(), f"the {label} run is not deterministic")
    log_path = BUILD / f"swarm-{settings.workers}-{settings.tasks}-{label}.jsonl"
    log_path.write_text(text)
    return run, log_path


def swarm_tasks(settings):
    return list(range(1, settings.tasks + 1))


def check_swarm():
    settings = swarm.Settings()
    print(f"\nThe {settings.workers}-worker run: {settings.tasks} tasks, seed {SEED}, against BudgetReserve")
    whole, one = swarm_configs(settings)
    rows = []
    for fenced in (True, False):
        label = "fenced" if fenced else "unfenced"
        run, log_path = swarm_run(settings, fenced)
        digest = hashlib.sha256(log_path.read_bytes()).hexdigest()[:12]
        tally = run.tally
        print(
            f"  {label}: {tally['log lines']} log lines (sha256 {digest}), {tally['ticks']} ticks; "
            f"{tally['takeovers']} takeovers, {tally['pauses past the lease']} of {tally['pauses']} pauses "
            f"past the lease, {tally['crashes']} crashes, {tally['lost replies']} lost replies, "
            f"{tally['reserve calls with no room']} reserve calls with no room, {tally['cancels']} cancels "
            f"with {tally['cancel messages dropped']} of their messages dropped; late commits: "
            f"{tally['late commits accepted']} accepted, {tally['late commits refused']} refused; "
            f"{tally['tasks committed']} tasks committed, {tally['tasks canceled']} canceled, "
            f"{tally['units spent']} of {settings.limit} units spent, "
            f"{tally['units still reserved']} still reserved"
        )

        # The unfenced run's whole log is checked by `check.py measure`: Everystate takes about a
        # minute to report a mismatch in a state this large.
        if fenced:
            code, result, seconds, peak = conform(log_path, "BudgetReserve", whole)
            rows.append([label, "whole log", 1, code, result["status"], f"{seconds:.2f}", f"{peak:.0f}"])
            expect(code == 0, f"the fenced run's log does not conform: {result.get('message')}")

        by_task, wall = conform_tasks(run.log.lines, swarm_tasks(settings), one, f"tasks-{label}")
        failing = {t for t, (code, _, _) in by_task.items() if code != 0}
        late_tasks = {t for _, t in run.late_accepted}
        rows.append(
            [
                label,
                "each task",
                len(by_task),
                "0" if not failing else "20",
                f"{len(by_task) - len(failing)} conform, {len(failing)} do not",
                f"{wall:.2f}",
                "-",
            ]
        )
        expect(all(by_task[t][0] in (0, 20) for t in by_task), f"{label}: a task's check gave no verdict")
        expect(
            failing == late_tasks,
            f"{label}: the tasks that do not conform {sorted(failing)} are not the tasks with an "
            f"accepted late commit {sorted(late_tasks)}",
        )
        for t in sorted(failing):
            print(f"  task {t}, line {by_task[t][1]['line']} of its own log: {by_task[t][1]['message']}")
    table(["run", "checked", "logs", "exit", "result", "seconds", "peak MB"], rows)


def tla2tools():
    jar = BUILD / "tla2tools-1.7.4.jar"
    if not jar.exists():
        data = urllib.request.urlopen(TLA2TOOLS).read()
        if hashlib.sha256(data).hexdigest() != TLA2TOOLS_SHA256:
            sys.exit(f"{TLA2TOOLS} does not have the pinned digest {TLA2TOOLS_SHA256}")
        jar.write_bytes(data)
    return jar


def tlc(jar, spec, config):
    # A folder for each configuration: TLC names its own folder inside by the second it
    # started, and refuses to start when that folder exists.
    code, output, seconds, _ = measured(
        [
            "java",
            "-XX:+UseParallelGC",
            "-cp",
            str(jar),
            "tlc2.TLC",
            "-workers",
            "1",
            "-metadir",
            str(BUILD / "tlc-states" / config),
            "-config",
            f"{config}.cfg",
            f"{spec}.tla",
        ],
        cwd=MODELS,
    )
    counts = re.findall(r"^(\d+) states generated, (\d+) distinct states found", output, re.MULTILINE)
    invariant = re.search(r"^Error: Invariant (\w+) is violated", output, re.MULTILINE)
    if invariant:
        outcome, name = "invariant", invariant.group(1)
    elif "Temporal properties were violated" in output:
        outcome, name = "liveness", None
    else:
        outcome, name = ("ok" if code == 0 else f"exit {code}"), None
    generated, distinct = (int(n) for n in counts[-1]) if counts else (None, None)
    return code, outcome, name, generated, distinct, seconds


def check_tlc():
    if shutil.which("java") is None:
        sys.exit("TLC needs Java 17 or later on PATH.")
    jar = tla2tools()
    print("\nThe same configurations with TLC 2.19 (tla2tools.jar 1.7.4), one worker, beside Everystate")
    rows = []
    for spec, config, outcome, _ in MODEL_CHECKS:
        _, ours, es_seconds, _ = everystate(spec, config)
        code, theirs, name, generated, distinct, seconds = tlc(jar, spec, config)
        agree = (
            theirs == ours["status"]
            and generated == ours["generated"]
            and distinct == ours["distinct"]
            and (theirs != "invariant" or name == ours["name"])
        )
        rows.append(
            [
                config,
                theirs,
                name or "-",
                distinct,
                generated,
                f"{seconds:.2f}",
                f"{es_seconds:.2f}",
                "yes" if agree else "NO",
            ]
        )
        expect(code == EXIT[outcome], f"{config}: TLC exited {code}, expected {EXIT[outcome]}")
        expect(agree, f"{config}: TLC and Everystate disagree")
    table(
        [
            "configuration",
            "TLC outcome",
            "property",
            "distinct",
            "generated",
            "TLC seconds",
            "Everystate seconds",
            "same",
        ],
        rows,
    )


def measure():
    print("Model checking at larger bounds: TaskLease, fenced, Everystate on one thread")
    rows = []
    for agents, tasks, epochs in [(3, 2, 3), (3, 3, 3), (4, 2, 3), (4, 3, 3), (4, 3, 4)]:
        config = BUILD / f"TaskLease-{agents}-{tasks}-{epochs}.cfg"
        write_config(
            config,
            {"NumAgents": agents, "NumTasks": tasks, "MaxEpoch": epochs, "Fenced": "TRUE"},
            "TypeOK OneOwnerPerEpoch NoStaleOverwrite ResultFromCurrentLease",
        )
        code, output, seconds, peak = measured(
            [str(EVERYSTATE), "-json", "-workers", "1", "-config", str(config), "TaskLease.tla"], cwd=MODELS
        )
        result = last_json(output)
        expect(code == 0, f"TaskLease at {agents} agents, {tasks} tasks, {epochs} leases: {result['status']}")
        rows.append(
            [agents, tasks, epochs, result["status"], result["distinct"], f"{seconds:.1f}", f"{peak:.0f}"]
        )
    table(["agents", "tasks", "leases per task", "outcome", "distinct states", "seconds", "peak MB"], rows)

    print(f"\nFenced runs at more tasks and more workers, seed {SEED}, against BudgetReserve")
    rows = []
    # (workers, tasks, whether to check the whole log): at 512 by 512 only each task is checked.
    for workers, tasks, check_whole in [
        (128, 64, True),
        (128, 128, True),
        (128, 256, True),
        (128, 512, True),
        (256, 128, True),
        (512, 128, True),
        (512, 512, False),
    ]:
        settings = replace(swarm.Settings(), workers=workers, tasks=tasks, limit=tasks)
        whole, one = swarm_configs(settings)
        run, log_path = swarm_run(settings, fenced=True)
        row = [workers, tasks, len(run.log.lines), "-", "-", "-"]
        if check_whole:
            code, result, seconds, peak = conform(log_path, "BudgetReserve", whole)
            expect(
                code == 0,
                f"the fenced {workers} by {tasks} run's log does not conform: {result.get('message')}",
            )
            row[3:] = [result["status"], f"{seconds:.1f}", f"{peak:.0f}"]
        by_task, wall = conform_tasks(run.log.lines, swarm_tasks(settings), one, f"tasks-{workers}-{tasks}")
        conforming = sum(code == 0 for code, _, _ in by_task.values())
        expect(
            conforming == tasks,
            f"{tasks - conforming} tasks of the fenced {workers} by {tasks} run do not conform",
        )
        # Without the lines the scheduler writes (crashes and lost replies): a fleet that records
        # only its store's steps, checked with up to one unrecorded step before each line.
        store_only = [line for line in run.log.lines if line["action"] not in ("Crash", "LoseReply")]
        hidden, hidden_wall = conform_tasks(
            store_only, swarm_tasks(settings), one, f"tasks-{workers}-{tasks}-store-only", "-hidden", "1"
        )
        hidden_conforming = sum(code == 0 for code, _, _ in hidden.values())
        rows.append(
            [
                *row,
                f"{conforming}/{tasks}",
                f"{wall:.1f}",
                f"{hidden_conforming}/{tasks}",
                f"{hidden_wall:.1f}",
            ]
        )
    table(
        [
            "workers",
            "tasks",
            "log lines",
            "whole log",
            "seconds",
            "peak MB",
            "tasks conforming",
            "seconds",
            "store lines only, -hidden 1",
            "seconds",
        ],
        rows,
    )

    settings = swarm.Settings()
    whole, _ = swarm_configs(settings)
    run, log_path = swarm_run(settings, fenced=False)
    first_late = run.late_accepted[0][0]
    print(f"\nThe unfenced {settings.tasks}-task run's whole log (first late commit: line {first_late})")
    before = BUILD / "swarm-unfenced-before-late.jsonl"
    write_lines(before, run.log.lines[: first_late - 1])
    rows = []
    for name, path in (("up to the line before", before), ("whole log", log_path)):
        code, result, seconds, peak = conform(path, "BudgetReserve", whole)
        rows.append([name, code, result["status"], result.get("line", "-"), f"{seconds:.1f}", f"{peak:.0f}"])
    expect(
        rows[0][1] == 0 and rows[1][1] == 20 and rows[1][3] == first_late,
        f"the unfenced run's log should conform up to line {first_late} and stop there",
    )
    table(["checked", "exit", "result", "line", "seconds", "peak MB"], rows)

    print("\nThe whole log of a fenced run, store lines only, with -hidden 1")
    rows = []
    for tasks in [8, 16]:
        settings = replace(swarm.Settings(), tasks=tasks, limit=tasks)
        whole, _ = swarm_configs(settings)
        run, _ = swarm_run(settings, fenced=True)
        path = BUILD / f"swarm-{settings.workers}-{tasks}-store-only.jsonl"
        write_lines(path, [line for line in run.log.lines if line["action"] not in ("Crash", "LoseReply")])
        code, result, seconds, peak = conform(path, "BudgetReserve", whole, "-hidden", "1")
        rows.append(
            [
                tasks,
                code,
                result["status"],
                f"{result['matched']} of {result['observations']}",
                f"{seconds:.1f}",
                f"{peak:.0f}",
            ]
        )
    table(["tasks", "exit", "result", "lines matched", "seconds", "peak MB"], rows)


def write_fixtures():
    for name, fenced in (("late-commit-unfenced.jsonl", False), ("late-commit-fenced.jsonl", True)):
        (FIXTURES / name).write_text(late_commit.run(fenced))
        print(f"wrote conformance/{name}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode not in ("check", "tlc", "measure", "fixtures"):
        sys.exit(__doc__)
    if mode == "fixtures":
        write_fixtures()
        return
    BUILD.mkdir(exist_ok=True)
    if mode == "measure":
        measure()
    else:
        check_models()
        check_late_commit()
        check_swarm()
    if mode == "tlc":
        check_tlc()
    if failures:
        sys.exit(f"\n{len(failures)} check(s) failed.")
    print("\nEvery check gave the result it must.")


if __name__ == "__main__":
    main()
