"""The published JSON Schemas. Spec sections 8, 24.1, 27.3.

``schemas/`` is a contract with consumers who do not run this code, one
directory per protocol version: ``v1alpha1`` is v0.1 and its bytes are frozen,
``v2`` holds the documents v0.2 changes. The tests here hold the parts of that
contract a regeneration could break without anybody noticing: which files
exist, that each is the schema of the model it claims, that the tree on disk
matches what the exporter produces right now, and that the exporter is
deterministic.

They also enforce two protocol rules structurally rather than by review. No
schema in either tree admits unknown fields. The Relay guard is narrower on
purpose: it is a v0.1 ruling (decisions 0001) and it covers the frozen
v1alpha1 tree, because v0.2 adds bounded Relay evidence in WP3.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIRECTORY = REPOSITORY_ROOT / "schemas" / "v1alpha1"
#: The protocol v0.2 introduces. It holds only the documents whose shape
#: changed, and it never rewrites the frozen v1alpha1 tree beside it.
V2_SCHEMA_DIRECTORY = REPOSITORY_ROOT / "schemas" / "v2"

#: Spec section 8, extended by decisions 0003 A7 with the catalog, summary, and
#: compatibility schemas, by A1 with normalized validation evidence, and by the
#: v0.2 plan's evidence contract with the facets, evidence availability, and
#: the estimate and approval that authorize a run's spend.
EXPECTED_SCHEMAS = {
    "campaign",
    "catalog",
    "cli-envelope",
    "climb",
    "climb-summary",
    "compatibility-result",
    "configuration-comparison",
    "configuration-compatibility-policy",
    "data-policy",
    "engine",
    "episode-receipt",
    "evaluation-backend",
    "evidence-artifact-ref",
    "evidence-facets",
    "execution-approval",
    "experiment-manifest",
    "publication-receipt",
    "publication-submission",
    "publication-withdrawal",
    "publication-withdrawal-receipt",
    "remote-execution-estimate",
    "run-state",
    "skill-artifact",
    "submission-draft",
    "taskset-lock",
    "taskset-validation-receipt",
    "uplift-report",
    "validation-evidence",
}

#: Plan v0.2: the Campaign gains its bound execution plan, the plan is a
#: document of its own, and every run-side document that used to copy its
#: execution facts out of the Campaign takes them from the plan instead.
EXPECTED_V2_SCHEMAS = {
    "campaign",
    "climb-summary",
    "compatibility-result",
    "episode-receipt",
    "execution-plan",
    "experiment-manifest",
    "run-request",
    "uplift-report",
}

#: The v0.2 documents whose execution facts come from the plan the Campaign
#: binds, and where each one names that plan so a reader can fetch it and
#: check every plane. Two documents name it below their root. The experiment
#: manifest puts it in the configuration the two arms are compared on, so that
#: a candidate which moved to another backend will read as an undeclared
#: difference once a comparator takes these documents; the climb summary
#: carries it through the compatibility result it already holds rather than
#: stating it twice.
V2_SCHEMAS_NAMING_THE_PLAN = {
    "compatibility-result": (),
    "episode-receipt": (),
    "experiment-manifest": ("ExperimentConfigurationV2",),
    "run-request": (),
    "uplift-report": (),
}

#: What the v0.2 Campaign dropped, in the spelling each dropped fact has in a
#: JSON Schema property name. No v0.2 document may state one of these, at any
#: depth: decision 0040's whole point is that the plan owns them now, and a
#: fact stated in two documents is a fact that can disagree with itself.
FACTS_THE_V2_CAMPAIGN_DROPPED = {
    "evaluation_backend",
    "evaluation_backend_kind",
    "evaluation_backend_supported",
    "verifiers_episode",
}


def exporter() -> Any:
    """Import the schema exporter from the tools tree.

    ``tools`` is a scripts directory rather than an installed package, so it is
    loaded by path. Importing it is what lets this test compare the committed
    tree against what the generator produces, instead of against itself.
    """
    import importlib.util

    location = REPOSITORY_ROOT / "tools" / "export_schemas.py"
    spec = importlib.util.spec_from_file_location("techtree_export_schemas", location)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def schema_text(name: str) -> str:
    """Return the committed schema file as text."""
    return (SCHEMA_DIRECTORY / f"{name}.schema.json").read_text(encoding="utf-8")


def schema(name: str) -> dict[str, Any]:
    """Return the committed schema file as a parsed document."""
    document: dict[str, Any] = json.loads(schema_text(name))
    return document


def v2_schema_text(name: str) -> str:
    """Return the committed v2 schema file as text."""
    return (V2_SCHEMA_DIRECTORY / f"{name}.schema.json").read_text(encoding="utf-8")


def v2_schema(name: str) -> dict[str, Any]:
    """Return the committed v2 schema file as a parsed document."""
    document: dict[str, Any] = json.loads(v2_schema_text(name))
    return document


def test_every_expected_schema_is_committed() -> None:
    committed = {
        path.name.removesuffix(".schema.json")
        for path in SCHEMA_DIRECTORY.glob("*.schema.json")
    }

    assert committed == EXPECTED_SCHEMAS


def test_no_unexpected_files_live_in_the_schema_tree() -> None:
    assert {path.name for path in SCHEMA_DIRECTORY.iterdir()} == {
        f"{name}.schema.json" for name in EXPECTED_SCHEMAS
    }


def test_the_exporter_and_the_expected_list_agree() -> None:
    assert set(exporter().schema_models()) == EXPECTED_SCHEMAS


@pytest.mark.parametrize("name", sorted(EXPECTED_SCHEMAS))
def test_the_committed_schema_matches_the_model(name: str) -> None:
    module = exporter()
    model: type[BaseModel] = module.schema_models()[name]
    expected = module.schema_document(model, f"{name}.schema.json", "v1alpha1")

    assert schema(name) == expected


@pytest.mark.parametrize("name", sorted(EXPECTED_SCHEMAS))
def test_each_schema_declares_a_dialect_and_an_identifier(name: str) -> None:
    document = schema(name)

    assert document["$schema"] == exporter().JSON_SCHEMA_DIALECT
    assert document["$id"].endswith(f"{name}.schema.json")


@pytest.mark.parametrize("name", sorted(EXPECTED_SCHEMAS))
def test_each_schema_is_deterministically_formatted(name: str) -> None:
    text = schema_text(name)
    expected = json.dumps(
        json.loads(text), indent=2, sort_keys=True, ensure_ascii=False
    )

    assert text == f"{expected}\n"


@pytest.mark.parametrize("name", sorted(EXPECTED_SCHEMAS))
def test_no_schema_admits_unknown_fields(name: str) -> None:
    """``extra="forbid"`` on every protocol model, checked from the outside."""
    document = schema(name)
    objects = [document, *document.get("$defs", {}).values()]

    for definition in objects:
        if definition.get("type") == "object" and "properties" in definition:
            assert definition["additionalProperties"] is False, definition.get("title")


@pytest.mark.parametrize("name", sorted(EXPECTED_SCHEMAS))
def test_no_schema_mentions_relay(name: str) -> None:
    """Decisions 0001: no Relay package, field, exporter, or status."""
    assert "relay" not in schema_text(name).lower()


# ---------------------------------------------------------------------------
# The protocol v0.2 introduces
# ---------------------------------------------------------------------------


def test_every_expected_v2_schema_is_committed() -> None:
    committed = {
        path.name.removesuffix(".schema.json")
        for path in V2_SCHEMA_DIRECTORY.glob("*.schema.json")
    }

    assert committed == EXPECTED_V2_SCHEMAS


def test_no_unexpected_files_live_in_the_v2_schema_tree() -> None:
    assert {path.name for path in V2_SCHEMA_DIRECTORY.iterdir()} == {
        f"{name}.schema.json" for name in EXPECTED_V2_SCHEMAS
    }


def test_the_exporter_and_the_expected_v2_list_agree() -> None:
    assert set(exporter().v2_schema_models()) == EXPECTED_V2_SCHEMAS


@pytest.mark.parametrize("name", sorted(EXPECTED_V2_SCHEMAS))
def test_the_committed_v2_schema_matches_the_model(name: str) -> None:
    module = exporter()
    model: type[BaseModel] = module.v2_schema_models()[name]
    expected = module.schema_document(model, f"{name}.schema.json", "v2")

    assert v2_schema(name) == expected


@pytest.mark.parametrize("name", sorted(EXPECTED_V2_SCHEMAS))
def test_each_v2_schema_declares_a_dialect_and_a_versioned_identifier(
    name: str,
) -> None:
    document = v2_schema(name)

    assert document["$schema"] == exporter().JSON_SCHEMA_DIALECT
    assert document["$id"].endswith(f"/v2/{name}.schema.json")


@pytest.mark.parametrize("name", sorted(EXPECTED_V2_SCHEMAS))
def test_each_v2_schema_is_deterministically_formatted(name: str) -> None:
    text = v2_schema_text(name)
    expected = json.dumps(
        json.loads(text), indent=2, sort_keys=True, ensure_ascii=False
    )

    assert text == f"{expected}\n"


@pytest.mark.parametrize("name", sorted(EXPECTED_V2_SCHEMAS))
def test_no_v2_schema_admits_unknown_fields(name: str) -> None:
    document = v2_schema(name)
    objects = [document, *document.get("$defs", {}).values()]

    for definition in objects:
        if definition.get("type") == "object" and "properties" in definition:
            assert definition["additionalProperties"] is False, definition.get("title")


def test_the_v2_campaign_schema_requires_its_execution_plan_digest() -> None:
    assert "execution_plan_digest" in v2_schema("campaign")["required"]


def test_the_v2_campaign_schema_drops_what_the_plan_owns() -> None:
    document = v2_schema("campaign")
    harness = document["$defs"]["HarnessSpecV2"]["properties"]

    assert "evaluation_backend" not in document["properties"]
    assert set(harness).isdisjoint({"id", "version"})
    assert (
        "verifiers_episode"
        not in (document["$defs"]["EvidenceRequirementsV2"]["properties"])
    )


@pytest.mark.parametrize("name", sorted(V2_SCHEMAS_NAMING_THE_PLAN))
def test_every_v2_document_names_the_plan_its_facts_come_from(name: str) -> None:
    document = v2_schema(name)
    for definition in V2_SCHEMAS_NAMING_THE_PLAN[name]:
        document = document["$defs"][definition]

    assert "execution_plan_digest" in document["required"]


def test_the_v2_climb_summary_reads_the_plan_through_its_compatibility_result() -> None:
    document = v2_schema("climb-summary")
    referenced = document["properties"]["compatibility"]["$ref"]

    assert "execution_plan_digest" not in document["properties"]
    assert referenced == "#/$defs/CompatibilityResultV2"
    assert (
        "execution_plan_digest"
        in document["$defs"]["CompatibilityResultV2"]["required"]
    )


@pytest.mark.parametrize("name", sorted(EXPECTED_V2_SCHEMAS))
def test_no_v2_schema_states_a_fact_the_v2_campaign_dropped(name: str) -> None:
    """The structural form of decision 0040's rule, at every depth."""
    document = v2_schema(name)
    stated: set[str] = set()
    for definition in [document, *document.get("$defs", {}).values()]:
        stated |= set(definition.get("properties", {}))

    assert stated.isdisjoint(FACTS_THE_V2_CAMPAIGN_DROPPED)


