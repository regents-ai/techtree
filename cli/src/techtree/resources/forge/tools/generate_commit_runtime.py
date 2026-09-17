"""Drive Repo2RLEnv's ``commit_runtime`` pipeline from a bootstrap Techtree built.

Runs inside the managed forge environment, never in the ordinary Techtree
package. Techtree hands it one JSON request on argv[1]: the checkout to mine,
the bootstrap image it already built from that checkout, and the test commands
the person declared. It returns one JSON line on stdout with what the pipeline
found, emitted and skipped.

Repo2RLEnv's own bootstrap either runs an LLM loop to discover test commands
or, given a user Dockerfile, records none. Neither fits a lane whose model
calls belong to the person's own agent, so Techtree supplies the bootstrap
result whole: image tag, image id, language, test commands. Nothing here calls
a model; ``synthesize_with_llm`` is off and no LLM is configured.

The pipeline validates candidates in one long-lived container. Repo2RLEnv
would start that container unbounded and on the network; here it is started
on Techtree's terms instead, from the image id Techtree built, offline and
under the memory and CPU bounds the request names, with the name Techtree
chose so that Techtree can remove it if this process is stopped. The
pipeline's own cleanup still removes it on the ordinary path.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

from repo2rlenv.bootstrap.docker import DockerSandbox
from repo2rlenv.bootstrap.spec import BootstrapResult, LanguageHint
from repo2rlenv.log_parsers import parse_logs
from repo2rlenv.pipelines import pr_runtime_validate
from repo2rlenv.pipelines.commit_runtime import CommitRuntimePipeline
from repo2rlenv.pipelines.pr_runtime_validate import _slice_test_output
from repo2rlenv.spec.input import GenerationInput
from repo2rlenv.spec.options import CommitRuntimeOptions


class ValidationRecorder:
    """Observe the pinned validator without changing its result or admission rules."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.original = pr_runtime_validate.validate_pr
        self.records: list[dict] = []
        self.pending: dict | None = None

    def _save(self, record: dict) -> None:
        path = self.directory / record["index"] / "record.json"
        path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    def validate(self, **kwargs):
        result = self.original(**kwargs)
        index = f"{len(self.records) + 1:04d}"
        directory = self.directory / index
        directory.mkdir(parents=True, exist_ok=False)
        record = {
            "index": index,
            "label": None,
            "parent_commit": kwargs["base_commit"],
            "status": result.status,
            "upstream_reason": result.reason,
            "test_commands": list(kwargs["test_cmds"]),
        }
        for stage, log in (("pre", result.pre_log), ("post", result.post_log)):
            (directory / f"{stage}.log").write_text(log, encoding="utf-8")
            parsed = parse_logs(
                kwargs["test_cmds"],
                _slice_test_output(log),
                language=kwargs["language"],
            )
            record[stage] = {
                "parsed_count": len(parsed),
                "test_status": parsed,
            }
        self.records.append(record)
        self.pending = record
        self._save(record)
        return result

    def progress(self, *, name: str, outcome: str, reason: str = "") -> None:
        if self.pending is not None:
            self.pending.update(
                label=name, pipeline_outcome=outcome, pipeline_reason=reason
            )
            self._save(self.pending)
            self.pending = None

    def skip_reasons(self, original: dict[str, int]) -> dict[str, int]:
        if self.pending is not None or any(r["label"] is None for r in self.records):
            raise RuntimeError(
                "the pinned pipeline did not label its validation output"
            )
        count = sum(
            record["status"] == "failed"
            and record["upstream_reason"] == "no fail-to-pass tests after validation"
            and (
                record["pre"]["parsed_count"] == 0
                or record["post"]["parsed_count"] == 0
            )
            for record in self.records
        )
        reasons = dict(original)
        if count > reasons.get("no_fail_to_pass", 0):
            raise RuntimeError(
                "validation observations disagree with upstream skip counts"
            )
        if count:
            reasons["no_fail_to_pass"] -= count
            if reasons["no_fail_to_pass"] == 0:
                del reasons["no_fail_to_pass"]
            reasons["no_parseable_test_output"] = count
        return reasons


