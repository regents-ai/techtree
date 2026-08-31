"""The tool surface a pinned harness offers. Decisions 0007 R9 item 4.

Mounting a Skill changes what the subject is offered. Hermes 0.19.0 renders the
index of visible Skills into the description of its own Skill-management tool,
so the candidate variant is handed one tool description the baseline was not,
and a comparison that demanded one identical tool surface would reject every
correct run.

That leaves a question a comparison cannot answer from the run alone: is a
description difference *the* expected one, or is it evidence that the harness
pin moved underneath the Campaign? Both look the same from inside a single
comparison — one description differing on one tool.

This module holds the other half of the answer: a conformance fixture recording
the tool surface the pinned harness offers, tool by tool, schema by schema. The
ratified rule (decisions document 0007, release ratifications) is an exact
derived difference — the tool count, the tool names, the parameter schemas and
the capabilities are unchanged, and only the known skill-aware description field
differs. Everything in that sentence except the description is pinned here, so a
future harness that adds a tool, drops one, renames one or reshapes a schema
fails the comparison instead of being absorbed into "the Skill index changed".

Descriptions are deliberately *not* pinned. A description holds the names of the
Skills currently mounted, so its digest is a property of the Campaign's Skill
rather than of the harness, and pinning it would make the fixture wrong the
first time a different Skill was measured.

The fixture is recorded from real evaluations, never authored. Each file says
which ones in its own ``recorded_from`` field.
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from typing import Final

from techtree.models.base import Digest, NonEmptyString, ProtocolModel

__all__ = [
    "HARNESS_CONFORMANCE_SCHEMA_VERSION",
    "ConformanceTool",
    "HarnessConformance",
    "harness_conformance",
]

#: The schema every conformance fixture declares.
HARNESS_CONFORMANCE_SCHEMA_VERSION: Final = "techtree.harness-conformance.v1alpha1"

_RESOURCE_DIRECTORY: Final = "harness"


class ConformanceTool(ProtocolModel):
    """One tool the pinned harness offers, by name and parameter schema."""

    name: NonEmptyString
    parameters_digest: Digest


class HarnessConformance(ProtocolModel):
    """The tool surface one pinned harness build offers."""

    schema_version: NonEmptyString
    harness_id: NonEmptyString
    harness_version: NonEmptyString
    skill_index_tool: NonEmptyString
    recorded_from: NonEmptyString
    tools: list[ConformanceTool]

    @property
    def tool_names(self) -> list[str]:
        """Every tool name, in the order the fixture records them."""
        return [tool.name for tool in self.tools]

    @property
    def parameters_by_tool(self) -> dict[str, Digest]:
        """Each tool's parameter-schema digest, by tool name."""
        return {tool.name: tool.parameters_digest for tool in self.tools}


@cache
def harness_conformance(harness_id: str, harness_version: str) -> HarnessConformance:
    """Load the conformance fixture for one pinned harness build.

    Raises :class:`FileNotFoundError` when no fixture was ever recorded for that
    build, which is the correct outcome: a harness nobody measured has no
    expected tool surface, and inventing one would be the opposite of a
    conformance fixture.
    """
    resource = (
        resources.files("techtree")
        / "resources"
        / _RESOURCE_DIRECTORY
        / f"{harness_id}-{harness_version}.json"
    )
    if not resource.is_file():
        raise FileNotFoundError(
            f"no tool surface was recorded for {harness_id} {harness_version}"
        )
    document = json.loads(resource.read_text(encoding="utf-8"))
    conformance = HarnessConformance.model_validate(document)
    if conformance.schema_version != HARNESS_CONFORMANCE_SCHEMA_VERSION:
        raise ValueError(
            f"{resource} declares {conformance.schema_version}, not "
            f"{HARNESS_CONFORMANCE_SCHEMA_VERSION}"
        )
    return conformance
