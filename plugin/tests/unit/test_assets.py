"""Loading a Skill only when it is provably the right one.

Specification section 8.5, decision 0007 R2 and R10.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Sequence
from pathlib import Path

import pytest
from techtree_hermes.errors import PluginError
from techtree_hermes.models import ReleaseCore
from techtree_hermes.release import load_embedded_release_core
from techtree_hermes.services.assets import (
    PLACEHOLDER_DIGEST,
    bundled_skill_digest,
    expected_founder_skill_digest,
    file_digest,
    load_bundled_skill_text,
    load_verified_founder_skill,
    names_a_founder_skill,
    read_verified_skill,
    resolve_source_skill,
    source_skill_reference,
    verify_founder_skill_digests,
)

CORE = load_embedded_release_core()
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "skills"


def _bundle(root: Path, name: str, text: str) -> str:
    """Write a Skill into a temporary build and return its digest."""
    directory = root / "skills" / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(text, encoding="utf-8")
    return file_digest(text.encode("utf-8"))


def _release_naming(
    *, rich: str = PLACEHOLDER_DIGEST, improver: str = PLACEHOLDER_DIGEST
) -> ReleaseCore:
    """Return a finished release that names these two Skills."""
    return dataclasses.replace(
        CORE,
        placeholder_release=False,
        placeholder_fields=(),
        rich_output_skill_digest=rich,
        skill_improver_digest=improver,
    )


FIXTURE_RICH = (FIXTURES / "rich-terminal-output" / "SKILL.md").read_text("utf-8")
FIXTURE_IMPROVER = (FIXTURES / "skill-improver" / "SKILL.md").read_text("utf-8")


# What this build actually has -------------------------------------------------


def test_this_build_bundles_no_founder_skill() -> None:
    """The two founder Skills are the last unchosen release coordinates."""
    for name in ("rich-terminal-output", "skill-improver"):
        with pytest.raises(PluginError, match="does not bundle"):
            load_bundled_skill_text(name)


def test_this_release_names_no_founder_skill() -> None:
    for name in ("rich-terminal-output", "skill-improver"):
        assert names_a_founder_skill(CORE, name) is False
        assert expected_founder_skill_digest(CORE, name) == PLACEHOLDER_DIGEST


def test_a_placeholder_release_cannot_verify_a_skill(tmp_path: Path) -> None:
    """Even with a file present, an unchosen Skill is not a founder Skill."""
    _bundle(tmp_path, "skill-improver", FIXTURE_IMPROVER)

    with pytest.raises(PluginError, match="has not chosen") as raised:
        load_verified_founder_skill(CORE, "skill-improver", tmp_path)

    assert raised.value.code == "founder_skill_missing"


# Loading by exact digest --------------------------------------------------------


def test_a_skill_that_matches_the_release_loads(tmp_path: Path) -> None:
    digest = _bundle(tmp_path, "skill-improver", FIXTURE_IMPROVER)
    release = _release_naming(improver=digest)

    text = load_verified_founder_skill(release, "skill-improver", tmp_path)

    assert text == FIXTURE_IMPROVER
    assert bundled_skill_digest("skill-improver", tmp_path) == digest


def test_one_altered_character_refuses_the_skill(tmp_path: Path) -> None:
    digest = _bundle(tmp_path, "skill-improver", FIXTURE_IMPROVER)
    release = _release_naming(improver=digest)
    _bundle(tmp_path, "skill-improver", FIXTURE_IMPROVER + "\n")

    with pytest.raises(PluginError, match="not the one this release names") as raised:
        load_verified_founder_skill(release, "skill-improver", tmp_path)

    assert raised.value.code == "founder_skill_digest_mismatch"


def test_both_skills_are_verified_together(tmp_path: Path) -> None:
    release = _release_naming(
        rich=_bundle(tmp_path, "rich-terminal-output", FIXTURE_RICH),
        improver=_bundle(tmp_path, "skill-improver", FIXTURE_IMPROVER),
    )

    verify_founder_skill_digests(release, tmp_path)


def test_a_release_missing_one_skill_is_blocked(tmp_path: Path) -> None:
    release = _release_naming(
        rich=_bundle(tmp_path, "rich-terminal-output", FIXTURE_RICH),
        improver="sha256:" + "9" * 64,
    )

    with pytest.raises(PluginError, match="does not bundle"):
        verify_founder_skill_digests(release, tmp_path)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", "empty"),
        ("   \n\n ", "empty"),
        ("# Skill\nOPENAI_API_KEY=sk-live-abcdefghijklmnop\n", "credential"),
        ("# Skill\nAuthorization: Bearer abc123DEF456ghi\n", "credential"),
    ],
)
def test_an_unusable_skill_file_is_refused(
    tmp_path: Path, text: str, expected: str
) -> None:
    _bundle(tmp_path, "skill-improver", text)

    with pytest.raises(PluginError, match=expected):
        load_bundled_skill_text("skill-improver", tmp_path)


def test_a_skill_larger_than_was_reviewed_is_refused(tmp_path: Path) -> None:
    _bundle(tmp_path, "skill-improver", "# Skill\n" + "x" * 300_000)

    with pytest.raises(PluginError, match="larger than"):
        load_bundled_skill_text("skill-improver", tmp_path)


def test_only_the_two_founder_skills_have_this_contract(tmp_path: Path) -> None:
    _bundle(tmp_path, "operator", "# Operator\n")

    with pytest.raises(PluginError, match="not a founder Skill"):
        load_bundled_skill_text("operator", tmp_path)


# The Skill a run was measured with -------------------------------------------------


def test_a_snapshot_that_matches_its_digest_is_read(tmp_path: Path) -> None:
    text = "# Subject Skill\nStep 5: add seven times the distinct characters.\n"
    snapshot = tmp_path / "skill"
    snapshot.mkdir()
    (snapshot / "SKILL.md").write_text(text, encoding="utf-8")
    entrypoint_digest = f"sha256:{hashlib.sha256(text.encode()).hexdigest()}"

    verified = read_verified_skill(
        snapshot,
        expected_entrypoint_digest=entrypoint_digest,
        root_digest="sha256:" + "a" * 64,
    )

    assert verified.text == text
    assert verified.entrypoint_digest == entrypoint_digest
    assert verified.root_digest == "sha256:" + "a" * 64


def test_a_snapshot_that_does_not_match_is_refused(tmp_path: Path) -> None:
    """The text a proposal is made against must be the text the run measured."""
    snapshot = tmp_path / "skill"
    snapshot.mkdir()
    (snapshot / "SKILL.md").write_text("# Something else\n", encoding="utf-8")

    with pytest.raises(PluginError, match="not the Skill the run measured") as raised:
        read_verified_skill(
            snapshot,
            expected_entrypoint_digest="sha256:" + "b" * 64,
            root_digest="sha256:" + "a" * 64,
        )

    assert raised.value.code == "founder_skill_digest_mismatch"


def test_a_skill_is_never_read_out_without_a_digest_to_check_it_by(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "skill"
    snapshot.mkdir()
    (snapshot / "SKILL.md").write_text("# Subject Skill\n", encoding="utf-8")

    with pytest.raises(PluginError, match="which Skill it is"):
        read_verified_skill(
            snapshot, expected_entrypoint_digest="", root_digest="sha256:" + "a" * 64
        )


def test_a_snapshot_with_no_entrypoint_is_refused(tmp_path: Path) -> None:
    snapshot = tmp_path / "skill"
    snapshot.mkdir()

    with pytest.raises(PluginError, match=r"no SKILL\.md"):
        read_verified_skill(
            snapshot,
            expected_entrypoint_digest="sha256:" + "b" * 64,
            root_digest="sha256:" + "a" * 64,
        )


def test_a_snapshot_carrying_a_credential_is_never_read_out(tmp_path: Path) -> None:
    text = "# Subject Skill\nuse OPENAI_API_KEY=sk-live-abcdefghijklmnop\n"
    snapshot = tmp_path / "skill"
    snapshot.mkdir()
    (snapshot / "SKILL.md").write_text(text, encoding="utf-8")

    with pytest.raises(PluginError, match="credential"):
        read_verified_skill(
            snapshot,
            expected_entrypoint_digest=f"sha256:{hashlib.sha256(text.encode()).hexdigest()}",
            root_digest="sha256:" + "a" * 64,
        )


# What the improvement context pins ----------------------------------------------


def _context_envelope(**overrides: str) -> dict[str, object]:
    context = {
        "schema_version": "techtree.skill-improvement-context.v1",
        "source_run_id": "run_" + "0" * 32,
        "parent_skill_digest": "sha256:" + "c" * 64,
        "campaign_spec_digest": "sha256:" + "d" * 64,
        "data_policy_digest": "sha256:" + "e" * 64,
    }
    context.update(overrides)
    return {"ok": True, "data": {"context": context, "relative_path": "context.json"}}


def test_the_context_pins_the_skill_by_digest() -> None:
    reference = source_skill_reference(_context_envelope())

    assert reference.parent_skill_digest == "sha256:" + "c" * 64
    assert reference.source_run_id == "run_" + "0" * 32


@pytest.mark.parametrize("missing", ["parent_skill_digest", "source_run_id"])
def test_a_context_that_pins_nothing_is_refused(missing: str) -> None:
    envelope = _context_envelope(**{missing: ""})

    with pytest.raises(PluginError, match="does not pin"):
        source_skill_reference(envelope)


def test_something_that_is_not_a_context_is_refused() -> None:
    with pytest.raises(PluginError, match="not an improvement context"):
        source_skill_reference({"ok": True, "data": None})


class ContextBridge:
    """A bridge that answers the improvement-context call."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def invoke(self, arguments: Sequence[str]) -> dict[str, object]:
        self.calls.append(list(arguments))
        return _context_envelope()


def test_reading_the_measured_skill_stops_where_techtree_stops() -> None:
    """The run owns its copy, and no command yet says where it is."""
    from types import SimpleNamespace

    bridge = ContextBridge()
    services = SimpleNamespace(bridge=bridge)

    with pytest.raises(PluginError, match="does not yet report where") as raised:
        resolve_source_skill(services, "run_" + "0" * 32)

    assert raised.value.code == "source_skill_snapshot_unavailable"
    assert bridge.calls == [["uplift", "context", "run_" + "0" * 32]]
    assert "entrypoint digest" in str(raised.value.repair)


def test_a_context_techtree_refused_reports_techtrees_own_reason() -> None:
    envelope = {
        "ok": False,
        "data": None,
        "error": {
            "code": "run_not_found",
            "message": "there is no run called run_000",
            "retryable": False,
            "details": {},
        },
    }

    with pytest.raises(PluginError, match="no run called"):
        source_skill_reference(envelope)
