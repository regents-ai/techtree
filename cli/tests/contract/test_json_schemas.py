"""The published JSON Schemas. Spec sections 8, 24.1, 27.3.

``schemas/v1alpha1`` is a contract with consumers who do not run this code. The
tests here hold the parts of that contract a regeneration could break without
anybody noticing: which files exist, that each is the schema of the model it
claims, that the tree on disk matches what the exporter produces right now, and
that the exporter is deterministic.

They also enforce two protocol rules structurally rather than by review — no
schema admits unknown fields, and none of them mentions Relay.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIRECTORY = REPOSITORY_ROOT / "schemas" / "v1alpha1"

#: Spec section 8, extended by decisions 0003 A7 with the catalog, summary, and
#: compatibility schemas, and by A1 with normalized validation evidence.
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
    "experiment-manifest",
    "publication-receipt",
    "publication-submission",
    "publication-withdrawal",
    "publication-withdrawal-receipt",
    "run-state",
    "skill-artifact",
    "submission-draft",
    "taskset-lock",
    "taskset-validation-receipt",
    "uplift-report",
    "validation-evidence",
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
    expected = module.schema_document(model, f"{name}.schema.json")

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


def test_the_campaign_schema_has_no_public_policy_fields() -> None:
    properties = set(schema("campaign")["properties"])

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
        module.export_schema(model, destination)
        module.export_schema(model, destination)

        assert destination.read_text(encoding="utf-8") == schema_text(name)