def test_no_v2_schema_restates_the_subject_harness_coordinates() -> None:
    """A harness id and version beside a skill list is the coordinate pair."""
    for name in sorted(EXPECTED_V2_SCHEMAS):
        for definition in v2_schema(name).get("$defs", {}).values():
            properties = set(definition.get("properties", {}))
            if "skills" not in properties:
                continue
            assert properties.isdisjoint({"id", "version"}), name


def test_the_v2_run_side_documents_report_where_the_work_ran() -> None:
    for name in ("episode-receipt", "uplift-report"):
        assert "execution_location" in v2_schema(name)["required"], name


def test_the_v2_compatibility_result_judges_every_plane_a_host_can_fail() -> None:
    required = set(v2_schema("compatibility-result")["required"])

    assert {
        "evaluation_engine_source_commit",
        "evaluation_engine_wheel_digest",
        "execution_backend_kind",
        "execution_backend_supported",
        "subject_backend_kind",
        "subject_backend_supported",
    } <= required


def test_the_v2_receipt_names_its_executor_the_way_a_run_does() -> None:
    """One spelling of that fact in v0.2, and none that reads as a plane."""
    properties = set(v2_schema("episode-receipt")["properties"])

    assert "executor_kind" in properties
    assert "execution_backend" not in properties


