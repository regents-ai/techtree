"""Offering to publish, and publishing. Decisions 0038, ticket techtree-python-tta.

Four behavioural rules live here, and each one exists because breaking it
would be invisible in the output:

*Publishing is offered only for a run whose proof verified.* The plugin reads
Techtree's own ``publish_run`` next action and relays it. It composes none, so
a result nobody checked cannot be offered — there is nothing there to read.

*The offer says a person has to answer.* ``requires_user_confirmation`` is what
tells a host agent to ask rather than act, and an offer that lost it would look
identical beside a result.

*The plugin never publishes without recording where the approval was given.*
Every call carries ``--yes --reviewed-on host-agent``. Without the second flag
the publication would record ``explicit_cli_review``, which is true of the
command line and false about the person, who answered in a conversation.

*The plugin still opens no connection.* Publishing reaches the run log because
the Techtree CLI does. Nothing added for this feature imports a networking
module, and the doctor's own check is what proves it.
"""

from __future__ import annotations

import ast
import json
from typing import Any

import pytest
from techtree_hermes.cli.constants import PLUGIN_ROOT
from techtree_hermes.cli.doctor import NETWORKING_MODULES
from techtree_hermes.cli.errors import ApprovalRequiredError
from techtree_hermes.services.approvals import (
    PUBLICATION_DISCLOSURE,
    REVIEWED_ON_HOST_AGENT,
    publish_arguments,
)
from techtree_hermes.tools.publish import publication_offer
from unit.test_tools import RUN_ID, FakeBridge, _call, _envelope, _services

PUBLISH_OFFER: dict[str, Any] = {
    "id": "publish_run",
    "label": "Publish this run to the public run log",
    "reason": "The proof just verified, so the run's own evidence travels with it.",
    "cli": ["techtree", "publish", RUN_ID],
    "hermes_tool": None,
    "hermes_args": None,
    "requires_user_confirmation": True,
}

VERIFY_PROOF: dict[str, Any] = {
    "id": "verify_proof",
    "label": "Verify this run's local proof",
    "reason": "It checks offline, from the bytes the run stored.",
    "cli": ["techtree", "proof", "verify", RUN_ID],
    "hermes_tool": None,
    "hermes_args": None,
    "requires_user_confirmation": False,
}


