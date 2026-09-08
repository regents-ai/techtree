"""Export the published JSON Schemas. Spec section 24.1.

One schema file per protocol object that crosses a boundary — a stored
document, a catalog entry, or a CLI response. The tree under ``schemas/`` is
generated, never hand-edited, and ``make generated-check`` regenerates it in a
throwaway copy of the repository and fails on any difference.

There is one directory per protocol version. ``v1alpha1`` is v0.1, and its
bytes are frozen because published evidence is validated against them.
``v2`` is the protocol v0.2 introduces, and it holds only the documents whose
shape actually changed; neither tree knows about the other.

The frozen tree is *verified* rather than written. Saying the bytes are frozen
and then rewriting them on every regeneration is a promise nothing keeps: a
change that reorders a v0.1 document's fields would land in the working tree
silently, and every check that compares the committed tree against a fresh
export would agree with it afterwards. So ``v1alpha1`` is never opened for
writing here. Its schemas are exported in memory, compared byte for byte
against what is committed, and a difference stops the generation and names the
files, which is the only outcome that can reach a reviewer.

Two of its files have outlived their models and are checked a second way. The
v1 CLI envelope described bytes v0.1 released and its model describes
``techtree.cli.v2`` now; the v1 run state embeds that envelope's error, which
lost a field in the same cutover. Neither can be rendered any more, so there is
nothing to compare against — they are checked against the digest of the exact
bytes instead, by the same guard, and are still never written. Their v0.2
shapes are published in the ``v2`` tree by the work that owns each document.

Two things make the output stable enough to diff:

* Keys are sorted and the indent is fixed, so a reordering inside Pydantic
  cannot show up as a spurious change.
* Every schema carries an ``$id`` derived from its filename, so a consumer that
  has fetched one can say which one it fetched.

``CliEnvelope`` is generic. Its published schema describes the envelope, and
``facts`` is deliberately unconstrained: each operation documents its own
payload, and pinning one payload type here would describe a contract no command
keeps. The envelope's v0.2 shape is ``techtree.cli.v2`` and lives in the ``v2``
tree.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel

from techtree.models.approval import ExecutionApproval, RemoteExecutionEstimate
from techtree.models.base import ObjectEnvelope
from techtree.models.campaign import CampaignSpec, CampaignSpecV2
from techtree.models.catalog import (
    CatalogIndex,
    CatalogIndexV2,
    ClimbSummary,
    ClimbSummaryV2,
    CompatibilityResult,
    CompatibilityResultV2,
)
from techtree.models.cli import CliEnvelope
from techtree.models.climb import ClimbManifest
from techtree.models.compatibility import (
    ConfigurationComparison,
    ConfigurationCompatibilityPolicy,
)
from techtree.models.data_policy import DataPolicy
from techtree.models.engine import EngineDescriptor
from techtree.models.episode_receipt import EpisodeReceipt, EpisodeReceiptV2
from techtree.models.evaluation_backend import EvaluationBackendSpec
from techtree.models.evidence import EvidenceArtifactRef, EvidenceFacets
from techtree.models.execution_plan import ResolvedExecutionPlan
from techtree.models.experiment import ExperimentManifest, ExperimentManifestV2
from techtree.models.run import RunRequestV2
from techtree.models.skill import SkillArtifact, SubmissionDraft
from techtree.models.uplift_report import UpliftReport, UpliftReportV2
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

#: The protocol generations whose committed bytes this tool may not write.
#: Published v0.1 evidence is validated against ``v1alpha1``, so a change to a
#: document there is a release decision rather than a regeneration.
FROZEN_SCHEMA_VERSIONS = frozenset({SCHEMA_VERSION_DIRECTORY})

#: Files in a frozen tree that no model can render any more, per protocol
#: version, keyed by filename and valued by the SHA-256 of the exact bytes v0.1
#: released. ``techtree.models.cli:CliEnvelope`` describes ``techtree.cli.v2``
#: now, and ``techtree.models.run:RunState`` carries that envelope's error,
#: which lost its ``retryable`` field in the same cutover. There is nothing
#: left to render them from, so the guard checks their digest instead — the
#: same guard, and the same refusal to write.
FROZEN_SCHEMAS_WITHOUT_A_MODEL: dict[str, dict[str, str]] = {
    SCHEMA_VERSION_DIRECTORY: {
        "cli-envelope.schema.json": (
            "3d978d9f44068ac76f05b5ccded485f589031482bc401736f09789b0a98fbbb1"
        ),
        "run-state.schema.json": (
            "d9c835017a26e0ea72e073c9624608bcfc8425cf1116f3f0c9a446737644e321"
        ),
    },
}

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
        # The index gains one object kind, the resolved execution plan, so a
        # v0.2 catalog is described here rather than by the frozen v0.1 index.
        "catalog": CatalogIndexV2,
        "cli-envelope": CliEnvelope,
        "climb-summary": ClimbSummaryV2,
        "compatibility-result": CompatibilityResultV2,
        "episode-receipt": EpisodeReceiptV2,
        "execution-plan": ResolvedExecutionPlan,
        "experiment-manifest": ExperimentManifestV2,
        # The run's own record of what was asked for. It is a stored document
        # in both generations and it had no published schema under v0.1; the
        # v0.2 shape is published because it is the document that names the
        # execution plan a run is bound to, and a consumer reading a run
        # directory should be able to validate it.
        "run-request": RunRequestV2,
        "uplift-report": UpliftReportV2,
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


def rendered_schema(model: type[BaseModel], filename: str, version: str) -> str:
    """Return the exact text one schema file holds."""
    document = schema_document(model, filename, version)
    rendered = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)
    return f"{rendered}\n"


def export_schema(model: type[BaseModel], destination: Path, version: str) -> None:
    """Generate stable JSON Schema."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        rendered_schema(model, destination.name, version), encoding="utf-8"
    )


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