def test_the_v2_run_request_says_which_document_it_is() -> None:
    assert v2_schema("run-request")["properties"]["schema_version"]["const"] == (
        "techtree.run-request.v2"
    )


def test_the_v1alpha1_run_side_schemas_are_untouched_by_the_v2_documents() -> None:
    """The frozen tree still states the facts v0.2 moved to the plan."""
    assert "evaluation_backend" in schema("episode-receipt")["properties"]
    assert "evaluation_backend" in schema("uplift-report")["properties"]
    assert (
        "evaluation_backend"
        in (
            schema("experiment-manifest")["$defs"]["ExperimentConfiguration"][
                "properties"
            ]
        )
    )
    assert "evaluation_backend" in schema("climb-summary")["properties"]


def test_the_v1alpha1_campaign_schema_has_no_execution_plan_digest() -> None:
    """The frozen tree gains nothing; published evidence validates against it."""
    assert "execution_plan_digest" not in schema("campaign")["properties"]


def test_the_execution_plan_schema_carries_all_four_planes() -> None:
    properties = set(v2_schema("execution-plan")["properties"])

    assert {"evaluation", "execution", "subject", "evidence"} <= properties


def test_the_campaign_schema_has_no_public_policy_fields() -> None:
    for properties in (
        set(schema("campaign")["properties"]),
        set(v2_schema("campaign")["properties"]),
    ):
        assert properties.isdisjoint(
            {"slug", "leaderboard", "publication", "candidate_policy", "status"}
        )