class BoundedPipeline(CommitRuntimePipeline):
    """The commit_runtime pipeline with its validation container on Techtree's terms."""

    def __init__(self, *args, container: dict[str, str], image_id: str, **kwargs):
        super().__init__(*args, **kwargs)
        self._container = container
        self._image_id = image_id

    def _start_validation_sandbox(self) -> DockerSandbox:
        # Overrides repo2rlenv 0.8.8's private method, which pulls the image by
        # tag and runs it unbounded. The marker directory plays the part the
        # upstream method gives it: an empty tree copied over /workspace.
        marker = Path(tempfile.mkdtemp(prefix="techtree-forge-validation-"))
        (marker / ".keep").write_text("")
        started = subprocess.run(
            [
                "docker",
                "run",
                "--detach",
                "--pull",
                "never",
                "--name",
                self._container["name"],
                "--platform",
                self.input.bootstrap.platform,
                "--network",
                "none",
                "--memory",
                self._container["memory"],
                "--cpus",
                self._container["cpus"],
                "--workdir",
                "/workspace",
                self._image_id,
                "sleep",
                "infinity",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        container_id = started.stdout.strip()
        if started.returncode != 0 or not container_id:
            reason = started.stderr.strip()[-400:]
            raise RuntimeError(f"the validation container did not start: {reason}")
        return DockerSandbox(
            container_id=container_id,
            repo_mount=str(marker),
            platform=self.input.bootstrap.platform,
        )


def main(argv: list[str]) -> int:
    # Repo2RLEnv reports progress and skip reasons through logging; Techtree
    # keeps stderr as the generation log, so everything goes there.
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    request = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    out_dir = Path(request["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    generation_input = GenerationInput.model_validate(
        {
            "repo": {"url": request["checkout"], "ref": "HEAD", "access": "public"},
            "pipeline": {
                "name": "commit_runtime",
                "options": {
                    "limit": request["limit"],
                    "synthesize_with_llm": False,
                },
            },
            "output": {
                "destination": str(out_dir),
                "org": request["org"],
                "dataset_name": request["dataset"],
                "visibility": "private",
            },
            "bootstrap": {"platform": request["platform"]},
            "auth": {"use_gh_cli": False, "use_hf_cli": False},
        }
    )
    options = CommitRuntimeOptions(limit=request["limit"], synthesize_with_llm=False)
    bootstrap = BootstrapResult(
        image_digest=request["image_id"],
        image_tag=request["image_tag"],
        language=LanguageHint(request["language"]),
        repo="/".join(generation_input.repo.owner_name),
        ref=request["head_commit"],
        rebuild_cmds=[],
        test_cmds=list(request["test_commands"]),
        smoke_passed=True,
        iterations=0,
        build_time_sec=0.0,
        llm_provider="none",
        dockerfile_reconstruction=request["dockerfile"],
        pushed_to_registry=False,
    )

    pipeline = BoundedPipeline(
        generation_input,
        options,
        bootstrap=bootstrap,
        container=dict(request["container"]),
        image_id=request["image_id"],
    )
    # commit_runtime 0.8.8 imports this function inside its serial candidate
    # loop. Its callback supplies labels but omits raw logs; observe the original
    # result at that narrow boundary, then restore the binding even on failure.
    # This module hook and its private output slicer are specific to the exact
    # 0.8.8 pin; an upstream bump requires real generation requalification.
    recorder = ValidationRecorder(out_dir.parent / "generation-validation")
    pipeline.set_progress_callback(recorder.progress)
    pr_runtime_validate.validate_pr = recorder.validate
    try:
        result = pipeline.run(out_dir)
    finally:
        pr_runtime_validate.validate_pr = recorder.original
    skip_reasons = recorder.skip_reasons(dict(result.skip_reasons))

    tasks = sorted(
        path.parent.name for path in out_dir.glob("*/task.toml") if path.is_file()
    )
    print(
        json.dumps(
            {
                "candidates": result.candidates,
                "emitted": result.emitted,
                "skipped": result.skipped,
                "skip_reasons": skip_reasons,
                "tasks": tasks,
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
