"""The starter Skill, and only when it is provably the right one.

Specification section 7.10.
"""

from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace

import pytest
from techtree_hermes.cli.errors import PluginError
from techtree_hermes.cli.release import load_embedded_release_core
from techtree_hermes.services.assets import materialize_starter_skill

CORE = load_embedded_release_core()


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
        "schema_version": "techtree.cli.v2",
        "operation": "plan.prepare",
        "ok": ok,
        "state_digest": None,
        "facts": data,
        "unknowns": [],
        "blockers": [],
        "warnings": [],
        "content_refs": [],
        "next_actions": [],
        "error": error,
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
