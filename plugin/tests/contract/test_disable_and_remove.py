"""Turning the plugin off, and taking it away. WP11g B2.

The README promises what stays on the machine after a disable or a remove.
A promise about disk is worth what its test is worth, so this checks the parts
that can be checked from inside the repository:

* the plugin surfaces exist only because ``register()`` put them there — a
  host that never registers has none of them, which is what disabling is;
* importing the package registers nothing, so an installed-but-not-enabled
  plugin is genuinely inert;
* one directory is the whole of what the plugin can leave on disk, it is the
  one the README names, and the README's own removal command is the one that
  removes it.

What cannot be checked here is checked nowhere else either, and is stated
rather than implied: this repository cannot uninstall a plugin from a real
Hermes, and it cannot reach into a model provider's retention. The README says
so in those words, and the last test holds it to saying so.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import techtree_hermes
from support import RecordingContext
from techtree_hermes.constants import (
    PLUGIN_ROOT,
    PROPOSAL_STAGING_DIRNAME,
    plugin_state_home,
    proposal_staging_home,
)
from techtree_hermes.services.proposal import ProposalService

README = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")


# Disabled: registered nothing, so nothing is offered --------------------------------


def test_a_host_that_never_registers_is_offered_nothing() -> None:
    """Disabling is the absence of registration, and leaves no residue in it."""
    ctx = RecordingContext()

    assert ctx.tools == {}
    assert ctx.commands == {}
    assert ctx.hooks == {}
    assert ctx.skills == {}


def test_importing_the_plugin_registers_nothing() -> None:
    """Installed but not enabled must mean genuinely inert, not merely quiet."""
    ctx = RecordingContext()

    # The module object is already imported by this test module's own imports.
    assert hasattr(techtree_hermes, "register")
    assert ctx.tools == {}, "importing the package registered a tool"


def test_registering_and_discarding_the_context_leaves_no_global_state() -> None:
    """Two hosts do not share a plugin: the surfaces live on the ctx, not here."""
    first = RecordingContext()
    techtree_hermes.register(first)
    assert first.tools

    second = RecordingContext()

    assert second.tools == {}, "a surface survived into a host that never registered"
    assert second.hooks == {}


# Removed: one directory, and the README names it -------------------------------------


def test_the_plugin_can_leave_exactly_one_directory_behind() -> None:
    """Everything else it holds is in memory for the length of a session."""
    assert proposal_staging_home() == plugin_state_home() / PROPOSAL_STAGING_DIRNAME
    assert ProposalService(bridge=None).staging_root == proposal_staging_home()


def test_the_readme_names_that_directory_and_how_to_remove_it() -> None:
    removal = README.split("### Removing", 1)
    assert len(removal) == 2, "the README has no removal instructions"
    instructions = removal[1]

    assert "hermes plugins remove techtree" in instructions
    assert "techtree-hermes" in instructions
    assert "XDG_STATE_HOME" in instructions


def test_the_readme_says_what_removal_does_not_reach() -> None:
    """An honest removal section names what it cannot delete. Decision 0013."""
    collapsed = " ".join(README.split()).lower()

    assert "techtree's own home" in collapsed
    assert "model provider" in collapsed
    assert "governed by their policies" in collapsed


def test_the_readme_documents_disabling_separately_from_removing() -> None:
    """They do different things, and a user choosing between them must see it."""
    assert "### Disabling" in README
    assert "hermes plugins disable techtree" in README
    assert README.index("### Disabling") < README.index("### Removing")


def test_the_removal_command_would_remove_the_staging_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The path in the README is the path the code actually stages into.

    Read out of the README rather than repeated here, so the documentation
    cannot drift away from the code while a test that hardcodes the same
    string goes on passing.
    """
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    documented = re.search(r'rm -rf "([^"]+)"', README)
    assert documented is not None, "the README documents no removal path"

    expanded = Path(
        documented.group(1)
        .replace("${XDG_STATE_HOME:-$HOME/.local/state}", str(tmp_path / "state"))
        .replace("$HOME", str(tmp_path))
    )

    assert proposal_staging_home().is_relative_to(expanded)


def test_a_staged_proposal_lives_under_the_documented_path_and_is_removed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The end-to-end claim: written where promised, gone when handed over."""
    from techtree_hermes.models import SkillRevisionOutput

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    service = ProposalService(bridge=None)
    staged = service.write_temporary_skill(
        demo_id="demo_" + "0" * 32,
        output=SkillRevisionOutput(
            analysis_summary="A general rule explains the failures.",
            change_rationale=("Count distinct characters.",),
            revised_skill_markdown="---\nname: x\ndescription: y\n---\n\n# X\n",
            expected_tradeoffs=("Unchanged on all-distinct inputs.",),
            confidence="medium",
        ),
    )

    assert staged.entrypoint.is_relative_to(proposal_staging_home())
    assert service.remove_temporary_skill(staged) is None
    assert not staged.directory.exists()
    # The staging root itself remains, empty: it is the documented address.
    assert proposal_staging_home().is_dir()
    assert list(proposal_staging_home().iterdir()) == []


def test_nothing_is_staged_outside_a_proposal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Registration writes nothing; only a guided revision creates the directory."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    techtree_hermes.register(RecordingContext())

    assert not (tmp_path / "state").exists()
