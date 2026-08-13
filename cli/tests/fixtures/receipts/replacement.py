"""Evidence for a Skill-against-Skill run, and what in it is a stub.

The v1-against-v2 loop needs a second run to execute, and no Skill v2 has ever
been evaluated: the paid probes of 2026-08-13 measured ``branch-code-v1``
against no Skill, once. Spec section 7.19's replacement is therefore exercised
here over evidence that is *recorded on one side and stubbed on the other*, and
this module exists so that which is which is never in doubt.

RECORDED, UNTOUCHED
    Every episode, reward, tool digest, runtime record and resolved
    configuration on **both** sides comes from the recorded candidate probe —
    the real evaluation of ``branch-code-v1`` in a real Docker container, two
    tasks, ``exact_match`` 2/2. No number here was invented.

STUBBED, AND THIS IS THE WHOLE OF IT
    The candidate side's episodes are re-declared under Skill v2's content
    address. Two strings change — the ``skill_root_digests`` each trace
    records, and the content-addressed directory the resolved configuration
    says the Skill was mounted from — and nothing else. So the candidate side
    of the second run reports measurements that were really taken, attributed
    to a Skill that did not take them.

WHAT THAT MAKES TESTABLE, AND WHAT IT DOES NOT
    It makes the *pipeline* testable end to end: a replacement Campaign
    derived, a controlled pair prepared, a run started, receipts built and
    signed, an observed comparison passed with a Skill on each side, and a
    second signed report whose proof verifies offline. It makes no scientific
    claim about any Skill v2 whatsoever, and the tests assert none: the second
    report's honest outcome is a tie and therefore a rejection, because the two
    sides are the same measurements.

The revised Skill itself is a real directory that goes through the real
scanner, the real snapshotter and the real archive builder. Only the evidence
of running it is a stub.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from fixtures.receipts.pair import restrict_to_tasks
from fixtures.receipts.support import (
    NORMALIZED_EPISODES_FILE,
    RESOLVED_CONFIG_FILE,
    recorded_root,
)
from techtree.canonical import digest_object, sha256_digest_bytes
from techtree.models.base import ArtifactRef, Digest
from techtree.models.campaign import SUBJECT_AGENT
from techtree.models.experiment import ExperimentManifest
from techtree.models.run import RunPhase
from techtree.paths import TechtreePaths
from techtree.receipts.episode import read_variant_episodes
from techtree.runs.executor import ExecutionContext
from techtree.runs.real import TASKSET_LOCK_FILENAME
from techtree.verifiers.models import (
    RealExecutionResult,
    RunPaths,
    VariantExecutionResult,
    VariantName,
)

__all__ = [
    "REVISED_SKILL_TEXT",
    "ReplacementEvidenceExecutor",
    "write_revised_skill",
]

#: The revised Skill's own text. It is a real instruction Skill — the scanner,
#: the archive builder and the manifest comparison all see the genuine article
#: — and it says nothing about any task, because a Skill that named one would
#: be the contamination spec section 7.18 keeps out of the improvement loop.
REVISED_SKILL_TEXT: Final = """# Branch code procedure, revised

Work the procedure one branch at a time.

1. Read the whole rule set before deciding anything.
2. Identify which single branch condition the input satisfies.
3. Apply only that branch's transformation.
4. State the result on its own, with no working shown.

