"""What ``techtree publish`` puts in front of a person. Decisions 0038.

The command is the consent boundary, so what is tested here is the asking: that
nothing is sent without an answer, that the answer cannot be supplied by a
machine simply running the command, that what a person is shown before they
answer is what would actually be sent, and that the address question defaults to
no and promises nothing.

The transport is substituted at the one place the command builds it. Everything
else — the offline verification, the plan, the receipt, the journal — is the
real code, so a test that passes here is a test of the command a person runs.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Final

import pytest
from typer.testing import CliRunner

from fixtures.publication import (
    ADDRESS,
    COORDINATES,
    ENDPOINT,
    ENDPOINT_VARIABLE,
    PINNED_ENDPOINT,
    StubTransport,
)
from fixtures.receipts.proof import PROOF_RUN_ID, signed_proof, write_proof
from techtree.cli.app import create_app
from techtree.cli.commands import publish as publish_module
from techtree.cli.commands.publish import (
    ADDRESS_QUESTION,
    NOTHING_IS_OFFERED,
    PUBLICATION_CONFIRMATION_REQUIRED,
    publication_review_lines,
)
from techtree.errors import EXIT_OK, EXIT_USAGE, EXIT_VERIFICATION
from techtree.publication.journal import PublicationJournal
from techtree.publication.service import (
    PUBLICATION_RECEIPT_FILENAME,
    PublicationPlan,
    PublicationService,
)

#: The one transport every invocation in this module shares, so a test can look
#: at what the command sent after the process it ran in has exited. The address
#: has its own list because it does not travel in the body: the run log serves a
#: stored submission back at a public address, so it goes beside one.
SENT: Final[list[bytes]] = []
SENT_ADDRESSES: Final[list[str | None]] = []


class RecordingTransport(StubTransport):
    """The stub, at the one place the command builds a transport.

    The command constructs its own service, so the substitution happens on the
    name it constructs the transport from. What it records goes into a module
    list because each invocation builds its own instance.
    """

    def submit(
        self, *, endpoint: str, body: bytes, contributor_address: str | None
    ) -> bytes:
        """Record the request where the test can read it, then answer."""
        SENT.append(body)
        SENT_ADDRESSES.append(contributor_address)
        return super().submit(
            endpoint=endpoint, body=body, contributor_address=contributor_address
        )


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a Techtree home holding one finished, verifiable run."""
    root = tmp_path / "home"
    root.mkdir()
    write_proof(signed_proof(root), root / "runs" / PROOF_RUN_ID)
    SENT.clear()
    SENT_ADDRESSES.clear()
    monkeypatch.setattr(publish_module, "HttpsPublicationTransport", RecordingTransport)
    # The release pins a real key whose private half nobody in this repository
    # holds, so a test that wants a receipt to verify has to publish against
    # coordinates it can sign for. Only the coordinates are substituted; every
    # check made against them is the real one.
    monkeypatch.setattr(
        publish_module, "packaged_publication_coordinates", lambda: COORDINATES
    )
    monkeypatch.setenv(ENDPOINT_VARIABLE, ENDPOINT)
    return root


def invoke(home: Path, *arguments: str, stdin: str | None = None) -> Any:
    return CliRunner().invoke(
        create_app(), ["--home", str(home), *arguments], input=stdin
    )


# ---------------------------------------------------------------------------
# Nothing goes anywhere without an answer
# ---------------------------------------------------------------------------


def test_a_machine_that_cannot_be_asked_is_told_which_flag_to_pass(
    home: Path,
) -> None:
    """Machine mode implies no input, so the question has to be answered already."""
    result = invoke(home, "--json", "publish", PROOF_RUN_ID)

    assert result.exit_code == EXIT_USAGE
    assert PUBLICATION_CONFIRMATION_REQUIRED in result.stdout
    assert SENT == []


def test_saying_no_at_the_prompt_sends_nothing(home: Path) -> None:
    result = invoke(home, "publish", PROOF_RUN_ID, stdin="n\nn\n")

    assert result.exit_code == EXIT_USAGE
    assert SENT == []
    assert not (home / "runs" / PROOF_RUN_ID / PUBLICATION_RECEIPT_FILENAME).exists()


def test_reviewed_on_without_yes_is_a_surface_nobody_answered_on(
    home: Path,
) -> None:
    """It states where an answer was given, so it cannot stand in for one."""
    result = invoke(
        home,
        "--json",
        "publish",
        PROOF_RUN_ID,
        "--reviewed-on",
        "host-agent",
    )

    assert result.exit_code == EXIT_USAGE
    assert SENT == []


