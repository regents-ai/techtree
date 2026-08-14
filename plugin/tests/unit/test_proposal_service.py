"""Staging a proposal, and the diff a person sees. Sections 8.13, 8.14, 8.21."""

from __future__ import annotations

import os
import stat
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from techtree_hermes.diff import (
    GATEWAY_DIFF_LINES,
    build_skill_diff,
    text_digest,
)
from techtree_hermes.errors import PluginError
from techtree_hermes.models import ChannelKind, SkillRevisionOutput
from techtree_hermes.services.proposal import (
    ProposalService,
    validate_replacement_response,
)

RUN_ID = "run_" + "0" * 32
DRAFT_ID = "draft_" + "0" * 32

V1 = """---
name: branchcode
description: A procedure.
---

# BranchCode

## Step 5

Add seven times the TOTAL number of characters.
"""

V2 = V1.replace("TOTAL number", "number of DISTINCT")


def _output(markdown: str = V2) -> SkillRevisionOutput:
    return SkillRevisionOutput(
        analysis_summary="Every failure repeats a character.",
        change_rationale=("Step 5 should count distinct characters.",),
        revised_skill_markdown=markdown,
        expected_tradeoffs=("Identifiers with no repeats are unchanged.",),
        confidence="medium",
    )


def _prepared(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "draft_id": DRAFT_ID,
        "draft_digest": "sha256:" + "1" * 64,
        "confirmation_token": "confirmation-token-value",
        "confirmation_expires_at": "2026-08-13T12:00:00Z",
        "source_run_id": RUN_ID,
        "campaign_spec_digest": "sha256:" + "2" * 64,
        "data_policy_digest": "sha256:" + "3" * 64,
        "baseline_skill_digest": "sha256:" + "4" * 64,
        "candidate_skill_digest": "sha256:" + "5" * 64,
        "candidate_label": "revision",
        "included_files": ["SKILL.md"],
        "estimated_episodes": 72,
    }
    payload.update(overrides)
    return payload


class FakeBridge:
    def __init__(self, data: Any = None, ok: bool = True) -> None:
        self.calls: list[list[str]] = []
        self.data = _prepared() if data is None else data
        self.ok = ok
        self.skill_seen: str | None = None

    def invoke(self, arguments: Sequence[str]) -> dict[str, Any]:
        self.calls.append(list(arguments))
        if "--candidate-skill" in arguments:
            path = Path(arguments[list(arguments).index("--candidate-skill") + 1])
            self.skill_seen = path.read_text(encoding="utf-8")
        return {
            "schema_version": "techtree.cli.v1",
            "command": "uplift prepare",
            "ok": self.ok,
            "data": self.data if self.ok else None,
            "error": None
            if self.ok
            else {
                "code": "skill_scan_failed",
                "message": "the scanner refused this Skill",
                "retryable": False,
                "details": {},
            },
            "messages": [],
            "warnings": [],
            "next_actions": [],
        }


# Staging -----------------------------------------------------------------------


def test_a_proposed_skill_is_written_where_only_its_owner_can_read_it(
    tmp_path: Path,
) -> None:
    service = ProposalService(plugin_data_root=tmp_path, bridge=FakeBridge())

    staged = service.write_temporary_skill(demo_id="demo_abc", output=_output())

    assert staged.entrypoint.read_text(encoding="utf-8") == V2
    assert stat.S_IMODE(os.stat(staged.entrypoint).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(staged.directory).st_mode) == 0o700


def test_techtree_is_handed_the_path_and_does_the_judging(tmp_path: Path) -> None:
    """The scanner is Techtree's; the plugin never marks its own homework."""
    bridge = FakeBridge()
    service = ProposalService(plugin_data_root=tmp_path, bridge=bridge)
    staged = service.write_temporary_skill(demo_id="demo_abc", output=_output())

    prepared = service.prepare_replacement_draft(
        source_run_id=RUN_ID, skill_path=staged.entrypoint
    )

    assert bridge.calls[0][:4] == ["uplift", "prepare", "--from-run", RUN_ID]
    assert bridge.skill_seen == V2
    assert prepared["draft_id"] == DRAFT_ID


def test_the_plugins_copy_is_removed_once_techtree_has_its_own(
    tmp_path: Path,
) -> None:
    service = ProposalService(plugin_data_root=tmp_path, bridge=FakeBridge())
    staged = service.write_temporary_skill(demo_id="demo_abc", output=_output())

    service.remove_temporary_skill(staged)

    assert not staged.entrypoint.exists()
    assert not staged.directory.exists()


def test_a_scanner_refusal_is_reported_in_techtrees_own_words(tmp_path: Path) -> None:
    service = ProposalService(plugin_data_root=tmp_path, bridge=FakeBridge(ok=False))
    staged = service.write_temporary_skill(demo_id="demo_abc", output=_output())

    with pytest.raises(PluginError, match="scanner refused"):
        service.prepare_replacement_draft(
            source_run_id=RUN_ID, skill_path=staged.entrypoint
        )


# What a person must be told before approving ---------------------------------------


def test_a_complete_preparation_passes() -> None:
    validate_replacement_response(_prepared(), RUN_ID)


@pytest.mark.parametrize(
    "missing",
    [
        "draft_id",
        "confirmation_token",
        "data_policy_digest",
        "baseline_skill_digest",
        "candidate_skill_digest",
        "estimated_episodes",
    ],
)
def test_a_preparation_missing_what_approval_needs_is_refused(missing: str) -> None:
    with pytest.raises(PluginError, match="needs before approving"):
        validate_replacement_response(_prepared(**{missing: None}), RUN_ID)


