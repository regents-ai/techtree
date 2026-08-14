"""The next step ``skill starter`` prints. Decisions 0010 item 5.

A materialized Skill lives in a directory Techtree named after the digest it
was verified against — seventy-one characters of hexadecimal. The command that
puts it there also prints the command to prepare it, and for a while that
printed command named no label, so the preparation fell back to the directory
name and refused it: seventy-one characters is longer than a candidate label
may be. Following the guided first run exactly as printed did not work.

The ruling is wider than the bug. A path is never a name and never a label, in
either direction: not the cache directory, not a temporary directory, not the
last segment of a download URL, not a filename. So the answer carries three
separate values — where the Skill is, what it is called, what a candidate
carrying it is filed under — and the printed command takes the path from the
first and the label from the third.

What is proved here is that the separation holds against paths chosen to break
it: one over two hundred characters long, one with spaces in every parent, and
the digest-named cache directory itself, which is present in all of them
because it is where materialization always puts the Skill. The verbatim
end-to-end run of the printed arguments lives in ``test_cli_flow``, where a
real engine and the shipped catalog exist for it to run against.

Decisions document 0010 item 2 adds a fourth value to the same answer, and it
is proved here for the same reason: the starter Skill is deliberately
incomplete, its own text says nothing about that, and the disclosure has to
reach whoever is handed it. So the command that hands it over names the
purpose beside the Skill, in the human output and in the machine envelope
alike.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from fixtures.starter import STARTER_FIXTURE, tree_digest
from fixtures.starter import release_pinning as release
from techtree.cli.app import create_app
from techtree.constants import (
    STARTER_SKILL_CANDIDATE_LABEL,
    STARTER_SKILL_NAME,
    STARTER_SKILL_PURPOSE,
)
from techtree.errors import EXIT_OK
from techtree.paths import paths_from_root
from techtree.release.document import render_release_core

pytestmark = pytest.mark.integration

#: A directory name a person would never type and a label could never hold.
DIGEST_DIRECTORY_LENGTH = len("sha256-") + 64


@pytest.fixture
def pinned_release(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make the command see a release that has chosen the fixture Skill.

    This build's own release pins no starter Skill, so the command's only
    reachable answer today is the honest refusal. Substituting the document
    the command reads — and nothing else — is what lets the successful path be
    exercised before the founder Skills are frozen.
    """
    document = render_release_core(release(tree_digest(STARTER_FIXTURE)))
    monkeypatch.setattr(
        "techtree.cli.commands.skill.packaged_release_core_bytes",
        lambda: document,
    )
    yield


def source_under(root: Path, *segments: str) -> Path:
    """Copy the fixture Skill to a source directory a test chose the shape of."""
    directory = root.joinpath(*segments)
    directory.mkdir(parents=True)
    entrypoint = directory / "SKILL.md"
    entrypoint.write_bytes((STARTER_FIXTURE / "SKILL.md").read_bytes())
    return entrypoint


def obtain(home: Path, source: Path) -> dict[str, Any]:
    """Run ``skill starter`` in machine mode and return its whole envelope."""
    result = CliRunner().invoke(
        create_app(),
        [
            "--home",
            str(home),
            "--json",
            "skill",
            "starter",
            "--from-file",
            str(source),
        ],
    )
    assert result.exit_code == EXIT_OK, result.stdout
    envelope: Any = json.loads(result.stdout.splitlines()[-1])
    assert isinstance(envelope, dict)
    assert envelope["ok"] is True, envelope.get("error")
    return envelope


#: Every source shape that has ever made something derive a name from a path.
SOURCE_SHAPES: dict[str, tuple[str, ...]] = {
    "ordinary": ("downloads", "starter"),
    "over_two_hundred_characters": (
        "deeply",
        "nested" * 12,
        "and" * 20,
        "still" * 12,
        "going" * 12,
    ),
    "spaces_in_every_parent": (
        "My Documents",
        "Techtree Skills",
        "hello world starter v1",
    ),
}


@pytest.fixture(params=sorted(SOURCE_SHAPES), ids=sorted(SOURCE_SHAPES))
def obtained(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    temp_techtree_home: Path,
    pinned_release: None,
) -> dict[str, Any]:
    """Materialize the starter Skill from one awkwardly named source."""
    source = source_under(tmp_path / "sources", *SOURCE_SHAPES[request.param])
    if request.param == "over_two_hundred_characters":
        assert len(str(source)) > 200
    return obtain(temp_techtree_home, source)


