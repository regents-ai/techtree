"""The command a person types. Decisions document 0038, founder ruling 2026-08-27.

``techtree publish <run-id>``. Not ``techtree proof publish``. Nothing has been
released, so this is a hard cut with no alias, and ``proof`` keeps ``verify`` and
nothing else.

The name is a contract rather than a preference. It is printed as a next action
by three surfaces, quoted in the plugin's operator Skill, and typed by a person
reading a page on the website, so a build that answered to a second spelling
would make every one of those places ambiguous, and a build that quietly moved
the name would break all of them at once.

Four things are held here. The command exists. The one it replaced does not.
The envelope calls itself by the new name, because a host agent branches on that
string. And no source file anywhere still prints the old spelling — held over the
tree rather than over the one function a reader happens to remember, since a
stale next action is exactly the kind of thing that survives a rename.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from fixtures.receipts.proof import PROOF_RUN_ID
from techtree.cli.app import create_app
from techtree.cli.commands.publish import PUBLISH_COMMAND
from techtree.publication.offer import publish_action
from techtree.publication.transport import CONTRIBUTOR_ADDRESS_HEADER

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "techtree"

#: Every way the old command could still be written down: as a command line for
#: a person to type, and as the argument list of a ``NextAction``.
OLD_SPELLINGS = ("techtree proof publish", '"proof", "publish"', "proof publish")


def invoke(*arguments: str) -> Any:
    return CliRunner().invoke(create_app(), list(arguments))


def test_techtree_publish_exists() -> None:
    result = invoke("publish", "--help")

    assert result.exit_code == 0
    assert "RUN_ID" in result.stdout


def test_techtree_withdraw_exists() -> None:
    """The other half of the ruling: withdrawal is implemented, not promised."""
    result = invoke("withdraw", "--help")

    assert result.exit_code == 0
    assert "BUNDLE_DIGEST" in result.stdout


def test_techtree_proof_verify_still_exists() -> None:
    """``proof`` keeps ``verify``; it is where evidence is checked offline."""
    result = invoke("proof", "verify", "--help")

    assert result.exit_code == 0


def test_techtree_proof_publish_does_not_exist() -> None:
    """The hard cut, with no alias behind it."""
    result = invoke("proof", "publish", "--help")

    assert result.exit_code != 0


def test_proof_offers_only_verify() -> None:
    """Stated as the whole group, so a third member cannot arrive unnoticed."""
    result = invoke("proof", "--help")

    assert "verify" in result.stdout
    assert "publish" not in result.stdout


def test_the_envelope_calls_the_command_by_its_name(tmp_path: Path) -> None:
    """A host agent branches on this string, so it is the new one.

    Read off a real envelope rather than off the constant. The refusal here is
    the one a run nobody has on this machine gets, which is enough: what is being
    checked is the name the envelope carries, and every envelope carries it.
    """
    assert PUBLISH_COMMAND == "publish"

    result = invoke(
        "--home", str(tmp_path), "--json", "publish", "run_" + "0" * 32, "--yes"
    )

    assert json.loads(result.stdout)["command"] == "publish"


def test_the_offer_a_person_is_shown_is_the_command_that_exists() -> None:
    assert publish_action(PROOF_RUN_ID).cli == ["techtree", "publish", PROOF_RUN_ID]
    # A host agent asks rather than acts. Decisions 0038.
    assert publish_action(PROOF_RUN_ID).requires_user_confirmation is True


@pytest.mark.parametrize("spelling", OLD_SPELLINGS)
def test_no_shipped_file_still_prints_the_old_command(spelling: str) -> None:
    """Held over the package rather than over one function.

    Publishing is offered from the proof check, from a finished result, and from
    the command's own output, and a rename that missed one of them would leave a
    person a command line that does not run.
    """
    stale = [
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
        if spelling in path.read_text(encoding="utf-8")
    ]

    assert stale == [], f"these still name {spelling!r}: {stale}"


# ---------------------------------------------------------------------------
# Where the volunteered address travels
#
# Decisions 0038 blocker two. The whole privacy argument rests on the address
# being beside the submission rather than inside it: the run log stores the
# submission it is given and serves those exact bytes back at a public address,
# so an address in the body would be public by construction. Prose that said
# otherwise would not be a typo, it would be a description of a different and
# much worse design, so the two files that describe it are held to naming the
# header they mean.
# ---------------------------------------------------------------------------

#: The files that tell a reader where the address goes.
ADDRESS_PROSE_FILES = (
    "publication/models.py",
    "publication/transport.py",
    "cli/commands/publish.py",
)


@pytest.mark.parametrize("relative", ADDRESS_PROSE_FILES)
def test_the_prose_names_the_header_the_address_actually_travels_in(
    relative: str,
) -> None:
    text = (PACKAGE_ROOT / relative).read_text(encoding="utf-8")

    assert CONTRIBUTOR_ADDRESS_HEADER in text


#: Ways of writing down the design this one is not. Literal rather than
#: heuristic: the word "body" also appears inside "somebody", and a guard that
#: fired on that would be a guard somebody deleted.
WRONG_PHRASINGS = (
    "address travels in the request body",
    "address travels in the body",
    "address in the request body",
    "address in the submission",
    "address inside the submission",
    "address is part of the submission",
    "address in the body",
)


@pytest.mark.parametrize("relative", ADDRESS_PROSE_FILES)
def test_no_file_says_the_address_travels_in_what_is_published(
    relative: str,
) -> None:
    """The design this is not, spelled the ways somebody would spell it."""
    text = (PACKAGE_ROOT / relative).read_text(encoding="utf-8").lower()

    said = [phrase for phrase in WRONG_PHRASINGS if phrase in text]

    assert said == [], f"{relative} describes a design this is not: {said}"


@pytest.mark.parametrize("relative", ADDRESS_PROSE_FILES)
def test_the_separation_is_stated_and_not_only_implemented(relative: str) -> None:
    """Beside the submission, never inside it — in words, in all three files.

    The privacy argument is the reason for the header, so a file that named the
    header without saying why would leave the next person free to decide the
    separation was an implementation detail.
    """
    # Whitespace-normalised, because the sentence wraps in every one of them
    # and a rule that could be broken by a reflow would be noise.
    text = " ".join((PACKAGE_ROOT / relative).read_text(encoding="utf-8").split())

    assert "beside" in text
    assert "never inside it" in text