def test_a_preparation_for_another_run_is_refused() -> None:
    with pytest.raises(PluginError, match="different run"):
        validate_replacement_response(_prepared(), "run_" + "9" * 32)


def test_a_revision_identical_to_the_original_is_refused() -> None:
    """Comparing a Skill against itself would spend money to learn nothing."""
    same = "sha256:" + "4" * 64

    with pytest.raises(PluginError, match="nothing to compare") as raised:
        validate_replacement_response(
            _prepared(baseline_skill_digest=same, candidate_skill_digest=same), RUN_ID
        )

    assert raised.value.code == "skill_revision_unchanged"


# The diff --------------------------------------------------------------------------


def test_the_diff_shows_what_changed() -> None:
    difference = build_skill_diff(v1_text=V1, v2_text=V2)

    assert difference.added_lines == 1
    assert difference.removed_lines == 1
    assert "DISTINCT" in difference.unified
    assert "TOTAL" in difference.unified


def test_the_same_two_skills_always_produce_the_same_diff() -> None:
    """Deterministic: what was approved can be checked against what ran."""
    first = build_skill_diff(v1_text=V1, v2_text=V2)
    second = build_skill_diff(v1_text=V1, v2_text=V2)

    assert first.unified == second.unified
    assert first.diff_digest == second.diff_digest
    assert first.v1_digest == text_digest(V1)
    assert first.v2_digest == text_digest(V2)


def test_a_different_revision_produces_a_different_diff_digest() -> None:
    one = build_skill_diff(v1_text=V1, v2_text=V2)
    other = build_skill_diff(v1_text=V1, v2_text=V2 + "\nOne more rule.\n")

    assert one.diff_digest != other.diff_digest


def test_two_identical_skills_have_no_diff() -> None:
    difference = build_skill_diff(v1_text=V1, v2_text=V1)

    assert difference.is_empty
    assert difference.unified == ""


def test_a_phone_gets_a_bounded_diff_that_says_it_was_cut() -> None:
    long_v2 = V1 + "".join(f"\n## Rule {n}\n\nDo the thing.\n" for n in range(200))

    difference = build_skill_diff(
        v1_text=V1, v2_text=long_v2, channel=ChannelKind.GATEWAY
    )

    assert difference.truncated_lines > 0
    assert "more diff lines are not shown here" in difference.unified
    assert difference.unified.count("\n") <= GATEWAY_DIFF_LINES + 4
    payload = difference.to_dict()
    assert payload["truncated"] is True
    assert "terminal" in payload["see_all_of_it"]


def test_the_counts_are_of_the_whole_diff_even_when_it_is_cut() -> None:
    """A phone is told how much changed, not only how much it can see."""
    long_v2 = V1 + "".join(f"\n## Rule {n}\n" for n in range(200))

    bounded = build_skill_diff(v1_text=V1, v2_text=long_v2, channel=ChannelKind.GATEWAY)
    whole = build_skill_diff(v1_text=V1, v2_text=long_v2, channel=ChannelKind.TERMINAL)

    assert bounded.added_lines == whole.added_lines
    assert bounded.changed_lines == whole.changed_lines


def test_a_diff_never_carries_control_characters() -> None:
    difference = build_skill_diff(v1_text=V1, v2_text=V2 + "\x1b[31mred\x1b[0m\n")

    assert "\x1b" not in difference.unified


# Where a proposal is staged ---------------------------------------------------------
#
# WP11g S9. The staging root used to fall back to the shared OS temporary
# directory, and a failed cleanup was swallowed — so participant Skill content
# could be orphaned somewhere nobody had been told to look.


def test_the_default_staging_root_is_the_plugins_own(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Not the shared OS temp dir: a documented, plugin-owned address."""
    import tempfile

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    root = ProposalService(bridge=FakeBridge()).staging_root

    assert root == tmp_path / "state" / "techtree-hermes" / "proposals"
    assert Path(tempfile.gettempdir()) not in root.parents


def test_the_staging_root_is_named_in_the_removal_documentation() -> None:
    """A location nobody documented is a location nobody can clean up."""
    from techtree_hermes.constants import PLUGIN_ROOT

    readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")

    assert "techtree-hermes/proposals" in readme
    assert "XDG_STATE_HOME" in readme


def test_staging_creates_private_directories_all_the_way_down(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    service = ProposalService(bridge=FakeBridge())

    staged = service.write_temporary_skill(demo_id="demo_" + "0" * 32, output=_output())

    for directory in (service.staging_root, staged.directory):
        assert stat.S_IMODE(os.stat(directory).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(staged.entrypoint).st_mode) == 0o600
    assert staged.directory.parent == service.staging_root


def test_a_clean_removal_reports_nothing_and_leaves_nothing(tmp_path: Path) -> None:
    service = ProposalService(plugin_data_root=tmp_path, bridge=FakeBridge())
    staged = service.write_temporary_skill(demo_id="demo_" + "0" * 32, output=_output())

    assert service.remove_temporary_skill(staged) is None
    assert not staged.entrypoint.exists()
    assert not staged.directory.exists()


def test_a_removal_that_fails_says_where_the_file_still_is(tmp_path: Path) -> None:
    """A swallowed cleanup failure is content on disk nobody knows about."""
    service = ProposalService(plugin_data_root=tmp_path, bridge=FakeBridge())
    staged = service.write_temporary_skill(demo_id="demo_" + "0" * 32, output=_output())
    # Something else in the directory: rmdir cannot succeed.
    (staged.directory / "left-behind.txt").write_text("x", encoding="utf-8")

    failure = service.remove_temporary_skill(staged)

    assert failure is not None
    assert str(staged.directory) in failure
    assert "could not be removed" in failure
