"""Private shared profiles. Privy proof is separate from publication keys."""

from __future__ import annotations

import http.client
import json
import os
import queue
import re
import select
import signal
import socket
import sys
import threading
import time
from contextlib import suppress
from typing import Annotated, NoReturn
from urllib.parse import urlsplit

import typer

from techtree.cli.context import cli_context
from techtree.cli.invoke import CommandResult, invoke_command
from techtree.errors import TechtreeError, UsageError
from techtree.models.base import JsonValue
from techtree.models.cli import Operation

DEFAULT_ORIGIN = "https://techtree.sh"
_PROOF_TIMEOUT = 30


def _proof() -> dict[str, str]:
    if sys.stdin.isatty():
        raise UsageError(
            "Pipe paired Privy proof JSON from an approved credential provider."
        )
    try:
        # Read the pipe directly: a timed-out buffered reader thread can keep
        # stdin locked and abort Python during interpreter shutdown.
        fd = sys.stdin.fileno()
        deadline = time.monotonic() + _PROOF_TIMEOUT
        raw = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
                raise ValueError
            chunk = os.read(fd, 70001 - len(raw))
            if not chunk:
                break
            raw.extend(chunk)
            if len(raw) > 70000:
                raise ValueError
        pair = json.loads(raw)
        if not isinstance(pair, dict) or set(pair) != {"access", "identity"}:
            raise ValueError
        if not all(
            isinstance(token, str)
            and 0 < len(token) <= 32768
            and re.fullmatch(r"[A-Za-z0-9_.-]+", token)
            for token in pair.values()
        ):
            raise ValueError
        return {"access": pair["access"], "identity": pair["identity"]}
    except Exception:
        raise UsageError(
            "Could not read a valid paired Privy proof from stdin."
        ) from None


def _request(
    operation: str, origin: str, body: dict[str, JsonValue] | None
) -> CommandResult[dict[str, JsonValue]]:
    try:
        url = urlsplit(origin)
        if (
            (
                url.scheme != "https"
                and not (
                    url.scheme == "http"
                    and url.hostname in {"localhost", "127.0.0.1", "::1"}
                )
            )
            or url.username
            or url.password
            or url.path not in {"", "/"}
            or url.query
            or url.fragment
            or not url.hostname
        ):
            raise ValueError
        port = url.port
    except ValueError:
        raise UsageError("Provide an HTTPS origin or HTTP loopback fixture.") from None
    pair = _proof()
    method = {"get": "GET", "sync": "POST", "update": "PATCH"}[operation]
    path = "/api/v1/profile/sync" if operation == "sync" else "/api/v1/profile"
    connection_class = (
        http.client.HTTPSConnection
        if url.scheme == "https"
        else http.client.HTTPConnection
    )
    connection = connection_class(url.hostname, port, timeout=30)
    headers = {
        "accept": "application/json",
        "authorization": "Bearer " + pair["access"],
        "privy-id-token": pair["identity"],
    }
    if body is not None:
        headers["content-type"] = "application/json"
    received: queue.Queue[dict[str, JsonValue]] = queue.Queue(maxsize=1)
    cancelled = threading.Event()
    unavailable: dict[str, JsonValue] = {
        "ok": False,
        "status": None,
        "error": {"code": "profile_unavailable", "outcome_unknown": operation != "get"},
    }

    def exchange() -> None:
        try:
            connection.connect()
            if cancelled.is_set():
                return
            connection.request(
                method,
                path,
                body=json.dumps(body) if body is not None else None,
                headers=headers,
            )
            response = connection.getresponse()
            raw = response.read(1000001)
            if len(raw) > 1000000 or 300 <= response.status < 400:
                raise ValueError
            payload = json.loads(raw)
            normalized = json.dumps(payload)
            if (
                any(token in normalized for token in pair.values())
                or not isinstance(payload, dict)
                or not (
                    isinstance(payload.get("profile"), dict)
                    or (
                        isinstance(payload.get("error"), dict)
                        and isinstance(payload["error"].get("code"), str)
                    )
                )
            ):
                raise ValueError
            received.put(
                {
                    "ok": 200 <= response.status < 300,
                    "status": response.status,
                    "body": payload,
                }
            )
        except Exception:
            received.put(unavailable)
        finally:
            connection.close()

    def terminate(_signum: int, _frame: object) -> NoReturn:
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, terminate)
    try:
        threading.Thread(target=exchange, daemon=True).start()
        result = received.get(timeout=30)
    except (queue.Empty, KeyboardInterrupt):
        result = unavailable
    finally:
        cancelled.set()
        # Interrupt a trickling socket, not just idle reads. A late DNS result
        # checks cancelled before sending any request.
        active = connection.sock
        if active is not None:
            with suppress(OSError):
                active.shutdown(socket.SHUT_RDWR)
        signal.signal(signal.SIGTERM, previous)
    return CommandResult(
        data=result,
        error=None
        if result["ok"]
        else TechtreeError(
            "Profile request did not complete successfully. It was not retried.",
            code="profile_request_failed",
        ),
    )


def get_profile_command(
    ctx: typer.Context,
    base_url: Annotated[str, typer.Option("--base-url")] = DEFAULT_ORIGIN,
) -> NoReturn:
    invoke_command(
        cli_context(ctx), Operation.PROFILE_GET, lambda: _request("get", base_url, None)
    )


def sync_profile_command(
    ctx: typer.Context,
    base_url: Annotated[str, typer.Option("--base-url")] = DEFAULT_ORIGIN,
) -> NoReturn:
    invoke_command(
        cli_context(ctx),
        Operation.PROFILE_SYNC,
        lambda: _request("sync", base_url, None),
    )


def update_profile_command(
    ctx: typer.Context,
    display_name: Annotated[str | None, typer.Option("--display-name")] = None,
    wallet_address: Annotated[str | None, typer.Option("--wallet-address")] = None,
    clear_wallet: Annotated[bool, typer.Option("--clear-wallet")] = False,
    base_url: Annotated[str, typer.Option("--base-url")] = DEFAULT_ORIGIN,
) -> NoReturn:
    def update() -> CommandResult[dict[str, JsonValue]]:
        body: dict[str, JsonValue] = {}
        if display_name is not None:
            if len(display_name.encode()) > 320:
                raise UsageError("Display name is too long.")
            body["display_name"] = display_name
        if wallet_address is not None:
            if clear_wallet or not re.fullmatch(r"0x[a-fA-F0-9]{40}", wallet_address):
                raise UsageError(
                    "Provide a wallet address or --clear-wallet, not both."
                )
            body["wallet_address"] = wallet_address
        if clear_wallet:
            body["wallet_address"] = None
        if not body:
            raise UsageError(
                "Provide a display name, wallet address or --clear-wallet."
            )
        return _request("update", base_url, body)

    invoke_command(cli_context(ctx), Operation.PROFILE_UPDATE, update)
