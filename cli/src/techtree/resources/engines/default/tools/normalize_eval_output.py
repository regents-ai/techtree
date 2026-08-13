"""Turn raw eval output into the protocol projection. Spec 6.12, decisions 0003 A3.

The Verifiers evaluation writes ``traces.jsonl``: one complete Episode per
line, appended as episodes finish. Two things make it unusable as a scientific
record on its own. Its order is completion order, which varies run to run and
has nothing to do with the Campaign's committed task membership. And it is a
full upstream wire record — timings, host paths, message graphs, the whole
transcript — most of which is either non-deterministic or not something a
receipt should carry.

This helper extracts the part that is a claim: for each task, in membership
order, which subject ran it under which configuration, under which sampling
settings, at what recorded token cost, and what Verifiers scored it. Everything
else stays where it is. The normalizer does not replace
``traces.jsonl``; Techtree keeps the raw evidence and this projection side by
side, because a projection nobody can check against its source is an assertion
rather than evidence.

It belongs inside the engine bundle because it imports the pinned Verifiers
wire models and its reader. Reading a Trace with the version of Verifiers that
wrote it is the difference between interpreting the record and guessing at it,
and pinning the interpretation exactly as tightly as the library is the whole
point of decisions document 0003 A3.

It refuses rather than guesses. A run missing a task, scoring one twice,
seating a role other than ``subject``, or executing somewhere other than Docker
is not the run the Campaign described, and normalizing it anyway would produce
a tidy document making a false claim.

Usage, from the host side::

    <engine-python> <engine-root>/tools/normalize_eval_output.py \\
        --output-dir <eval output dir> \\
        --membership <TasksetLock JSON> \\
        --experiment-manifest <ExperimentManifest JSON> \\
        --output <normalized-episodes.jsonl>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from verifiers.v1.cli.output import read_episodes
from verifiers.v1.trace import WireTrace

#: The one role v0.1 evaluates. A trace seated anywhere else is a different
#: experiment (spec 6.5).
SUBJECT_ROLE = "subject"

#: The only subject runtime WP6 executes.
DOCKER_RUNTIME = "docker"

TECHTREE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
RAW_TASK_HASH = re.compile(r"^[0-9a-f]{64}$")
#: An OCI reference that names content. The digest is what a receipt can cite.
#: For a multi-platform repository it is the image *index* digest, which is what
#: a Campaign pins and what the local daemon confirms it holds.
IMAGE_INDEX_DIGEST = re.compile(r"@(sha256:[0-9a-f]{64})$")


def parse_args() -> argparse.Namespace:
    """Parse the fixed helper arguments."""
    parser = argparse.ArgumentParser(
        description="Normalize raw Verifiers evaluation output.",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--membership", required=True, type=Path)
    parser.add_argument("--experiment-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def load_membership(path: Path) -> list[str]:
    """Load the Campaign's committed task hashes, in order.

    Techtree writes hashes with a ``sha256:`` prefix and Verifiers records them
    bare, so this is also the one place the two spellings meet.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    hashes = document.get("ordered_task_hashes")
    if not isinstance(hashes, list) or not hashes:
        raise SystemExit("the taskset lock commits no ordered task hashes")

    ordered: list[str] = []
    for value in hashes:
        if not isinstance(value, str) or TECHTREE_DIGEST.fullmatch(value) is None:
            raise SystemExit(f"committed task hash {value!r} is not a Techtree digest")
        ordered.append(value)
    if len(set(ordered)) != len(ordered):
        raise SystemExit("the taskset lock commits the same task twice")
    return ordered


def load_experiment(path: Path) -> dict[str, Any]:
    """Load the resolved experiment this evaluation claims to be."""
    document = json.loads(path.read_text(encoding="utf-8"))
    configuration = document.get("configuration")
    subject = (configuration or {}).get("agents", {}).get(SUBJECT_ROLE)
    if not isinstance(subject, dict):
        raise SystemExit(
            f"the experiment manifest defines no {SUBJECT_ROLE!r} agent to "
            "normalize against"
        )
    return document


