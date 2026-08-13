"""The embedded release, and what it is compared against.

Specification sections 6.6 and 7.6. The digest a release is published under is
the SHA-256 of the stored file, so these tests are as much about the bytes as
about the fields.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from techtree_hermes.constants import PLUGIN_ROOT, RELEASE_CORE_FILENAME
from techtree_hermes.errors import PluginError
from techtree_hermes.release import (
    compare_bootstrap_release,
    compare_cli_release,
    document_digest,
    embedded_release_core_digest,
    is_canonical_document,
    load_embedded_release_core,
    release_core_digest,
    render_release_core,
)

EMBEDDED_PATH = PLUGIN_ROOT / RELEASE_CORE_FILENAME
CORE = load_embedded_release_core()


def _installed_facts(**overrides: Any) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "release_id": CORE.release_id,
        "cli_version": CORE.cli_version,
        "package_version": "0.1.0",
        "cli_source_commit": CORE.cli_source_commit,
        "protocol_version": CORE.protocol_version,
        "release_core_digest": release_core_digest(CORE),
        "engine_digest": CORE.engine_digest,
        "catalog_digest": CORE.catalog_digest,
        "intro_climb_reference": CORE.intro_climb_reference,
        "placeholder_release": CORE.placeholder_release,
        "placeholder_fields": list(CORE.placeholder_fields),
    }
    facts.update(overrides)
    return facts


# The stored bytes ---------------------------------------------------------------


def test_the_release_digest_is_the_digest_of_the_stored_file() -> None:
    """Anyone can check this release with shasum, in any repository."""
    raw = EMBEDDED_PATH.read_bytes()

    assert release_core_digest(CORE) == f"sha256:{hashlib.sha256(raw).hexdigest()}"
    assert embedded_release_core_digest() == release_core_digest(CORE)


def test_the_stored_file_is_in_the_one_published_spelling() -> None:
    raw = EMBEDDED_PATH.read_bytes()

    assert is_canonical_document(raw)
    assert render_release_core(CORE) == raw


def test_whitespace_that_changes_nothing_still_changes_the_digest(
    tmp_path: Path,
) -> None:
    payload = json.loads(EMBEDDED_PATH.read_bytes())
    reformatted = json.dumps(payload, indent=4, sort_keys=True).encode() + b"\n"

    assert not is_canonical_document(reformatted)
    assert document_digest(reformatted) != release_core_digest(CORE)


def test_a_rewritten_release_file_is_refused(tmp_path: Path) -> None:
    """A hand-edited file cannot carry the digest the release published."""
    payload = json.loads(EMBEDDED_PATH.read_bytes())
    (tmp_path / RELEASE_CORE_FILENAME).write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PluginError, match="published spelling"):
        load_embedded_release_core(tmp_path)


def test_the_release_says_whether_it_is_finished() -> None:
    """A release generated before every coordinate is chosen declares itself."""
    assert CORE.placeholder_release is (len(CORE.placeholder_fields) > 0)
    for name in CORE.placeholder_fields:
        assert name in {
            "cli_source_commit",
            "cli_version",
            "maximum_tested_host_hermes_version",
            "minimum_host_hermes_version",
            "release_id",
            "rich_output_skill_digest",
            "skill_improver_digest",
            "starter_skill_digest",
        }


# Comparison against an installed CLI ----------------------------------------------


def test_the_same_release_reports_no_mismatch() -> None:
    assert compare_cli_release(CORE, _installed_facts()) == []


def test_a_different_release_digest_is_reported() -> None:
    facts = _installed_facts(release_core_digest="sha256:" + "0" * 64)

    assert compare_cli_release(CORE, facts) == ["release_core_digest"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("release_id", "9.9.9"),
        ("cli_version", "9.9.9"),
        ("cli_source_commit", "f" * 40),
        ("protocol_version", "v2"),
        ("engine_digest", "sha256:" + "1" * 64),
        ("catalog_digest", "sha256:" + "2" * 64),
        ("intro_climb_reference", "something-else@1"),
    ],
)
def test_each_shared_coordinate_is_compared(field: str, value: str) -> None:
    mismatches = compare_cli_release(CORE, _installed_facts(**{field: value}))

    assert field in mismatches


def test_an_empty_answer_is_not_treated_as_agreement() -> None:
    assert compare_cli_release(CORE, {}) == ["installed_release_facts_missing"]


def test_a_truncated_answer_is_reported() -> None:
    facts = _installed_facts()
    del facts["engine_digest"]

    assert "installed_release_facts_missing" in compare_cli_release(CORE, facts)


# Comparison against a published bootstrap release ------------------------------------


def _bootstrap(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "release_core_digest": release_core_digest(CORE),
        "cli_version": CORE.cli_version,
        "plugin_repository": "regents-labs/techtree-hermes",
        "plugin_commit": "a" * 40,
    }
    document.update(overrides)
    return document


def test_a_website_release_that_names_this_build_agrees() -> None:
    assert compare_bootstrap_release(CORE, _bootstrap(), "a" * 40) == []


def test_a_website_release_naming_another_plugin_commit_is_reported() -> None:
    mismatches = compare_bootstrap_release(CORE, _bootstrap(), "b" * 40)

    assert mismatches == ["plugin_commit"]


def test_a_website_release_naming_another_core_is_reported() -> None:
    mismatches = compare_bootstrap_release(
        CORE,
        _bootstrap(release_core_digest="sha256:" + "9" * 64, cli_version="9.9.9"),
        None,
    )

    assert mismatches == ["release_core_digest", "cli_version"]
