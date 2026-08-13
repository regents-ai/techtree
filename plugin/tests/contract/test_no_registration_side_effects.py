"""Loading the plugin does nothing to the machine.

Specification sections 7.4, 7.15, 7.16, and the binding rule in section 16
that no plugin may install during ``register()``.

This is the plugin's most important test. A user who lists, installs, or
enables plugins has approved exactly that and nothing else. So registration is
held to a hard line here: with every way of starting a process, opening a
socket, or writing a file replaced by a tripwire, ``register()`` must still
finish normally.

A model call is covered by the same net. The plugin runtime imports only the
standard library — the doctor's runtime-imports check enforces that — so the
only ways it could reach a model are a subprocess or a socket, and both fail
here.
"""

from __future__ import annotations

import builtins
import http.client
import io
import os
import pathlib
import shutil
import socket
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

import pytest
import techtree_hermes
from support import RecordingContext

WRITE_MODES = frozenset("wax+")


class SideEffectError(AssertionError):
    """Raised when registration reaches for the outside world."""


def _tripwire(description: str) -> Any:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise SideEffectError(f"registration attempted to {description}: {args!r}")

    return refuse


@pytest.fixture
def sealed_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace every process, socket, and write entry point with a tripwire."""
    for module, names, description in (
        (
            subprocess,
            ("run", "call", "check_call", "check_output", "Popen"),
            "start a subprocess",
        ),
        (
            os,
            (
                "system",
                "popen",
                "execv",
                "execve",
                "execvp",
                "posix_spawn",
                "spawnv",
                "fork",
            ),
            "start a process",
        ),
        (socket, ("socket", "create_connection", "getaddrinfo"), "open a socket"),
        (urllib.request, ("urlopen",), "make a network request"),
        (http.client.HTTPConnection, ("request", "connect"), "make a network request"),
        (
            os,
            ("remove", "unlink", "mkdir", "makedirs", "rename", "replace", "rmdir"),
            "change the filesystem",
        ),
        (shutil, ("rmtree", "copy", "copytree", "move"), "change the filesystem"),
        (
            pathlib.Path,
            (
                "write_text",
                "write_bytes",
                "mkdir",
                "touch",
                "unlink",
                "rmdir",
                "rename",
                "replace",
                "chmod",
                "symlink_to",
            ),
            "change the filesystem",
        ),
    ):
        for name in names:
            monkeypatch.setattr(module, name, _tripwire(description), raising=False)

    real_open = builtins.open

    def guarded_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if WRITE_MODES & set(mode):
            raise SideEffectError(f"registration attempted to write {file!r}")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)


def test_registration_starts_no_process_and_opens_no_socket(
    sealed_host: None, ctx: RecordingContext
) -> None:
    techtree_hermes.register(ctx)


def test_registration_writes_nothing(
    tmp_path: Path, sealed_host: None, ctx: RecordingContext
) -> None:
    """Not even a state file, a cache, or a log."""
    before = sorted(path.name for path in tmp_path.iterdir())

    techtree_hermes.register(ctx)

    assert sorted(path.name for path in tmp_path.iterdir()) == before


def test_registration_dispatches_no_tool(
    sealed_host: None, ctx: RecordingContext
) -> None:
    """Dispatching would run host tooling, including the terminal tool."""
    techtree_hermes.register(ctx)

    # The recording context raises on dispatch; reaching here means it was
    # never called, and the registered handlers were only handed over.
    assert all(callable(tool.handler) for tool in ctx.tools.values())


def test_the_tripwires_would_notice(sealed_host: None) -> None:
    """The seal is real: the same calls fail when made deliberately."""
    with pytest.raises(SideEffectError):
        subprocess.run(["true"], check=False)
    with pytest.raises(SideEffectError):
        socket.create_connection(("localhost", 9))
    with pytest.raises(SideEffectError):
        Path("/tmp/techtree-plugin-should-never-exist").write_text("x")