def read_wire_episodes(output_dir: Path) -> list[Any]:
    """Read every persisted Episode with the pinned wire Trace type.

    ``WireTrace`` reads any taskset's saved trace without importing that
    taskset, which keeps this helper independent of whichever reference package
    produced the run.
    """
    return read_episodes(output_dir, WireTrace)


def digest_text(value: str) -> str:
    """Return the Techtree digest of one string's UTF-8 bytes."""
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def digest_json(value: Any) -> str:
    """Return the Techtree digest of one value's canonical JSON form."""
    return digest_text(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )


def normalize_task_hash(raw: str | None) -> str:
    """Return the Techtree spelling of one Verifiers task hash."""
    if not isinstance(raw, str) or RAW_TASK_HASH.fullmatch(raw) is None:
        raise SystemExit(f"a trace records no usable task hash: {raw!r}")
    return f"sha256:{raw}"


def normalize_error(error: Any) -> dict[str, Any]:
    """Project one upstream error.

    The traceback is kept: this projection only ever holds errors from records
    that failed, and a failure with its traceback stripped is a failure nobody
    can act on.
    """
    return {
        "type": error.type,
        "message": error.message,
        "traceback": error.traceback,
    }


def normalize_reward(name: str, reward: Any) -> dict[str, Any]:
    """Project one named reward, with its weighted contribution."""
    if reward is None:
        raise SystemExit(
            f"reward {name!r} was never scored; an episode whose scoring did "
            "not run is not a result"
        )
    score = float(reward.score)
    weight = float(reward.weight)
    value = score * weight
    for label, number in (("score", score), ("weight", weight), ("value", value)):
        if number != number or number in (float("inf"), float("-inf")):
            raise SystemExit(f"reward {name!r} has a non-finite {label}")
    return {"name": name, "score": score, "weight": weight, "value": value}


def normalize_tool(tool: Any) -> dict[str, Any]:
    """Project one advertised tool by name and by digest.

    A tool's description and parameter schema are prompt material. Hashing them
    proves two variants were offered identical tools without republishing what
    the subject was told.
    """
    return {
        "name": tool.name,
        "description_digest": digest_text(tool.description or ""),
        "parameters_digest": digest_json(tool.parameters or {}),
    }


def normalize_runtime(trace: Any) -> dict[str, Any]:
    """Project the box one trace ran in.

    The pinned Verifiers build records the reference it was asked to run and
    nothing about what the daemon resolved it to, so this projection reports
    exactly that: the reference, and the content digest the reference names. A
    Campaign pins its subject image by digest, so a reference that names no
    content is a run of something nobody can identify and is refused here
    rather than described as if it were pinned.

    What the local daemon confirmed — that it holds that content, and which
    platform it served — is captured by Techtree beside this projection, and the
    two are required to agree before a comparison is called controlled.
    """
    info = trace.agent.runtime
    if info is None:
        raise SystemExit(f"trace {trace.id} records no runtime")

    kind = getattr(info, "type", None)
    if kind != DOCKER_RUNTIME:
        raise SystemExit(
            f"trace {trace.id} ran on the {kind!r} runtime; WP6 evaluates the "
            f"{DOCKER_RUNTIME!r} runtime only"
        )

    image = getattr(info, "image", None)
    if not isinstance(image, str) or not image:
        raise SystemExit(f"trace {trace.id} records no runtime image")

    match = IMAGE_INDEX_DIGEST.search(image)
    if match is None:
        raise SystemExit(
            f"trace {trace.id} ran {image!r}, which names a tag rather than "
            "content; a controlled comparison runs a digest-pinned image"
        )

    return {
        "kind": DOCKER_RUNTIME,
        "runtime_id": getattr(info, "id", None),
        "image": image,
        "image_index_digest": match.group(1),
        "cpu": _optional_float(getattr(info, "cpu", None)),
        "memory_gb": _optional_float(getattr(info, "memory", None)),
    }


