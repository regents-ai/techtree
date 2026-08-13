"""Export the published JSON Schemas. Spec section 24.1.

One schema file per protocol object that crosses a boundary — a stored
document, a catalog entry, or a CLI response. The tree under ``schemas/`` is
generated, never hand-edited, and ``make generated-check`` regenerates it in a
throwaway copy of the repository and fails on any difference.

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

from techtree.models.campaign import CampaignSpec
from techtree.models.catalog import CatalogIndex, ClimbSummary, CompatibilityResult
from techtree.models.cli import CliEnvelope
from techtree.models.climb import ClimbManifest
from techtree.models.data_policy import DataPolicy
from techtree.models.engine import EngineDescriptor
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.evaluation_backend import EvaluationBackendSpec
from techtree.models.experiment import ExperimentManifest
from techtree.models.run import RunState
from techtree.models.skill import SkillArtifact, SubmissionDraft
from techtree.models.uplift_report import UpliftReport
from techtree.models.validation import (
    TasksetLock,
    TasksetValidationReceipt,
    ValidationEvidence,
)

#: Where the generated tree lives, relative to the repository root.
SCHEMA_VERSION_DIRECTORY = "v1alpha1"

#: The JSON Schema dialect the exported documents are written against.
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

#: Base for the ``$id`` of each schema. It is a name, not a location: nothing
#: fetches it at runtime.
SCHEMA_ID_BASE = "https://schemas.techtree.dev/v1alpha1"

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
        "data-policy": DataPolicy,
        "engine": EngineDescriptor,
        "episode-receipt": EpisodeReceipt,
        "evaluation-backend": EvaluationBackendSpec,
        "experiment-manifest": ExperimentManifest,
        "run-state": RunState,
        "skill-artifact": SkillArtifact,
        "submission-draft": SubmissionDraft,
        "taskset-lock": TasksetLock,
        "taskset-validation-receipt": TasksetValidationReceipt,
        "uplift-report": UpliftReport,
        "validation-evidence": ValidationEvidence,
    }


def schema_document(model: type[BaseModel], filename: str) -> dict[str, object]:
    """Return the complete schema document for one model."""
    schema = model.model_json_schema(
        by_alias=True,
        ref_template="#/$defs/{model}",
        mode="validation",
    )
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": f"{SCHEMA_ID_BASE}/{filename}",
        **schema,
    }


def export_schema(model: type[BaseModel], destination: Path) -> None:
    """Generate stable JSON Schema."""
    document = schema_document(model, destination.name)
    rendered = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(f"{rendered}\n", encoding="utf-8")


def main() -> None:
    """Rewrite schema tree."""
    directory = REPOSITORY_ROOT / "schemas" / SCHEMA_VERSION_DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)

    models = schema_models()
    expected = {f"{name}.schema.json" for name in models}
    for stale in sorted(directory.glob("*.json")):
        if stale.name not in expected:
            stale.unlink()

    for name, model in sorted(models.items()):
        export_schema(model, directory / f"{name}.schema.json")

    print(f"wrote {len(models)} schemas to {directory.relative_to(REPOSITORY_ROOT)}")


if __name__ == "__main__":
    main()