def _with_actions(command: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
    envelope = _envelope(command, {"verified": True, "kind": "bundle"})
    envelope["next_actions"] = actions
    return envelope


def _result_envelope(actions: list[dict[str, Any]]) -> dict[str, Any]:
    """A finished result the presentation service can compose, with next actions."""
    envelope = _envelope(
        "run result",
        {
            "presentation": {
                "verification_status": "verified",
                "proof_grade": "P1",
                "task_rows": [],
            },
            "report": None,
        },
    )
    envelope["next_actions"] = actions
    return envelope


# The offer ---------------------------------------------------------------------


def test_the_offer_is_read_out_of_techtrees_own_next_actions() -> None:
    """Techtree's words, carried across rather than written again."""
    offer = publication_offer(_with_actions("proof verify", [PUBLISH_OFFER]), RUN_ID)

    assert offer is not None
    assert offer["label"] == PUBLISH_OFFER["label"]
    assert offer["reason"] == PUBLISH_OFFER["reason"]
    assert offer["run_id"] == RUN_ID
    assert offer["tool"] == "techtree_publish_run"


def test_the_offer_says_a_person_has_to_answer() -> None:
    """The flag is the whole instruction to ask rather than act."""
    offer = publication_offer(_with_actions("proof verify", [PUBLISH_OFFER]), RUN_ID)

    assert offer is not None
    assert offer["requires_user_confirmation"] is True


def test_the_offer_carries_what_a_person_is_owed_before_answering() -> None:
    """A disclosure a host agent has to go and find is a disclosure nobody reads."""
    offer = publication_offer(_with_actions("proof verify", [PUBLISH_OFFER]), RUN_ID)

    assert offer is not None
    assert offer["disclosure"] == list(PUBLICATION_DISCLOSURE)


@pytest.mark.parametrize(
    "actions",
    [
        pytest.param([], id="no actions at all"),
        pytest.param([VERIFY_PROOF], id="every action but this one"),
    ],
)
def test_nothing_is_offered_when_techtree_offered_nothing(
    actions: list[dict[str, Any]],
) -> None:
    """A run whose proof did not verify carries no offer, so none is invented."""
    assert publication_offer(_with_actions("proof verify", actions), RUN_ID) is None


def test_an_envelope_with_no_next_actions_at_all_offers_nothing() -> None:
    """Malformed input is not a reason to guess."""
    assert publication_offer({"ok": True}, RUN_ID) is None


# The two surfaces that relay it -------------------------------------------------


def test_a_verified_result_relays_the_offer() -> None:
    bridge = FakeBridge({"run result": _result_envelope([PUBLISH_OFFER])})

    answer = _call("techtree_run_result", _services(bridge=bridge), {"run_id": RUN_ID})

    assert answer["publication_offer"]["requires_user_confirmation"] is True
    assert answer["publication_offer"]["run_id"] == RUN_ID


def test_a_result_nobody_verified_relays_no_offer() -> None:
    bridge = FakeBridge({"run result": _result_envelope([VERIFY_PROOF])})

    answer = _call("techtree_run_result", _services(bridge=bridge), {"run_id": RUN_ID})

    assert "publication_offer" not in answer


def test_a_passing_proof_check_relays_the_offer() -> None:
    bridge = FakeBridge(
        {"proof verify": _with_actions("proof verify", [PUBLISH_OFFER])}
    )

    answer = _call(
        "techtree_proof_verify", _services(bridge=bridge), {"run_id": RUN_ID}
    )

    assert answer["publication_offer"]["tool"] == "techtree_publish_run"


def test_a_failing_proof_check_relays_no_offer() -> None:
    bridge = FakeBridge({"proof verify": _with_actions("proof verify", [])})

    answer = _call(
        "techtree_proof_verify", _services(bridge=bridge), {"run_id": RUN_ID}
    )

    assert "publication_offer" not in answer


def test_a_bundle_somebody_was_handed_is_never_offered_publishing() -> None:
    """Publishing takes a run on this machine, and a path is not one.

    Techtree offers nothing for a directory outside the runs tree either, so
    this is belt and braces — but the plugin has the run identifier or it does
    not, and the case where it does not is the case where it must not guess.
    """
    bridge = FakeBridge(
        {"proof verify": _with_actions("proof verify", [PUBLISH_OFFER])}
    )

    answer = _call(
        "techtree_proof_verify", _services(bridge=bridge), {"proof_path": "/tmp/bundle"}
    )

    assert "publication_offer" not in answer


# Publishing ---------------------------------------------------------------------


def test_publishing_records_where_the_person_answered() -> None:
    """``--yes`` alone would say a flag was passed. This says a person answered."""
    assert publish_arguments(RUN_ID) == [
        RUN_ID,
        "--yes",
        "--reviewed-on",
        REVIEWED_ON_HOST_AGENT,
    ]


def test_there_is_no_run_to_publish_without_a_run() -> None:
    with pytest.raises(ApprovalRequiredError):
        publish_arguments("")


def test_the_publish_tool_always_carries_the_recorded_approval() -> None:
    """The flags are built, not passed in, so no argument can drop them."""
    bridge = FakeBridge(
        {f"publish {RUN_ID}": _envelope("publish", {"log_sequence": 7})}
    )

    _call("techtree_publish_run", _services(bridge=bridge), {"run_id": RUN_ID})

    assert bridge.last_argv() == [
        "publish",
        RUN_ID,
        "--yes",
        "--reviewed-on",
        "host-agent",
    ]


def test_the_publish_tool_records_that_a_person_approved_it() -> None:
    bridge = FakeBridge(
        {f"publish {RUN_ID}": _envelope("publish", {"log_sequence": 7})}
    )

    answer = _call("techtree_publish_run", _services(bridge=bridge), {"run_id": RUN_ID})

    assert answer["approval"]["kind"] == "publication.approved"
    assert answer["approval"]["run_id"] == RUN_ID
    assert answer["approval"]["reviewed_on"] == "host-agent"
    assert answer["approval"]["actor"] == "human_via_hermes"


def test_a_refused_publication_records_no_approval() -> None:
    """Nothing was published, so nothing about a publication is written down."""
    bridge = FakeBridge({f"publish {RUN_ID}": _envelope("publish", None, ok=False)})

    answer = _call("techtree_publish_run", _services(bridge=bridge), {"run_id": RUN_ID})

    assert answer["ok"] is False
    assert "approval" not in answer


def test_no_address_is_ever_sent_by_the_plugin() -> None:
    """An address in a tool call has passed through a model first.

    The command asks a person at a terminal whether they want to leave one, and
    that is the only place it is asked. Nothing in the tool's arguments can put
    one on the command line.
    """
    bridge = FakeBridge(
        {f"publish {RUN_ID}": _envelope("publish", {"log_sequence": 7})}
    )

    _call(
        "techtree_publish_run",
        _services(bridge=bridge),
        {"run_id": RUN_ID, "address": "0x" + "a" * 40},
    )

    assert "--address" not in bridge.last_argv()
    assert not any("0x" in argument for argument in bridge.last_argv())


def test_the_publish_tool_takes_a_run_identifier_and_nothing_else() -> None:
    """Decided at the schema, so the host refuses the argument before we do."""
    from techtree_hermes.host.schemas import all_tool_schemas

    schema = all_tool_schemas()["techtree_publish_run"]

    assert set(schema["properties"]) == {"run_id", "channel"}
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["run_id"]


# The boundary that must stay exactly where it is --------------------------------


def test_nothing_added_for_publishing_can_open_a_connection() -> None:
    """The plugin's guarantee is about the plugin, and it is unchanged.

    The doctor proves this for every runtime module; this narrows it to the two
    files this feature added or changed, so a networking import arriving here
    fails in the test that names the reason rather than in a whole-tree scan.
    """
    for name in ("tools/publish.py", "services/approvals.py"):
        source = (PLUGIN_ROOT / name).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=name)
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module
        }
        assert not imported & NETWORKING_MODULES, name