def normalize_sampling(trace: Any) -> dict[str, Any]:
    """Project the settings the subject was actually sampled under.

    Read from the trace rather than from the configuration file the engine
    wrote back out. Both are the engine's own answers, but only this one
    travels with the rollout it describes, so a consumer holding a normalized
    episode can compare two variants' effective sampling without opening a
    second document beside it.

    ``SamplingConfig`` allows provider-specific keys through, so every key the
    engine resolved is projected and none is filtered: a parameter Techtree
    never declared is exactly the sort of uncontrolled difference a comparison
    has to be able to see.
    """
    sampling = trace.agent.config.sampling
    if sampling is None:
        raise SystemExit(
            f"trace {trace.id} records no sampling settings, so how its subject "
            "was sampled is unknown"
        )
    values: dict[str, Any] = {}
    for key, value in sorted(sampling.model_dump(mode="json").items()):
        if value is None:
            continue
        if not isinstance(value, str | int | float | bool):
            raise SystemExit(
                f"trace {trace.id} was sampled under a non-scalar {key!r}, "
                "which cannot be compared between two variants"
            )
        values[str(key)] = value
    if not values:
        raise SystemExit(
            f"trace {trace.id} resolved an empty sampling table, so how its "
            "subject was sampled is unknown"
        )
    return values


def normalize_usage(trace: Any) -> dict[str, Any] | None:
    """Project provider-reported token accounting, or nothing.

    ``cost_usd`` is the provider's own number and is frequently absent. It is
    projected as-is, never computed here: an operational record downstream
    states where a cost came from, and a number this helper invented could not
    be told apart from one the provider reported.
    """
    usage = trace.usage
    if usage is None:
        return None
    return {
        "input_tokens": int(usage.input_tokens),
        "output_tokens": int(usage.completion_tokens),
        "total_tokens": int(usage.total_tokens),
        "cached_input_tokens": (
            None
            if usage.cached_input_tokens is None
            else int(usage.cached_input_tokens)
        ),
        "cost_usd": (None if usage.cost is None else float(usage.cost)),
    }


def normalize_trace(trace: Any, experiment: dict[str, Any]) -> dict[str, Any]:
    """Project one subject rollout."""
    if trace.agent.name != SUBJECT_ROLE:
        raise SystemExit(
            f"trace {trace.id} was produced by the {trace.agent.name!r} role; "
            f"v0.1 evaluates {SUBJECT_ROLE!r} and nothing else"
        )

    harness = trace.agent.config.harness
    if harness is None:
        raise SystemExit(f"trace {trace.id} records no harness")

    revision = trace.verifiers.commit
    if not isinstance(revision, str) or not revision:
        raise SystemExit(
            f"trace {trace.id} records no Verifiers commit; this run was not "
            "produced by an engine installed from the pinned source"
        )

    return {
        "trace_id": trace.id,
        "agent_role": SUBJECT_ROLE,
        "task_hash": normalize_task_hash(trace.task.hash),
        "ok": bool(trace.ok),
        "verifiers_version": trace.verifiers.version,
        "verifiers_revision": revision,
        "model_id": trace.agent.config.model or "",
        "sampling": normalize_sampling(trace),
        "harness_id": harness.id,
        "harness_version": str(getattr(harness, "version", "")),
        "use_bundled_skill": bool(getattr(harness, "use_bundled_skill", False)),
        "skill_root_digests": skill_root_digests(experiment),
        "runtime": normalize_runtime(trace),
        "tools": sorted(
            (normalize_tool(tool) for tool in trace.tools),
            key=lambda entry: entry["name"],
        ),
        "rewards": sorted(
            (normalize_reward(name, reward) for name, reward in trace.rewards.items()),
            key=lambda entry: entry["name"],
        ),
        "metrics": {
            name: (None if value is None else float(value))
            for name, value in sorted(trace.metrics.items())
        },
        "usage": normalize_usage(trace),
        # One entry per exchange the interception layer recorded. The token
        # counts above are an aggregate over exactly these calls, so a record
        # that reports a cost has the call count that cost was incurred over.
        "model_calls": len(trace.calls),
        "num_turns": int(trace.num_turns),
        "last_reply": trace.last_reply or None,
        "errors": [normalize_error(error) for error in trace.errors],
        "raw_trace_digest": digest_json(trace.model_dump(mode="json")),
    }


