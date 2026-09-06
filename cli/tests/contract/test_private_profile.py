"""Private profile requests keep proofs out of output and publication keys separate."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from techtree.cli.commands import profile
from techtree.errors import UsageError

PAIR = {"access": "fixture.access.signature", "identity": "fixture.identity.signature"}


@pytest.mark.parametrize("raw", [b"", b"no", b"{}", b'{"access":"only"}', b"x" * 70001])
def test_invalid_proof_is_a_fixed_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, raw: bytes
) -> None:
    proof = tmp_path / "fixture-proof.json"
    proof.write_bytes(raw)
    with proof.open() as stream:
        monkeypatch.setattr(sys, "stdin", stream)
        with pytest.raises(
            UsageError, match="Could not read a valid paired Privy proof"
        ):
            profile._proof()


def test_stalled_proof_producer_exits_without_a_buffered_reader_thread() -> None:
    script = """
import resource
from techtree.cli.commands import profile
from techtree.errors import UsageError
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
profile._PROOF_TIMEOUT = 0.05
try:
    profile._proof()
except UsageError:
    print('refused')
"""
    with subprocess.Popen(
        [sys.executable, "-c", script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as child:
        # Keep the producer open past the deadline, just as a stalled adapter does.
        try:
            child.wait(timeout=5)
        finally:
            if child.poll() is None:
                child.kill()
        output, errors = child.communicate(timeout=2)
        assert child.returncode == 0
        assert output.strip() == b"refused"
        assert errors == b""


def test_private_methods_and_reflected_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[tuple[str, str, str | None, str | None, str | None]] = []

    class Handler(BaseHTTPRequestHandler):
        def respond(self) -> None:
            self.rfile.read(int(self.headers.get("content-length", "0")))
            requests.append(
                (
                    self.command,
                    self.path,
                    self.headers.get("authorization"),
                    self.headers.get("privy-id-token"),
                    self.headers.get("cookie"),
                )
            )
            payload = (
                {"profile": {"profile_id": "shared"}}
                if len(requests) < 4
                else {"error": {"code": PAIR["access"]}}
            )
            encoded = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        do_GET = respond  # noqa: N815 - standard-library callback
        do_POST = respond  # noqa: N815 - standard-library callback
        do_PATCH = respond  # noqa: N815 - standard-library callback

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(profile, "_proof", lambda: PAIR.copy())
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        for operation, method, path in [
            ("get", "GET", "/api/v1/profile"),
            ("sync", "POST", "/api/v1/profile/sync"),
            ("update", "PATCH", "/api/v1/profile"),
        ]:
            result = profile._request(
                operation,
                origin,
                {"display_name": "Shared"} if operation == "update" else None,
            )
            assert result.error is None
            assert requests[-1] == (
                method,
                path,
                "Bearer " + PAIR["access"],
                PAIR["identity"],
                None,
            )
        refused = profile._request("sync", origin, None)
        assert refused.data == {
            "ok": False,
            "status": None,
            "error": {"code": "profile_unavailable", "outcome_unknown": True},
        }
        assert len(requests) == 4
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
