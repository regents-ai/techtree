"""The improvement context, against Techtree's own bytes. Sections 8.10, 8.21.

`tests/fixtures/context/improvement-context.json` is copied verbatim from the
Techtree repository's golden file, so the shape checked here is the shape
Techtree actually produces rather than one this plugin imagined.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from techtree_hermes.errors import PluginError
from techtree_hermes.services.improvement import (
    CONTEXT_FIELDS,
    public_prompts,
    validate_context,
)

GOLDEN = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "context"
    / "improvement-context.json"
)
CONTEXT: dict[str, Any] = json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_techtrees_own_context_is_accepted() -> None:
    validate_context(CONTEXT)


def test_the_context_carries_every_fingerprint_decision_0007_requires() -> None:
    """R2: source Skill root digest, entrypoint digest, run ID, report digest."""
    for name in (
        "parent_skill_digest",
        "parent_skill_entrypoint_digest",
        "source_run_id",
        "source_report_digest",
    ):
        assert isinstance(CONTEXT[name], str) and CONTEXT[name]


def test_the_context_fields_are_the_ones_this_plugin_expects() -> None:
    assert set(CONTEXT) == set(CONTEXT_FIELDS)


def test_no_subject_reply_survived_into_the_context() -> None:
    """R1: null for correct and incorrect episodes alike."""
    assert CONTEXT["examples"]
    for example in CONTEXT["examples"]:
        assert example["subject_reply"] is None


def test_no_hidden_answer_or_grader_material_is_present() -> None:
    """Scanned over the material itself.

    The context's own `prohibited_material` and `constraints` name the
    forbidden categories out loud — "hidden grader material", "expected
    answers" — which is the document being explicit rather than leaking, so
    they are not part of what gets scanned. The plugin's own check does not
    scan words at all; it refuses forbidden field names wherever they appear.
    """
    material = {
        name: value
        for name, value in CONTEXT.items()
        if name not in ("prohibited_material", "constraints")
    }
    document = json.dumps(material).lower()

    for word in ("expected_answer", "answer_key", "grader", "solution", "hidden"):
        assert word not in document


def test_no_credential_or_private_path_is_present() -> None:
    document = json.dumps(CONTEXT)

    assert "sk-" not in document
    assert "Bearer " not in document
    assert "/Users/" not in document
    assert "/home/" not in document


def test_the_public_prompts_are_what_a_revision_may_not_copy() -> None:
    prompts = public_prompts(CONTEXT)

    assert all(isinstance(prompt, str) and prompt for prompt in prompts)


def test_one_planted_answer_would_be_caught() -> None:
    """The check is a check, not a formality."""
    tampered = {**CONTEXT, "expected_answer": "42"}

    with pytest.raises(PluginError, match="hidden material"):
        validate_context(tampered)