def normalize_episode(episode: Any, experiment: dict[str, Any]) -> dict[str, Any]:
    """Project one episode and the single subject trace it must carry."""
    if len(episode.traces) != 1:
        raise SystemExit(
            f"episode {episode.id} carries {len(episode.traces)} traces; a "
            "single-agent Campaign produces exactly one per episode"
        )
    trace = normalize_trace(episode.traces[0], experiment)
    return {
        "episode_id": episode.id,
        "env_id": episode.env.id,
        "task_hash": trace["task_hash"],
        "task_position": -1,
        "ok": bool(episode.ok),
        "traces": [trace],
        "errors": [normalize_error(error) for error in episode.errors],
        "raw_episode_digest": digest_json(episode.model_dump(mode="json")),
    }


def order_by_membership(
    episodes: list[dict[str, Any]], ordered_task_hashes: list[str]
) -> list[dict[str, Any]]:
    """Join episodes onto the Campaign's committed membership, in order.

    Line position in ``traces.jsonl`` is completion order, so this join is the
    only thing that makes the projection comparable between two variants. It
    refuses on anything that would leave the join ambiguous: a task with no
    episode, a task with two, or an episode scoring a task the Campaign never
    committed to.
    """
    by_hash: dict[str, dict[str, Any]] = {}
    for episode in episodes:
        task_hash = episode["task_hash"]
        if task_hash in by_hash:
            raise SystemExit(f"two episodes scored task {task_hash}")
        by_hash[task_hash] = episode

    unexpected = sorted(set(by_hash) - set(ordered_task_hashes))
    if unexpected:
        raise SystemExit(
            f"the evaluation scored {len(unexpected)} task(s) the Campaign never "
            f"committed to: {unexpected[0]}"
        )
    missing = [value for value in ordered_task_hashes if value not in by_hash]
    if missing:
        raise SystemExit(
            f"the evaluation is missing {len(missing)} committed task(s), "
            f"starting with {missing[0]}"
        )

    ordered: list[dict[str, Any]] = []
    for position, task_hash in enumerate(ordered_task_hashes):
        episode = by_hash[task_hash]
        episode["task_position"] = position
        ordered.append(episode)
    return ordered


def subject_of(experiment: dict[str, Any]) -> dict[str, Any]:
    """Return the manifest's subject agent."""
    subject = experiment["configuration"]["agents"][SUBJECT_ROLE]
    assert isinstance(subject, dict)
    return subject


def skill_root_digests(experiment: dict[str, Any]) -> list[str]:
    """Return the content digests of the skills this variant declared.

    Read from the manifest rather than from the trace. Verifiers records the
    directory a skill was mounted from, which is a run-owned host path; what a
    receipt can cite is the content the Campaign pinned.
    """
    digests: list[str] = []
    for skill in subject_of(experiment)["harness"].get("skills", []):
        digest = skill.get("digest")
        if not isinstance(digest, str) or TECHTREE_DIGEST.fullmatch(digest) is None:
            raise SystemExit(f"the experiment declares an unusable skill: {skill!r}")
        digests.append(digest)
    return digests


def main() -> int:
    """Write canonical compact JSONL ordered by task membership."""
    arguments = parse_args()
    experiment = load_experiment(Path(arguments.experiment_manifest))
    membership = load_membership(Path(arguments.membership))

    episodes = [
        normalize_episode(episode, experiment)
        for episode in read_wire_episodes(Path(arguments.output_dir))
    ]
    ordered = order_by_membership(episodes, membership)

    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(
            json.dumps(
                episode, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            + "\n"
            for episode in ordered
        ),
        encoding="utf-8",
    )
    return 0


def _optional_float(value: Any) -> float | None:
    """Return a finite float, or nothing."""
    if value is None:
        return None
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise SystemExit(f"a runtime resource limit is not finite: {value!r}")
    return number


if __name__ == "__main__":
    raise SystemExit(main())
