"""The one way into Techtree. Specification section 7.5.

Everything scientific the plugin can cause happens through the Techtree CLI,
and every call goes through this module. The rules that make that safe are all
here rather than spread across the tool handlers:

* the command is always an argv array run with ``shell=False``, so nothing is
  ever quoted, expanded, or interpolated into a shell;
* the executable is the one name in ``constants.CLI_COMMAND``, resolved on
  PATH, and no argument, release field, or model output can name another;
* machine flags are appended by the bridge, exactly once, so a caller cannot
  ask for coloured or interactive output;
* output is bounded, and one valid JSON envelope is the only acceptable answer;
* the envelope is returned to the caller unchanged, because Techtree's own
  words about a Techtree result are the honest ones;
* stderr is scrubbed and truncated before it is repeated anywhere.

The host environment is inherited so the CLI and its worker can reach the
Prime authentication and ``TECHTREE_HOME`` the user already set up. The bridge
never reads, enumerates, copies, or logs those values: a credential that is
never touched cannot be leaked into an argument, a log line, or a model-visible
tool result.

One command is deliberately not bridged. ``techtree --version`` prints a bare
version string even in machine mode, so it is not an envelope and must never
be parsed as one. Release facts come from ``techtree release info``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from shutil import which
from typing import Any, Final, Protocol

from .constants import (
    CLI_COMMAND,
    CLI_JSON_FLAGS,
    DEFAULT_CLI_TIMEOUT_SECONDS,
    MAX_CLI_STDERR_BYTES,
    MAX_CLI_STDOUT_BYTES,
)
from .errors import (
    CODE_CLI_OUTPUT_TOO_LARGE,
    CODE_TECHTREE_CLI_NOT_FOUND,
    CliEnvelopeError,
    CliInvocationError,
    CliNotInstalledError,
    scrub_text,
)
from .models import CliInvocation, CliResponse, ReleaseCore, parse_cli_envelope
from .release import compare_cli_release, release_core_digest

#: The frozen read-only command that answers "which release is installed?".
RELEASE_INFO_ARGUMENTS: Final = ("release", "info")

#: How much scrubbed stderr is worth repeating as a diagnostic.
STDERR_EXCERPT_CHARS: Final = 2000

PathLookup = Callable[[str], str | None]


def resolve_techtree_binary(*, path_lookup: PathLookup = which) -> str | None:
    """Return the installed Techtree executable path, or None."""
    return path_lookup(CLI_COMMAND)


def require_techtree_binary(*, path_lookup: PathLookup = which) -> str:
    """Return the installed Techtree executable path, or fail with a repair.

    Raises:
        CliNotInstalledError: when Techtree is not installed on this host.
    """
    located = resolve_techtree_binary(path_lookup=path_lookup)
    if located is None:
        raise CliNotInstalledError(
            "the Techtree CLI is not installed on this host",
            code=CODE_TECHTREE_CLI_NOT_FOUND,
        )
    return located


def build_cli_argv(
    arguments: Sequence[str], *, path_lookup: PathLookup = which
) -> list[str]:
    """Return the complete argv for one machine-mode Techtree call.

    Raises:
        CliNotInstalledError: when Techtree is not installed on this host.
        CliInvocationError: when an argument is not a usable literal, or when
            a caller tried to supply the machine flags itself.
    """
    argv = [require_techtree_binary(path_lookup=path_lookup)]

    for argument in arguments:
        if not isinstance(argument, str):
            raise CliInvocationError("a Techtree argument was not a string")
        if not argument:
            raise CliInvocationError("a Techtree argument was empty")
        if "\x00" in argument:
            raise CliInvocationError("a Techtree argument contained a NUL byte")
        if argument in CLI_JSON_FLAGS:
            raise CliInvocationError(
                f"the machine flag {argument!r} is added by the bridge, not by a caller"
            )
        argv.append(argument)

    argv.extend(CLI_JSON_FLAGS)
    return argv


def invoke_cli(
    arguments: Sequence[str],
    *,
    timeout_seconds: float = DEFAULT_CLI_TIMEOUT_SECONDS,
    maximum_stdout_bytes: int = MAX_CLI_STDOUT_BYTES,
    maximum_stderr_bytes: int = MAX_CLI_STDERR_BYTES,
    path_lookup: PathLookup = which,
) -> dict[str, Any]:
    """Run one Techtree command and return its envelope unchanged.

    A command that fails still answers with an envelope: Techtree reports its
    own failures in-band, with a code, a message, and often a next step. Those
    are returned as they are. Only an answer that is not one valid envelope is
    a bridge-level failure.

    Raises:
        CliNotInstalledError: when Techtree is not installed.
        CliInvocationError: on timeout or a CLI that could not be run.
        CliEnvelopeError: when the answer was not exactly one valid envelope.
    """
    response = call_cli(
        arguments,
        timeout_seconds=timeout_seconds,
        maximum_stdout_bytes=maximum_stdout_bytes,
        maximum_stderr_bytes=maximum_stderr_bytes,
        path_lookup=path_lookup,
    )
    return dict(response.envelope)


def call_cli(
    arguments: Sequence[str],
    *,
    purpose: str = "",
    timeout_seconds: float = DEFAULT_CLI_TIMEOUT_SECONDS,
    maximum_stdout_bytes: int = MAX_CLI_STDOUT_BYTES,
    maximum_stderr_bytes: int = MAX_CLI_STDERR_BYTES,
    path_lookup: PathLookup = which,
) -> CliResponse:
    """Run one Techtree command and return the envelope with its exit code.

    The CLI's exit codes are part of its contract, so a caller that branches
    on them — a run that was cancelled, a prerequisite that is missing — needs
    them alongside the envelope.
    """
    argv = build_cli_argv(arguments, path_lookup=path_lookup)
    invocation = CliInvocation(
        argv=tuple(argv),
        timeout_seconds=timeout_seconds,
        purpose=purpose or " ".join(arguments),
    )

    try:
        # An argv array with shell=False: nothing here reaches a shell.
        completed = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise CliInvocationError(
            f"the Techtree command {invocation.purpose!r} did not finish within "
            f"{timeout_seconds:.0f} seconds",
            retryable=True,
        ) from error
    except OSError as error:
        raise CliInvocationError(
            f"the Techtree CLI could not be run: {scrub_text(str(error))}"
        ) from error

    stderr_excerpt = _safe_stderr(completed.stderr, maximum_stderr_bytes)
    stdout = _bounded_stdout(completed.stdout, maximum_stdout_bytes)
    envelope = parse_cli_envelope(stdout)

    return CliResponse(
        invocation=invocation,
        exit_code=completed.returncode,
        envelope=envelope,
        stderr_excerpt=stderr_excerpt,
    )


def read_cli_version(
    *,
    timeout_seconds: float = DEFAULT_CLI_TIMEOUT_SECONDS,
    path_lookup: PathLookup = which,
) -> str:
    """Return the installed CLI's version string.

    ``techtree --version`` answers with a bare version even in machine mode,
    so this is the one call that must not be parsed as an envelope. It exists
    to prove an installed CLI runs at all; every release fact comes from
    ``release info``.

    Raises:
        CliNotInstalledError: when Techtree is not installed.
        CliInvocationError: when it could not be run, or did not answer with
            one plain version line.
    """
    argv = [require_techtree_binary(path_lookup=path_lookup), "--version"]
    try:
        completed = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as error:
        raise CliInvocationError(
            f"the Techtree CLI could not report its version: {scrub_text(str(error))}"
        ) from error

    version = completed.stdout.decode("utf-8", errors="replace").strip()
    if completed.returncode != 0 or not version or "\n" in version:
        raise CliInvocationError(
            "the Techtree CLI did not answer with one plain version line"
        )
    return version


def invoke_cli_human(
    arguments: Sequence[str], *, path_lookup: PathLookup = which
) -> int:
    """Run a Techtree command with its human output, in a terminal.

    Techtree's own human output — a live run view, a rendered report — belongs
    on the terminal the user is looking at, not inside a JSON tool result. So
    this inherits the caller's streams and returns the exit code, and callers
    must never route it to a gateway.
    """
    argv = [require_techtree_binary(path_lookup=path_lookup)]
    for argument in arguments:
        if not isinstance(argument, str) or not argument or "\x00" in argument:
            raise CliInvocationError("a Techtree argument was not a usable literal")
        argv.append(argument)

    try:
        completed = subprocess.run(argv, shell=False, check=False)
    except OSError as error:
        raise CliInvocationError(
            f"the Techtree CLI could not be run: {scrub_text(str(error))}"
        ) from error
    return completed.returncode


def verify_cli_release(
    expected: ReleaseCore,
    *,
    timeout_seconds: float = DEFAULT_CLI_TIMEOUT_SECONDS,
    path_lookup: PathLookup = which,
) -> dict[str, Any]:
    """Check that the installed CLI belongs to the same release as this build.

    Runs the frozen read-only ``techtree release info`` command and compares
    every coordinate the two documents share. Returns what was found rather
    than raising, so a caller can show the operator both sides of a
    disagreement.
    """
    envelope = invoke_cli(
        RELEASE_INFO_ARGUMENTS,
        timeout_seconds=timeout_seconds,
        path_lookup=path_lookup,
    )
    installed = envelope_data(envelope)
    mismatches = compare_cli_release(expected, installed)

    return {
        "compatible": not mismatches,
        "mismatches": mismatches,
        "expected_release_core_digest": release_core_digest(expected),
        "installed": dict(installed),
    }


def _bounded_stdout(raw: bytes, maximum_bytes: int) -> str:
    if len(raw) > maximum_bytes:
        raise CliEnvelopeError(
            f"the Techtree CLI answered with {len(raw)} bytes, more than the "
            f"{maximum_bytes} this plugin will read",
            code=CODE_CLI_OUTPUT_TOO_LARGE,
        )
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CliEnvelopeError("CLI machine output was not valid UTF-8") from error


def _safe_stderr(raw: bytes, maximum_bytes: int) -> str:
    """Return a bounded, scrubbed excerpt of stderr, safe to repeat."""
    text = raw[:maximum_bytes].decode("utf-8", errors="replace")
    scrubbed = scrub_text(text).strip()
    if len(scrubbed) <= STDERR_EXCERPT_CHARS:
        return scrubbed
    return scrubbed[:STDERR_EXCERPT_CHARS] + "… (truncated)"


class Bridge(Protocol):
    """What the rest of the plugin needs from the CLI boundary.

    The container depends on this rather than on one class, so a caller — or a
    test — can supply anything that speaks the same four sentences.
    """

    def invoke(self, arguments: Sequence[str]) -> dict[str, Any]:
        """Run one machine-mode command and return its envelope."""

    def call(self, arguments: Sequence[str], *, purpose: str = "") -> CliResponse:
        """Run one machine-mode command and return envelope and exit code."""

    def invoke_human(self, arguments: Sequence[str]) -> int:
        """Run one terminal-only command against the user's own streams."""

    def version(self) -> str:
        """Return the installed CLI's plain version string."""

    def verify_release(self, expected: ReleaseCore) -> dict[str, Any]:
        """Compare the installed CLI's release against this plugin build."""