If two branches appear to apply, the earlier one in the rule set wins.
"""

#: The recorded probe both sides of a replacement run are laid out from.
_RECORDED = VariantName.CANDIDATE


def write_revised_skill(destination: Path) -> Path:
    """Write the Skill v2 directory a replacement is prepared from."""
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "SKILL.md").write_text(REVISED_SKILL_TEXT, encoding="utf-8")
    return destination


class ReplacementEvidenceExecutor:
    """Lays out a replacement run's evidence and returns what WP6 would return.

    It reads the run's own staged inputs to learn which Skill each variant
    declares, so the evidence it writes always agrees with the manifests the
    run was actually created from. Nothing is started, nothing is called, and
    nothing is spent.
    """

    def __init__(self, *, paths: TechtreePaths) -> None:
        self._paths = paths

    def execute(self, context: ExecutionContext) -> RealExecutionResult:
        """Validate the taskset, lay out the evidence, and hand back the result."""
        run_id = context.request.run_id
        run_paths = RunPaths.for_run(self._paths, run_id)
        inputs = context.artifact_store.load_inputs(run_id, context.request)

        context.run_store.append(run_id, phase=RunPhase.VALIDATING_TASKSET)
        validation = context.validation_provider.validate(run_id=run_id, inputs=inputs)
        context.artifact_store.write_validation_marker(
            run_id, validation.marker_document()
        )
        lock_path = run_paths.inputs_dir / TASKSET_LOCK_FILENAME
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_bytes(validation.lock.model_dump_json().encode("utf-8"))

        context.run_store.append(run_id, phase=RunPhase.RUNNING_VARIANTS)
        recorded_skill = _recorded_skill_digest()
        manifests = {
            VariantName.BASELINE: inputs.baseline,
            VariantName.CANDIDATE: inputs.candidate,
        }
        results = {
            variant: self._lay_out(
                run_paths=run_paths,
                variant=variant,
                manifest=manifests[variant],
                recorded_skill=recorded_skill,
                committed=list(validation.lock.ordered_task_hashes),
            )
            for variant in (VariantName.BASELINE, VariantName.CANDIDATE)
        }

        return RealExecutionResult(
            execution_backend="verifiers",
            engine_digest=validation.lock.engine_digest,
            verifiers_revision=validation.receipt.method.validator_revision,
            schedule=inputs.campaign.execution.order,
            baseline=results[VariantName.BASELINE],
            candidate=results[VariantName.CANDIDATE],
        )

    def _lay_out(
        self,
        *,
        run_paths: RunPaths,
        variant: VariantName,
        manifest: ExperimentManifest,
        recorded_skill: Digest,
        committed: list[Digest],
    ) -> VariantExecutionResult:
        """Write one variant's evidence and describe it as the engine would."""
        declared = _declared_skill(manifest)
        output = run_paths.variant_output_dir(variant)
        output.mkdir(parents=True, exist_ok=True)

        for name in (NORMALIZED_EPISODES_FILE, RESOLVED_CONFIG_FILE):
            source = (recorded_root() / _RECORDED.value / name).read_text("utf-8")
            # The only edit: the Skill this side declares. Both spellings of a
            # digest occur — ``sha256:`` in the episodes, ``sha256-`` in the
            # mount directory the resolved configuration names — and both are
            # rewritten so that what the traces record and what the engine
            # mounted still agree with each other.
            rewritten = source.replace(
                _hexadecimal(recorded_skill), _hexadecimal(declared)
            )
            (output / name).write_text(rewritten, encoding="utf-8")

        episodes_path = output / NORMALIZED_EPISODES_FILE
        config_path = output / RESOLVED_CONFIG_FILE
        recorded_result = _recorded_result()
        return restrict_to_tasks(
            recorded_result.model_copy(
                update={
                    "variant": variant,
                    # The operational envelope belongs to whichever side it is
                    # filed under, and the result model checks that it does.
                    "child_outcome": recorded_result.child_outcome.model_copy(
                        update={"variant": variant}
                    ),
                    "episodes": read_variant_episodes(episodes_path),
                    "normalized_episodes": _written(episodes_path),
                    "resolved_verifiers_config": _written(
                        config_path, media_type="application/toml"
                    ),
                }
            ),
            committed,
            experiment_manifest_digest=digest_object(manifest),
        )


def _declared_skill(manifest: ExperimentManifest) -> Digest:
    """Return the one Skill a replacement variant declares."""
    subject = manifest.configuration.agents[SUBJECT_AGENT]
    references = subject.harness.skills
    if len(references) != 1:
        raise AssertionError(
            "every variant of a replacement declares exactly one Skill; this "
            f"{manifest.variant.value} declares {len(references)}"
        )
    return references[0].digest


def _recorded_skill_digest() -> Digest:
    """Return the Skill the recorded probe actually mounted."""
    from fixtures.receipts.support import recorded_variant

    episodes = recorded_variant(_RECORDED).episodes
    digests = {
        digest
        for episode in episodes
        for trace in episode.traces
        for digest in trace.skill_root_digests
    }
    if len(digests) != 1:
        raise AssertionError(
            f"the recorded probe mounted {len(digests)} Skills, not one"
        )
    return digests.pop()


def _recorded_result() -> VariantExecutionResult:
    """Return the recorded probe's own execution result, to copy the shape from."""
    from fixtures.receipts.support import recorded_variant

    return recorded_variant(_RECORDED).result


def _written(path: Path, *, media_type: str = "application/x-ndjson") -> ArtifactRef:
    """Describe a file this fixture just wrote, hashed from its own bytes."""
    data = path.read_bytes()
    return ArtifactRef(
        digest=sha256_digest_bytes(data),
        media_type=media_type,
        size=len(data),
        relative_path=None,
    )


def _hexadecimal(digest: Digest) -> str:
    """Return the hexadecimal half of a digest, which is what a path carries."""
    _, _, hexadecimal = digest.partition(":")
    return hexadecimal