def test_a_host_agent_that_asked_in_the_conversation_may_publish(
    home: Path,
) -> None:
    """The path decisions 0038 names: ``--yes --reviewed-on host-agent``."""
    result = invoke(
        home,
        "--json",
        "publish",
        PROOF_RUN_ID,
        "--yes",
        "--reviewed-on",
        "host-agent",
    )

    assert result.exit_code == EXIT_OK
    assert len(SENT) == 1
    assert (home / "runs" / PROOF_RUN_ID / PUBLICATION_RECEIPT_FILENAME).is_file()


def test_a_proof_that_does_not_verify_is_refused_before_anything_is_asked(
    home: Path,
) -> None:
    """The refusal this whole command exists to make."""
    receipt = (
        home / "runs" / PROOF_RUN_ID / "proof" / "receipts" / "candidate" / "0000.json"
    )
    receipt.write_bytes(receipt.read_bytes().replace(b"candidate", b"candidatE", 1))

    result = invoke(home, "--json", "publish", PROOF_RUN_ID, "--yes")

    assert result.exit_code == EXIT_VERIFICATION
    assert SENT == []


def test_a_build_with_nothing_configured_publishes_to_the_pinned_address(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decisions 0038's founder ruling: a stable release publishes out of the box.

    No environment variable, no settings file entry, and the run still goes to
    the address the release pins.
    """
    monkeypatch.delenv(ENDPOINT_VARIABLE)

    result = invoke(home, "--json", "publish", PROOF_RUN_ID, "--yes")

    assert result.exit_code == EXIT_OK
    assert len(SENT) == 1
    assert json.loads(result.stdout)["data"]["endpoint"] == PINNED_ENDPOINT


# ---------------------------------------------------------------------------
# What a person reads before answering
# ---------------------------------------------------------------------------


def test_the_review_says_how_much_goes_where_and_what_is_not_in_it(
    home: Path,
) -> None:
    """Everything a person needs before they can honestly say yes."""
    plan = _plan(home)

    review = "\n".join(publication_review_lines(plan))

    assert PROOF_RUN_ID in review
    assert f"{plan.file_count} files" in review
    assert f"{plan.byte_count} bytes" in review
    assert ENDPOINT in review
    assert plan.bundle_digest in review
    assert "No prompts and no replies" in review
    assert "withdrawn" in review


def test_the_review_is_printed_before_either_question(home: Path) -> None:
    """What would be sent is shown first, and both questions come after it.

    An address asked for before the review would be asked of somebody who does
    not yet know what they are being asked about, and the agreement at the end
    is the one that covers the whole of it.
    """
    result = invoke(home, "publish", PROOF_RUN_ID, stdin="n\nn\n")

    printed = " ".join(result.stdout.split())
    review = printed.index(f"Publishing run {PROOF_RUN_ID}")
    address = printed.index("Leave an address with this run?")
    publish = printed.index("Publish this run to the public log?")

    assert ENDPOINT in printed
    assert review < address < publish


# ---------------------------------------------------------------------------
# The offer, on the surface that has just checked the proof
# ---------------------------------------------------------------------------


def test_a_verified_proof_offers_publishing(home: Path) -> None:
    """Decisions 0038: the offer is made where the check has just passed."""
    result = invoke(home, "--json", "proof", "verify", PROOF_RUN_ID)
    envelope = json.loads(result.stdout)

    offer = next(
        action for action in envelope["next_actions"] if action["id"] == "publish_run"
    )
    assert offer["cli"] == ["techtree", "publish", PROOF_RUN_ID]
    # The host agent asks; it does not act.
    assert offer["requires_user_confirmation"] is True


def test_a_proof_that_does_not_verify_is_offered_no_such_thing(home: Path) -> None:
    """Never offer to publish a result whose own proof fails."""
    receipt = (
        home / "runs" / PROOF_RUN_ID / "proof" / "receipts" / "baseline" / "0000.json"
    )
    receipt.write_bytes(receipt.read_bytes().replace(b"baseline", b"baselinE", 1))

    result = invoke(home, "--json", "proof", "verify", PROOF_RUN_ID)
    envelope = json.loads(result.stdout)

    assert envelope["ok"] is False
    assert "publish_run" not in [action["id"] for action in envelope["next_actions"]]


def test_a_bundle_carried_here_from_elsewhere_is_offered_nothing(
    home: Path, tmp_path: Path
) -> None:
    """Publishing takes a run, and a directory on a memory stick is not one."""
    carried = tmp_path / "carried"
    shutil.copytree(home / "runs" / PROOF_RUN_ID / "proof", carried)

    result = invoke(home, "--json", "proof", "verify", str(carried))
    envelope = json.loads(result.stdout)

    assert envelope["data"]["verified"] is True
    assert "publish_run" not in [action["id"] for action in envelope["next_actions"]]


# ---------------------------------------------------------------------------
# The address question
# ---------------------------------------------------------------------------


def test_the_address_question_is_asked_once_and_defaults_to_no(
    home: Path,
) -> None:
    """A stray newline is a no, at both prompts and in that order."""
    result = invoke(home, "publish", PROOF_RUN_ID, stdin="\ny\n")

    assert result.exit_code == EXIT_OK
    assert result.stdout.count("Leave an address with this run?") == 1
    assert SENT_ADDRESSES == [None]


def test_the_address_question_says_nothing_is_offered_for_it(home: Path) -> None:
    """The hard boundary, in the words a person actually reads."""
    result = invoke(home, "publish", PROOF_RUN_ID, stdin="n\nn\n")

    printed = " ".join(result.stdout.split())
    assert " ".join(ADDRESS_QUESTION.split()) in printed
    assert " ".join(NOTHING_IS_OFFERED.split()) in printed


def test_an_address_given_at_the_prompt_is_sent_in_its_canonical_form(
    home: Path,
) -> None:
    result = invoke(home, "publish", PROOF_RUN_ID, stdin=f"y\n{ADDRESS}\ny\n")

    assert result.exit_code == EXIT_OK
    assert [ADDRESS.lower()] == SENT_ADDRESSES


def test_a_machine_publishing_without_the_option_sends_no_address(
    home: Path,
) -> None:
    """Nobody was asked, so nobody volunteered anything."""
    invoke(home, "--json", "publish", PROOF_RUN_ID, "--yes")

    assert SENT_ADDRESSES == [None]


def test_a_mistyped_address_stops_the_publication(home: Path) -> None:
    """One wrong character, and nothing is sent rather than sent wrongly."""
    wrong = ADDRESS[:-1] + ADDRESS[-1].upper()

    result = invoke(
        home, "--json", "publish", PROOF_RUN_ID, "--yes", "--address", wrong
    )

    assert result.exit_code != EXIT_OK
    assert "contributor_address_invalid" in result.stdout
    assert SENT == []


def test_the_envelope_says_whether_an_address_was_sent_and_never_which(
    home: Path,
) -> None:
    """A machine may know that one was left. Nothing may read back what it was."""
    result = invoke(
        home,
        "--json",
        "publish",
        PROOF_RUN_ID,
        "--yes",
        "--address",
        ADDRESS,
    )

    assert result.exit_code == EXIT_OK
    assert '"contributor_address_sent":true' in result.stdout
    assert ADDRESS.lower() not in result.stdout.lower()
    journal = (home / "runs" / PROOF_RUN_ID).joinpath("publication.jsonl")
    assert ADDRESS.lower() not in journal.read_text(encoding="utf-8").lower()


def test_the_run_is_recorded_as_published(home: Path) -> None:
    invoke(home, "--json", "publish", PROOF_RUN_ID, "--yes")

    entries = PublicationJournal(home / "runs" / PROOF_RUN_ID).entries()
    assert [entry.status.value for entry in entries] == ["pending", "published"]


def _plan(home: Path) -> PublicationPlan:
    """Return the plan the command would show, built by the real service."""
    from techtree.drafts.store import utc_now

    return PublicationService(
        runs_dir=home / "runs",
        coordinates=COORDINATES,
        endpoint_override=ENDPOINT,
        transport=RecordingTransport(),
        clock=utc_now,
    ).plan(PROOF_RUN_ID)


# ---------------------------------------------------------------------------
# What the result table says
# ---------------------------------------------------------------------------


def test_the_result_table_calls_the_log_position_a_sequence(home: Path) -> None:
    """Decisions 0038 blocker two: a sequence is not a rank and may have gaps.

    The log is ordered by arrival and ranks nothing, and "Position" is the one
    word in this table that would invite a reader to think otherwise.
    """
    result = invoke(home, "publish", PROOF_RUN_ID, stdin="n\ny\n")

    printed = " ".join(result.stdout.split())
    assert result.exit_code == EXIT_OK
    assert "Log sequence" in printed
    assert "Position" not in printed


def test_the_result_says_the_log_ranks_nothing(home: Path) -> None:
    """The claim itself, in the words a person reads when it has worked."""
    result = invoke(home, "publish", PROOF_RUN_ID, stdin="n\ny\n")

    printed = " ".join(result.stdout.split())
    assert "records arrivals in order and ranks nothing" in printed