@dataclass(frozen=True)
class CliBridge:
    """The bridge as the service container holds it. Specification section 7.10.

    Constructing one does nothing: no executable is resolved, no process is
    started, nothing is read. It carries the timeouts and bounds a call will
    use, so registration stays inert and every call resolves the CLI freshly —
    which matters on a host where Techtree is installed mid-conversation.
    """

    timeout_seconds: float = DEFAULT_CLI_TIMEOUT_SECONDS
    maximum_stdout_bytes: int = MAX_CLI_STDOUT_BYTES
    maximum_stderr_bytes: int = MAX_CLI_STDERR_BYTES

    def is_installed(self) -> bool:
        """Whether the Techtree CLI can be found on PATH right now."""
        return resolve_techtree_binary() is not None

    def executable(self) -> str | None:
        """Where the Techtree CLI is, if it is installed."""
        return resolve_techtree_binary()

    def invoke(self, arguments: Sequence[str]) -> dict[str, Any]:
        """Run one machine-mode command and return its envelope."""
        return invoke_cli(
            arguments,
            timeout_seconds=self.timeout_seconds,
            maximum_stdout_bytes=self.maximum_stdout_bytes,
            maximum_stderr_bytes=self.maximum_stderr_bytes,
        )

    def call(self, arguments: Sequence[str], *, purpose: str = "") -> CliResponse:
        """Run one machine-mode command and return envelope and exit code."""
        return call_cli(
            arguments,
            purpose=purpose,
            timeout_seconds=self.timeout_seconds,
            maximum_stdout_bytes=self.maximum_stdout_bytes,
            maximum_stderr_bytes=self.maximum_stderr_bytes,
        )

    def version(self) -> str:
        """Return the installed CLI's plain version string."""
        return read_cli_version(timeout_seconds=self.timeout_seconds)

    def invoke_human(self, arguments: Sequence[str]) -> int:
        """Run one terminal-only command against the user's own streams."""
        return invoke_cli_human(arguments)

    def verify_release(self, expected: ReleaseCore) -> dict[str, Any]:
        """Compare the installed CLI's release against this plugin build."""
        return verify_cli_release(expected, timeout_seconds=self.timeout_seconds)


def envelope_data(envelope: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return an envelope's data object, or an empty mapping."""
    data = envelope.get("data")
    return data if isinstance(data, dict) else {}
