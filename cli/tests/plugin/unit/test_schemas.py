"""The declared tool surface is exactly what the manifest promises.

Specification sections 7.4 and 7.15: manifest validity, and the rules a
model-visible schema has to obey.
"""

from __future__ import annotations

from typing import Any

import pytest
from techtree_hermes.constants import MANIFEST_FILENAME, PLUGIN_ROOT
from techtree_hermes.doctor import read_manifest
from techtree_hermes.schemas import all_tool_schemas

MANIFEST = read_manifest(PLUGIN_ROOT / MANIFEST_FILENAME)
SCHEMAS = all_tool_schemas()

# Words that would mean the model is being handed a credential, an
# executable, or a command line.
FORBIDDEN_PROPERTY_WORDS = (
    "api_key",
    "apikey",
    "argv",
    "command",
    "credential",
    "executable",
    "password",
    "secret",
    "shell",
)


def test_manifest_declares_exactly_the_defined_tools() -> None:
    assert sorted(MANIFEST.provides_tools) == sorted(SCHEMAS)


def test_manifest_declares_no_environment_credentials() -> None:
    """Provider authentication belongs to Techtree's Doctor, not to loading."""
    declarations = [
        line
        for line in (PLUGIN_ROOT / MANIFEST_FILENAME).read_text("utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert not any("requires_env" in line for line in declarations)


def test_the_schema_mapping_cannot_be_edited_by_a_caller() -> None:
    schemas = all_tool_schemas()

    with pytest.raises(TypeError):
        schemas["techtree_run_status"] = {}  # type: ignore[index]

    all_tool_schemas()["techtree_run_status"]["description"] = "changed"
    assert all_tool_schemas()["techtree_run_status"]["description"] != "changed"


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_each_schema_is_closed_and_described(name: str) -> None:
    schema = SCHEMAS[name]

    assert schema["type"] == "object"
    assert schema["description"].strip()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) <= set(schema["properties"])


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_each_schema_offers_the_channel_choice(name: str) -> None:
    channel = SCHEMAS[name]["properties"]["channel"]

    assert channel["enum"] == ["terminal", "gateway", "unknown"]
    assert "channel" not in SCHEMAS[name]["required"]


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_no_schema_accepts_a_credential_or_a_command(name: str) -> None:
    for property_name in SCHEMAS[name]["properties"]:
        lowered = property_name.lower()
        assert not any(word in lowered for word in FORBIDDEN_PROPERTY_WORDS), (
            f"{name} accepts {property_name!r}"
        )


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_every_string_a_schema_takes_is_bounded(name: str) -> None:
    for property_name, definition in SCHEMAS[name]["properties"].items():
        if definition.get("type") != "string":
            continue
        bounded = (
            definition.get("pattern")
            or definition.get("enum")
            or definition.get("maxLength")
        )
        assert bounded, f"{name}.{property_name} is an unbounded string"
        assert definition["description"].strip()


def _path_properties() -> list[tuple[str, str, dict[str, Any]]]:
    found = []
    for name, schema in sorted(SCHEMAS.items()):
        for property_name, definition in schema["properties"].items():
            if property_name.endswith("_path"):
                found.append((name, property_name, definition))
    return found


def test_path_taking_tools_require_an_explicitly_identified_path() -> None:
    path_properties = _path_properties()

    assert path_properties, "the plugin still takes at least one local path"
    for name, property_name, definition in path_properties:
        assert "identified explicitly" in definition["description"], (
            f"{name}.{property_name} does not say where the path must come from"
        )


def test_spending_tools_say_so_in_their_description() -> None:
    """A tool that costs money or changes the host says it in its first lines."""
    spending = {
        "techtree_climb_start": "spends real money",
        "techtree_uplift_start": "spends real money",
        "techtree_bootstrap_install": "changes software",
    }

    for name, phrase in spending.items():
        assert phrase in SCHEMAS[name]["description"]


def test_reading_tools_say_they_are_free() -> None:
    for name in (
        "techtree_bootstrap_check",
        "techtree_system_check",
        "techtree_climbs_list",
        "techtree_climb_inspect",
        "techtree_run_status",
        "techtree_run_result",
        "techtree_proof_verify",
        "techtree_uplift_context",
    ):
        assert "free" in SCHEMAS[name]["description"]