def test_the_answer_separates_the_path_the_name_and_the_label(
    obtained: dict[str, Any],
) -> None:
    """Three values, three fields, and no two of them equal by accident."""
    payload = obtained["data"]

    assert payload["skill_name"] == STARTER_SKILL_NAME
    assert payload["candidate_label"] == STARTER_SKILL_CANDIDATE_LABEL
    assert payload["candidate_label"] != payload["skill_name"]
    assert payload["skill_path"].endswith("/SKILL.md")
    assert Path(payload["skill_path"]).is_file()


def test_the_skill_is_cached_under_a_digest_named_directory(
    obtained: dict[str, Any], temp_techtree_home: Path
) -> None:
    """The directory a label must never be taken from, present in every case."""
    payload = obtained["data"]
    cache_directory = Path(payload["skill_path"]).parent

    assert (
        cache_directory.parent == paths_from_root(temp_techtree_home).skills_cache_dir()
    )
    assert len(cache_directory.name) == DIGEST_DIRECTORY_LENGTH
    assert cache_directory.name == "sha256-" + payload[
        "skill_root_digest"
    ].removeprefix("sha256:")


def test_the_printed_command_is_argv_elements_rather_than_a_line_of_shell(
    obtained: dict[str, Any],
) -> None:
    """A host agent executes this, so it arrives already split and unquoted."""
    argv = obtained["next_actions"][0]["cli"]

    assert isinstance(argv, list)
    assert all(isinstance(element, str) for element in argv)
    assert argv[:3] == ["techtree", "climb", "prepare"]
    # Spaces survive as one element rather than as a quoting problem.
    assert argv.count("--skill") == 1
    assert argv.count("--label") == 1


def test_the_printed_command_takes_its_path_and_its_label_from_different_places(
    obtained: dict[str, Any],
) -> None:
    """The whole ruling, stated as one assertion pair."""
    payload = obtained["data"]
    argv = obtained["next_actions"][0]["cli"]

    assert argv[argv.index("--skill") + 1] == payload["skill_path"]
    assert argv[argv.index("--label") + 1] == STARTER_SKILL_CANDIDATE_LABEL


def test_no_argument_of_the_printed_command_is_a_label_read_off_a_path(
    obtained: dict[str, Any], tmp_path: Path
) -> None:
    """No segment of any path involved is offered as the candidate's name."""
    payload = obtained["data"]
    argv = obtained["next_actions"][0]["cli"]
    label = argv[argv.index("--label") + 1]

    forbidden = {
        *Path(payload["skill_path"]).parts,
        *(tmp_path / "sources").parts,
        Path(payload["skill_path"]).parent.name,
        Path(payload["skill_path"]).name,
        Path(payload["skill_path"]).stem,
    }
    assert label not in forbidden
    assert "/" not in label
    assert "\\" not in label
    assert not label.startswith("sha256")


def test_the_answer_says_what_the_starter_skill_is_for(
    obtained: dict[str, Any],
) -> None:
    """Decisions 0010 item 2: the disclosure travels with the artifact."""
    payload = obtained["data"]

    assert payload["skill_purpose"] == STARTER_SKILL_PURPOSE
    assert payload["skill_purpose"] == "intentionally incomplete introductory Skill"


def test_the_human_output_names_the_skill_and_its_purpose_together(
    tmp_path: Path, temp_techtree_home: Path, pinned_release: None
) -> None:
    """A person reading the terminal is told the same thing a host agent is."""
    source = source_under(tmp_path / "sources", "downloads", "starter")
    result = CliRunner().invoke(
        create_app(),
        [
            "--home",
            str(temp_techtree_home),
            "--no-color",
            "skill",
            "starter",
            "--from-file",
            str(source),
        ],
    )

    assert result.exit_code == EXIT_OK, result.stdout
    printed = " ".join(result.stdout.split())
    assert f"Skill {STARTER_SKILL_NAME}" in printed
    assert f"Purpose {STARTER_SKILL_PURPOSE}" in printed
