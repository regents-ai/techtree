"""Export the published JSON Schemas. Spec section 24.1.

One schema file per protocol object that crosses a boundary — a stored
document, a catalog entry, or a CLI response. The tree under ``schemas/`` is
generated, never hand-edited, and ``make generated-check`` regenerates it in a
throwaway copy of the repository and fails on any difference.

There is one directory per protocol version. ``v1alpha1`` is v0.1, and its
bytes are frozen because published evidence is validated against them.
``v2`` is the protocol v0.2 introduces, and it holds only the documents whose
shape actually changed; the two trees are exported the same way and neither
knows about the other.

Two things make the output stable enough to diff:

* Keys are sorted and the indent is fixed, so a reordering inside Pydantic
  cannot show up as a spurious change.
* Every schema carries an ``$id`` derived from its filename, so a consumer that
  has fetched one can say which one it fetched.

``CliEnvelope`` is generic. Its published schema describes the envelope, and
``data`` is deliberately unconstrained: each command documents its own payload,
and pinning one payload type here would describe a contract no command keeps.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from techtree.models.approval import ExecutionApproval, RemoteExecutionEstimate
from techtree.models.base import ObjectEnvelope
from techtree.models.campaign import CampaignSpec, CampaignSpecV2
from techtree.models.catalog import CatalogIndex, ClimbSummary, CompatibilityResult
from techtree.models.cli import CliEnvelope
from techtree.models.climb import ClimbManifest
from techtree.models.compatibility import (
    ConfigurationComparison,
    ConfigurationCompatibilityPolicy,
)
from techtree.models.data_policy import DataPolicy
from techtree.models.engine import EngineDescriptor
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.evaluation_backend import EvaluationBackendSpec
from techtree.models.evidence import EvidenceArtifactRef, EvidenceFacets
from techtree.models.execution_plan import ResolvedExecutionPlan
from techtree.models.experiment import ExperimentManifest
from techtree.models.run import RunState
from techtree.models.skill import SkillArtifact, SubmissionDraft
from techtree.models.uplift_report import UpliftReport
from techtree.models.validation import (
    TasksetLock,
    TasksetValidationReceipt,
    ValidationEvidence,
)
from techtree.publication.models import (
    PublicationReceiptPayload,
    PublicationSubmission,
    WithdrawalReceiptPayload,
    WithdrawalRequest,
)

#: Where each generated tree lives, relative to the repository root. One
#: directory per protocol version: ``v1alpha1`` is the v0.1 protocol and its
#: bytes are frozen, ``v2`` is the protocol v0.2 introduces.
SCHEMA_VERSION_DIRECTORY = "v1alpha1"
V2_SCHEMA_VERSION_DIRECTORY = "v2"

#: The JSON Schema dialect the exported documents are written against.
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

#: Base for the ``$id`` of each schema. It is a name, not a location: nothing
#: fetches it at runtime.
SCHEMA_ID_BASE = "https://schemas.techtree.dev"

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def schema_models() -> dict[str, type[BaseModel]]:
    """Return filename/model mapping."""
    return {
        "campaign": CampaignSpec,
        "catalog": CatalogIndex,
        "cli-envelope": CliEnvelope,
        "climb": ClimbManifest,
        "climb-summary": ClimbSummary,
        "compatibility-result": CompatibilityResult,
        "configuration-comparison": ConfigurationComparison,
        "configuration-compatibility-policy": ConfigurationCompatibilityPolicy,
        "data-policy": DataPolicy,
        "engine": EngineDescriptor,
        "episode-receipt": EpisodeReceipt,
        "evaluation-backend": EvaluationBackendSpec,
        "evidence-artifact-ref": EvidenceArtifactRef,
        "evidence-facets": EvidenceFacets,
        "execution-approval": ExecutionApproval,
        "experiment-manifest": ExperimentManifest,
        "remote-execution-estimate": RemoteExecutionEstimate,
        # The three signed documents travel in the envelope every other signed
        # document in this protocol travels in, so the published schema is the
        # envelope: a consumer validating one has to be told where the digest
        # and the signature are, not only what the payload holds.
        "publication-receipt": ObjectEnvelope[PublicationReceiptPayload],
        "publication-submission": PublicationSubmission,
        "publication-withdrawal": ObjectEnvelope[WithdrawalRequest],
        "publication-withdrawal-receipt": ObjectEnvelope[WithdrawalReceiptPayload],
        "run-state": RunState,
        "skill-artifact": SkillArtifact,
        "submission-draft": SubmissionDraft,
        "taskset-lock": TasksetLock,
        "taskset-validation-receipt": TasksetValidationReceipt,
        "uplift-report": UpliftReport,
        "validation-evidence": ValidationEvidence,
    }


def v2_schema_models() -> dict[str, type[BaseModel]]:
    """Return filename/model mapping for the protocol v0.2 introduces.

    The v1alpha1 tree above is frozen: consumers validate published v0.1
    evidence against it, so its documents keep their bytes. Documents whose
    shape v0.2 changes are published here instead of rewritten there.
    """
    return {
        "campaign": CampaignSpecV2,
        "execution-plan": ResolvedExecutionPlan,
    }


def schema_document(
    model: type[BaseModel], filename: str, version: str
) -> dict[str, object]:
    """Return the complete schema document for one model."""
    schema = model.model_json_schema(
        by_alias=True,
        ref_template="#/$defs/{model}",
        mode="validation",
    )
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": f"{SCHEMA_ID_BASE}/{version}/{filename}",
        **schema,
    }


def export_schema(model: type[BaseModel], destination: Path, version: str) -> None:
    """Generate stable JSON Schema."""
    document = schema_document(model, destination.name, version)
    rendered = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(f"{rendered}\n", encoding="utf-8")


def export_tree(models: dict[str, type[BaseModel]], version: str) -> Path:
    """Rewrite one protocol version's tree and return where it was written."""
    directory = REPOSITORY_ROOT / "schemas" / version
    directory.mkdir(parents=True, exist_ok=True)

    expected = {f"{name}.schema.json" for name in models}
    for stale in sorted(directory.glob("*.json")):
        if stale.name not in expected:
            stale.unlink()

    for name, model in sorted(models.items()):
        export_schema(model, directory / f"{name}.schema.json", version)
    return directory


def main() -> None:
    """Rewrite every schema tree."""
    trees = {
        SCHEMA_VERSION_DIRECTORY: schema_models(),
        V2_SCHEMA_VERSION_DIRECTORY: v2_schema_models(),
    }
    for version, models in trees.items():
        directory = export_tree(models, version)
        print(
            f"wrote {len(models)} schemas to {directory.relative_to(REPOSITORY_ROOT)}"
        )


if __name__ == "__main__":
    main()
