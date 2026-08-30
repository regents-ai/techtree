"""Loading a Skill only when it is provably the right one.

Specification section 8.5, decision 0007 R2.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

import pytest
from techtree_hermes.cli.errors import PluginError
from techtree_hermes.cli.release import load_embedded_release_core
from techtree_hermes.services.assets import (
    bundled_skill_digest,
    expected_founder_skill_digest,
    file_digest,
    load_bundled_skill_text,
    load_verified_founder_skill,
    materialize_starter_skill,
    read_verified_skill,
    resolve_source_skill,
    source_skill_reference,
    verify_founder_skill_digests,
)
from techtree_hermes.services.models import ReleaseCore

CORE = load_embedded_release_core()
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "skills"


def _bundle(root: Path, name: str, text: str) -> str:
    """Write a Skill into a temporary build and return its digest."""
    directory = root / "skills" / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(text, encoding="utf-8")
    return file_digest(text.encode("utf-8"))


FIXTURE_IMPROVER = (FIXTURES / "skill-improver" / "SKILL.md").read_text("utf-8")


def _release_naming(*, improver: str) -> ReleaseCore:
    """Return a release that names this improver Skill."""
    return dataclasses.replace(CORE, skill_improver_digest=improver)


# What this build actually has -------------------------------------------------


def test_this_build_bundles_the_founder_skill() -> None:
    """The Skill ships with the plugin, beside the release that names it."""
    assert load_bundled_skill_text("skill-improver").startswith("---\n")


def test_this_release_names_its_improver_skill() -> None:
    """The release binds the improver by digest, so the guided turn can run."""
    assert expected_founder_skill_digest(CORE, "skill-improver") == (
        CORE.skill_improver_digest
    )


def test_the_bundled_improver_is_the_one_this_release_names() -> None:
    """The property the canonical rehearsal depends on, checked against real bytes.

    Not a fixture and not a temporary directory: the release this build ships
    and the Skill file this build ships, verified against each other exactly
    as the guided revision verifies them at the moment of use.
    """
    text = load_verified_founder_skill(CORE, "skill-improver")

    assert text.startswith("---\n")
    assert bundled_skill_digest("skill-improver") == CORE.skill_improver_digest
    verify_founder_skill_digests(CORE)


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


def test_every_founder_skill_is_verified_together(tmp_path: Path) -> None:
    release = _release_naming(
        improver=_bundle(tmp_path, "skill-improver", FIXTURE_IMPROVER)
    )

    verify_founder_skill_digests(release, tmp_path)


def test_a_release_missing_its_skill_is_blocked(tmp_path: Path) -> None:
    release = _release_naming(improver="sha256:" + "9" * 64)

    with pytest.raises(PluginError, match="does not bundle"):
        verify_founder_skill_digests(release, tmp_path)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", "empty"),
        ("   \n\n ", "empty"),
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


def test_only_a_founder_skill_has_this_contract(tmp_path: Path) -> None:
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


# The starter Skill this release pins -----------------------------------------------
#
# Ticket 06v. The plugin does not fetch, unpack, or hash the starter Skill: it
# asks Techtree for the one this release names, through the ordinary CLI
# boundary, and then checks that what came back is that Skill. These cover the
# three things that can happen — it works, it is the wrong Skill, or Techtree
# could not hand one over.

STARTER_SKILL_PATH = "/tmp/techtree-home/cache/skills/sha256-abc/SKILL.md"


def _starter_envelope(
    *, ok: bool = True, data: object = None, error: object = None
) -> dict[str, object]:
    """Return one ``skill starter`` envelope as the bridge would hand it over."""
    return {
        "schema_version": "techtree.cli.v1",
        "command": "skill starter",
        "ok": ok,
        "data": data,
        "error": error,
        "messages": [],
        "warnings": [],
        "next_actions": [],
    }


def _starter_payload(**overrides: object) -> dict[str, object]:
    """Return what ``techtree skill starter`` says when it succeeded."""
    return {
        "release_id": CORE.release_id,
        "skill_root_digest": CORE.starter_skill_digest,
        "skill_path": STARTER_SKILL_PATH,
        "skill_name": "hello-world-starter-v1",
        "skill_purpose": "intentionally incomplete introductory Skill",
        "candidate_label": "hello-world-v1",
        "file_count": 1,
        "total_bytes": 1496,
        "origin": "cache",
        "intro_climb_reference": CORE.intro_climb_reference,
        **overrides,
    }


class StarterBridge:
    """A bridge that answers the starter-Skill call with one prepared envelope."""

    def __init__(self, envelope: dict[str, object]) -> None:
        self.envelope = envelope
        self.calls: list[list[str]] = []

    def invoke(self, arguments: Sequence[str]) -> dict[str, object]:
        self.calls.append(list(arguments))
        return self.envelope


def _starter_services(envelope: dict[str, object]) -> SimpleNamespace:
    """Return a container whose only live part is the CLI boundary."""
    from techtree_hermes.services.assets import ReleaseSkillProvider

    return SimpleNamespace(
        bridge=StarterBridge(envelope),
        release_core=CORE,
        assets=ReleaseSkillProvider(),
    )


def test_the_starter_skill_comes_from_the_command_techtree_publishes() -> None:
    """The guided first run can prepare: one CLI call, and the Skill comes back."""
    services = _starter_services(_starter_envelope(data=_starter_payload()))

    result = materialize_starter_skill(services)

    assert services.bridge.calls == [["skill", "starter"]]
    assert result["skill_path"] == STARTER_SKILL_PATH
    assert result["skill_root_digest"] == CORE.starter_skill_digest
    assert result["candidate_label"] == "hello-world-v1"


def test_a_skill_that_is_not_the_one_this_release_names_is_refused() -> None:
    """The whole point of the provider: the digest is checked, and it bites."""
    services = _starter_services(
        _starter_envelope(data=_starter_payload(skill_root_digest="sha256:" + "e" * 64))
    )

    with pytest.raises(PluginError, match="not the one this release names") as raised:
        materialize_starter_skill(services)

    assert raised.value.code == "starter_skill_digest_mismatch"


def test_a_skill_returned_without_a_digest_is_refused() -> None:
    services = _starter_services(
        _starter_envelope(data=_starter_payload(skill_root_digest=""))
    )

    with pytest.raises(PluginError, match="without a digest") as raised:
        materialize_starter_skill(services)

    assert raised.value.code == "starter_skill_digest_mismatch"


@pytest.mark.parametrize(
    ("field", "expected"),
    [("skill_path", "without a local path"), ("candidate_label", "without the label")],
)
def test_a_skill_missing_what_preparing_needs_is_refused(
    field: str, expected: str
) -> None:
    services = _starter_services(
        _starter_envelope(data=_starter_payload(**{field: ""}))
    )

    with pytest.raises(PluginError, match=expected) as raised:
        materialize_starter_skill(services)

    assert raised.value.code == "starter_skill_unavailable"


def test_a_refusal_from_techtree_is_reported_in_techtrees_own_words() -> None:
    """Ticket 06v: the one error a new participant meets has to be the true one.

    Techtree knows why it could not hand a Skill over. The plugin repeats that
    sentence and that code, and offers no repair of its own — in particular it
    never tells somebody to update a Techtree that is working correctly.
    """
    services = _starter_services(
        _starter_envelope(
            ok=False,
            error={
                "code": "starter_skill_source_refused",
                "message": (
                    "the starter Skill could not be read from /tmp/nowhere: "
                    "no such skill path: /tmp/nowhere"
                ),
                "retryable": False,
                "details": {"path": "/tmp/nowhere"},
            },
        )
    )

    with pytest.raises(PluginError, match="no such skill path") as raised:
        materialize_starter_skill(services)

    assert raised.value.code == "starter_skill_source_refused"
    assert raised.value.repair is None


def test_a_refusal_with_no_words_still_says_what_failed() -> None:
    services = _starter_services(_starter_envelope(ok=False))

    with pytest.raises(PluginError, match="could not put the starter Skill") as raised:
        materialize_starter_skill(services)

    assert raised.value.code == "starter_skill_unavailable"


def test_an_answer_with_nothing_to_read_is_refused() -> None:
    services = _starter_services(_starter_envelope(data=None))

    with pytest.raises(PluginError, match="nothing to read") as raised:
        materialize_starter_skill(services)

    assert raised.value.code == "starter_skill_unavailable"
