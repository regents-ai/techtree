"""Where an answer goes, and what that changes. Sections 6.1, 7.8, 7.15."""

from __future__ import annotations

import json
from typing import Any

import pytest
from techtree_hermes.channels import (
    DOCUMENTED_CHANNEL_KEYS,
    GATEWAY_TEXT_LIMIT,
    TRUNCATION_NOTE,
    bounded_gateway_text,
    ensure_gateway_safe,
    is_gateway_safe_required,
    resolve_channel,
)
from techtree_hermes.errors import ChannelError
from techtree_hermes.models import ChannelKind
from techtree_hermes.tools import tool_result


def test_an_explicit_hint_is_believed() -> None:
    assert resolve_channel("terminal") is ChannelKind.TERMINAL
    assert resolve_channel("gateway") is ChannelKind.GATEWAY
    assert resolve_channel(" Gateway ") is ChannelKind.GATEWAY


def test_no_hint_means_unknown() -> None:
    """The plugin never guesses from the operating system."""
    assert resolve_channel(None) is ChannelKind.UNKNOWN
    assert resolve_channel(None, {"platform": "darwin", "tty": True}) is (
        ChannelKind.UNKNOWN
    )


def test_no_callback_field_is_invented() -> None:
    """Hermes 0.20.0 hands a slash command the same way from a phone."""
    assert DOCUMENTED_CHANNEL_KEYS == ()


def test_a_documented_field_would_be_used(monkeypatch: pytest.MonkeyPatch) -> None:
    import techtree_hermes.channels as channels

    monkeypatch.setattr(channels, "DOCUMENTED_CHANNEL_KEYS", ("hermes_channel",))

    assert channels.resolve_channel(None, {"hermes_channel": "gateway"}) is (
        ChannelKind.GATEWAY
    )
    assert channels.resolve_channel(None, {"hermes_channel": "carrier pigeon"}) is (
        ChannelKind.UNKNOWN
    )


@pytest.mark.parametrize("named", ["console", "sms", ""])
def test_a_channel_that_does_not_exist_is_refused(named: str) -> None:
    with pytest.raises(ChannelError):
        resolve_channel(named)


def test_unknown_is_treated_as_a_gateway() -> None:
    assert is_gateway_safe_required(ChannelKind.UNKNOWN) is True
    assert is_gateway_safe_required(ChannelKind.GATEWAY) is True
    assert is_gateway_safe_required(ChannelKind.TERMINAL) is False


# Making text safe ---------------------------------------------------------------


@pytest.mark.parametrize(
    "hostile",
    [
        "\x1b[31mred\x1b[0m",
        "before\x00after",
        "carriage\rreturn",
        "\x9bcontrol sequence introducer",
    ],
)
def test_control_characters_never_survive(hostile: str) -> None:
    safe = ensure_gateway_safe(hostile)

    assert "\x1b" not in safe
    assert "\x00" not in safe
    assert "\r" not in safe
    assert "\x9b" not in safe


def test_ordinary_text_is_left_alone() -> None:
    text = "Run run_0123\tphase: completed\nProof: verified — 12 checks"

    assert ensure_gateway_safe(text) == text


def test_short_text_is_not_touched() -> None:
    assert bounded_gateway_text("a short answer") == "a short answer"


def test_long_text_is_cut_and_says_so() -> None:
    long_text = "\n".join(f"line {number} of the answer" for number in range(1000))

    bounded = bounded_gateway_text(long_text)

    assert len(bounded) <= GATEWAY_TEXT_LIMIT
    assert bounded.endswith(TRUNCATION_NOTE)
    assert "line 0 of the answer" in bounded


def test_a_cut_does_not_split_a_word() -> None:
    digest = "sha256:" + "a" * 64
    text = " ".join([digest] * 500)

    bounded = bounded_gateway_text(text)
    body = bounded[: -len(TRUNCATION_NOTE)]

    for fragment in body.split():
        assert fragment == digest


# What a channel changes about a tool answer -------------------------------------------


def _payload(size: int) -> dict[str, Any]:
    return {"ok": True, "command": "climb list", "rows": ["x" * 100] * size}


def test_a_terminal_may_receive_a_large_answer() -> None:
    answer = json.loads(tool_result(_payload(100), ChannelKind.TERMINAL))

    assert answer.get("truncated") is None
    assert len(answer["rows"]) == 100


def test_a_phone_receives_a_capped_answer_that_admits_it() -> None:
    answer = json.loads(tool_result(_payload(100), ChannelKind.GATEWAY))

    assert answer["truncated"] is True
    assert answer["code"] == "tool_result_too_large"
    assert answer["channel"] == "gateway"
    assert answer["ok"] is True


def test_an_unknown_channel_is_capped_like_a_phone() -> None:
    answer = json.loads(tool_result(_payload(100), ChannelKind.UNKNOWN))

    assert answer["truncated"] is True
    assert answer["channel"] == "unknown"


def test_a_capped_answer_still_carries_what_matters() -> None:
    payload = {**_payload(100), "run_id": "run_" + "0" * 32}

    answer = json.loads(tool_result(payload, ChannelKind.GATEWAY))

    assert answer["run_id"] == "run_" + "0" * 32