def test_the_publish_tool_reaches_techtree_the_only_way_anything_does() -> None:
    """One bridge call, and no second path invented for the one public step."""
    bridge = FakeBridge(
        {f"publish {RUN_ID}": _envelope("publish", {"log_sequence": 7})}
    )

    _call("techtree_publish_run", _services(bridge=bridge), {"run_id": RUN_ID})

    assert len(bridge.calls) == 1


def test_the_disclosure_separates_the_plugin_from_the_command_it_runs() -> None:
    """The copy boundary, held as a fact about the words rather than a hope.

    Two programs, two different facts. The plugin reaches no network; the CLI
    it runs does, after a yes. A disclosure that stated only the first would
    leave a reader thinking publishing cannot happen at all, and one that
    stated only the second would drop the guarantee the plugin actually makes.
    """
    text = " ".join(PUBLICATION_DISCLOSURE)

    assert "This plugin reaches no network." in text
    assert "Techtree CLI it runs is what talks to the run log" in text
    assert "only after the person has said yes" in text


def test_the_disclosure_says_what_the_log_is_and_is_not() -> None:
    """Decisions 0038: ranks nothing, withdrawn not deleted, nothing offered."""
    text = " ".join(PUBLICATION_DISCLOSURE)

    assert "ranks nothing" in text
    assert "no leaderboard" in text
    assert "It is not deleted." in text
    assert "nothing is offered in exchange" in text
    assert "never the episodes" not in text  # the disclosure says it in full below
    assert "does not send the episodes" in text


def test_the_offer_is_declared_to_the_host_the_way_the_start_is() -> None:
    """A tool that publishes is a tool a person confirms, and its schema says so."""
    from techtree_hermes.host.schemas import all_tool_schemas

    description = all_tool_schemas()["techtree_publish_run"]["description"]

    assert "REQUIRES USER CONFIRMATION" in description
    assert "This plugin reaches no network" in description


def test_the_manifest_declares_the_tool_the_handlers_implement() -> None:
    """A tool a host never hears about is a tool nobody can offer."""
    manifest = (PLUGIN_ROOT / "plugin.yaml").read_text(encoding="utf-8")

    assert "  - techtree_publish_run\n" in manifest


def test_the_offer_survives_an_answer_too_large_to_carry() -> None:
    """A truncated result keeps the offer; the whole point was to make it.

    A real Climb's result is several hundred kilobytes, and the reducing path
    keeps only a named few keys. The offer was the reason for the reading.
    """
    from techtree_hermes.tools import tool_result

    reduced = json.loads(
        tool_result(
            {
                "ok": True,
                "command": "run result",
                "publication_offer": {"id": "publish_run"},
                "filler": "x" * 200_000,
            }
        )
    )

    assert reduced["truncated"] is True
    assert reduced["publication_offer"] == {"id": "publish_run"}