def verify_tree(
    models: dict[str, type[BaseModel]],
    version: str,
    directory: Path | None = None,
    frozen: dict[str, str] | None = None,
) -> list[str]:
    """Return every way a frozen tree differs from what it is supposed to hold.

    Nothing is written, including when everything matches. A caller gets one
    sentence per problem, naming the file, so a drift is reported in full
    rather than one file at a time.

    Two kinds of file live in a frozen tree. Most are still described by a
    model, and are checked by rendering it and comparing byte for byte. A few
    have outlived their model — ``frozen`` names them — and are checked against
    the digest of the bytes v0.1 released, because there is nothing left to
    render them from. Both are the same promise: these bytes do not move.
    """
    tree = REPOSITORY_ROOT / "schemas" / version if directory is None else directory
    digests = (
        FROZEN_SCHEMAS_WITHOUT_A_MODEL.get(version, {}) if frozen is None else frozen
    )
    problems: list[str] = []

    for name, model in sorted(models.items()):
        filename = f"{name}.schema.json"
        expected = rendered_schema(model, filename, version)
        path = tree / filename
        try:
            committed = path.read_text(encoding="utf-8")
        except OSError:
            problems.append(f"{version}/{filename} is committed nowhere")
            continue
        if committed != expected:
            problems.append(
                f"{version}/{filename} no longer matches the model it publishes"
            )

    for filename, expected_digest in sorted(digests.items()):
        path = tree / filename
        try:
            raw = path.read_bytes()
        except OSError:
            problems.append(f"{version}/{filename} is committed nowhere")
            continue
        if hashlib.sha256(raw).hexdigest() != expected_digest:
            problems.append(f"{version}/{filename} no longer holds released bytes")

    published = {f"{name}.schema.json" for name in models} | set(digests)
    for stale in sorted(tree.glob("*.json")):
        if stale.name not in published:
            problems.append(f"{version}/{stale.name} publishes no model")
    return problems


def main() -> None:
    """Rewrite every schema tree that is not frozen, and verify the ones that are."""
    trees = {
        SCHEMA_VERSION_DIRECTORY: schema_models(),
        V2_SCHEMA_VERSION_DIRECTORY: v2_schema_models(),
    }
    for version, models in trees.items():
        relative = Path("schemas") / version
        if version in FROZEN_SCHEMA_VERSIONS:
            problems = verify_tree(models, version)
            if problems:
                raise SystemExit(
                    f"{relative} is frozen and its bytes were not written:\n"
                    + "".join(f"  {problem}\n" for problem in problems)
                    + "  published v0.1 evidence is validated against these "
                    "schemas, so changing one is a release decision, not a "
                    "regeneration."
                )
            frozen = FROZEN_SCHEMAS_WITHOUT_A_MODEL.get(version, {})
            checked = len(models) + len(frozen)
            print(f"verified {checked} frozen schemas in {relative}")
            continue
        export_tree(models, version)
        print(f"wrote {len(models)} schemas to {relative}")


if __name__ == "__main__":
    main()