def test_the_climb_schema_has_no_scientific_fields() -> None:
    properties = set(schema("climb")["properties"])

    assert properties.isdisjoint(
        {"agents", "taskset", "scoring", "execution", "mutation_contract", "budgets"}
    )


def test_the_campaign_schema_requires_a_data_policy_digest() -> None:
    assert "data_policy_digest" in schema("campaign")["required"]


def test_the_campaign_schema_pins_shuffle_to_false() -> None:
    selection = schema("campaign")["$defs"]["TaskSelection"]

    assert selection["properties"]["shuffle"]["const"] is False


def test_the_receipt_schema_carries_no_identity_or_timing() -> None:
    """Decisions 0003 A1."""
    properties = set(schema("taskset-validation-receipt")["properties"])

    assert properties.isdisjoint({"id", "created_at", "artifacts"})
    assert "method" in properties
    assert "normalized_evidence" in properties


def test_the_submission_draft_schema_asks_for_policy_acceptance() -> None:
    """Decisions 0003 A5."""
    properties = set(schema("submission-draft")["properties"])

    assert "policy_acceptance" in properties
    assert "policy_acknowledgement" not in properties


def test_the_cli_envelope_schema_leaves_its_payload_open() -> None:
    data = schema("cli-envelope")["properties"]["data"]

    assert data["anyOf"] == [{}, {"type": "null"}]


def test_the_engine_schema_fixes_the_host_vocabulary() -> None:
    """Decisions 0003 A9."""
    document = schema("engine")
    hosts = document["$defs"]["HostPlatform"]["enum"]

    assert document["properties"]["supported_hosts"]["items"] == {
        "$ref": "#/$defs/HostPlatform"
    }

    assert sorted(hosts) == [
        "darwin/amd64",
        "darwin/arm64",
        "linux/amd64",
        "linux/arm64",
    ]


def test_regeneration_is_byte_stable(tmp_path: Path) -> None:
    module = exporter()

    for name, model in module.schema_models().items():
        destination = tmp_path / f"{name}.schema.json"
        module.export_schema(model, destination, "v1alpha1")
        module.export_schema(model, destination, "v1alpha1")

        assert destination.read_text(encoding="utf-8") == schema_text(name)


def test_v2_regeneration_is_byte_stable(tmp_path: Path) -> None:
    module = exporter()

    for name, model in module.v2_schema_models().items():
        destination = tmp_path / f"{name}.schema.json"
        module.export_schema(model, destination, "v2")
        module.export_schema(model, destination, "v2")

        assert destination.read_text(encoding="utf-8") == v2_schema_text(name)


# ---------------------------------------------------------------------------
# The frozen tree is verified, never written
# ---------------------------------------------------------------------------
#
# Regenerating a tree that is called frozen is how a v0.1 document's bytes move
# without anybody deciding they should: the export rewrites the file, and every
# check that compares the committed tree against a fresh export agrees with the
# rewritten bytes afterwards. The tests below hold the only arrangement in
# which the word means something — the generator reads that tree and reports,
# and a difference stops the generation.


def test_the_v1alpha1_tree_is_the_frozen_one() -> None:
    assert set(exporter().FROZEN_SCHEMA_VERSIONS) == {"v1alpha1"}


def test_the_committed_frozen_tree_verifies() -> None:
    module = exporter()

    assert module.verify_tree(module.schema_models(), "v1alpha1") == []


def test_verifying_the_frozen_tree_writes_nothing(tmp_path: Path) -> None:
    module = exporter()
    copy = tmp_path / "v1alpha1"
    copy.mkdir()
    for path in SCHEMA_DIRECTORY.glob("*.schema.json"):
        (copy / path.name).write_bytes(path.read_bytes())
    before = {path.name: path.read_bytes() for path in copy.iterdir()}

    assert module.verify_tree(module.schema_models(), "v1alpha1", copy) == []
    assert {path.name: path.read_bytes() for path in copy.iterdir()} == before


@pytest.mark.parametrize(
    ("break_it", "expected"),
    [
        (
            lambda directory: (directory / "campaign.schema.json").write_text(
                '{"$id": "not the published schema"}\n', encoding="utf-8"
            ),
            "v1alpha1/campaign.schema.json no longer matches the model it publishes",
        ),
        (
            lambda directory: (directory / "campaign.schema.json").unlink(),
            "v1alpha1/campaign.schema.json is committed nowhere",
        ),
        (
            lambda directory: (directory / "invented.schema.json").write_text(
                "{}\n", encoding="utf-8"
            ),
            "v1alpha1/invented.schema.json publishes no model",
        ),
    ],
    ids=["changed", "missing", "unexpected"],
)
def test_a_frozen_tree_that_moved_is_reported(
    tmp_path: Path, break_it: Any, expected: str
) -> None:
    module = exporter()
    copy = tmp_path / "v1alpha1"
    copy.mkdir()
    for path in SCHEMA_DIRECTORY.glob("*.schema.json"):
        (copy / path.name).write_bytes(path.read_bytes())
    break_it(copy)

    assert module.verify_tree(module.schema_models(), "v1alpha1", copy) == [expected]
