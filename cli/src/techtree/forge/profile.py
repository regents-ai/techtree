"""The one Hermes profile forge experiments run in.

Hermes keeps every profile's sign-ins to itself: a named profile never reads
another profile's authentication store, and a copied OAuth token logs its
other holder out. So Techtree does not make a profile per attempt. The person
creates one profile named ``techtree`` and signs it in once::

    hermes profile create techtree --no-alias
    hermes -p techtree auth add PROVIDER

``--no-alias`` because Hermes would otherwise offer a ``techtree`` shortcut
command, and that name is already Techtree's own.

Techtree owns everything else in it. Before and after every attempt the
profile is emptied of all but the sign-in, so each attempt starts from the
same fresh state and leaves nothing for the next. A run holds the profile's
lock from its first attempt to its last, so two runs never share it.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from filelock import FileLock, Timeout

from techtree.errors import ConflictError, PrerequisiteError
from techtree.forge.process import CommandRunner
from techtree.fs import remove_tree

__all__ = [
    "CREATE_PROFILE_COMMAND",
    "PROFILE_NAME",
    "hermes_root",
    "hold_profile",
    "is_signed_in",
    "profile_dir",
    "require_signed_in",
    "reset_profile",
    "sign_in_command",
    "signed_in_providers",
]

PROFILE_NAME: Final = "techtree"
#: How a person makes the profile, once.
CREATE_PROFILE_COMMAND: Final = f"hermes profile create {PROFILE_NAME} --no-alias"
_LOCK_FILENAME: Final = "techtree-run.lock"
#: What a sign-in is made of: Hermes' authentication store and its lock, and
#: the file a provider's static key lives in. Nothing here is ever read.
_KEPT: Final = frozenset({"auth.json", "auth.lock", ".env", _LOCK_FILENAME})
_STATUS_TIMEOUT_SECONDS: Final = 60.0
#: How ``hermes auth list`` heads each provider that holds a credential:
#: ``openai-codex (1 credentials):``. Only the heading is read; the lines
#: under it describe the credentials and are never looked at.
_PROVIDER_HEADING: Final = re.compile(r"^(\S+) \(\d+ credentials?\):$", re.MULTILINE)


def hermes_root() -> Path:
    """Return the person's Hermes root, the way Hermes itself resolves it.

    ``HERMES_HOME`` names the root, or a profile under ``<root>/profiles``;
    otherwise the root is ``~/.hermes``.
    """
    configured = os.environ.get("HERMES_HOME", "")
    if not configured:
        return Path.home() / ".hermes"
    home = Path(configured).expanduser()
    return home.parent.parent if home.parent.name == "profiles" else home


def profile_dir(profiles_root: Path | None = None) -> Path:
    """Return where the ``techtree`` profile lives, or is expected to."""
    root = profiles_root if profiles_root is not None else hermes_root() / "profiles"
    return root / PROFILE_NAME


def sign_in_command(provider: str) -> str:
    """How a person signs the profile in to ``provider``."""
    return f"hermes -p {PROFILE_NAME} auth add {provider}"


def require_signed_in(
    run: CommandRunner, executable: Path, provider: str, profile: Path
) -> None:
    """Refuse unless the profile exists and Hermes says it is signed in.

    Hermes is asked, read-only, whether the profile holds a sign-in for the
    provider; its authentication store is never opened here.
    """
    sign_in = sign_in_command(provider)
    if not profile.is_dir():
        raise PrerequisiteError(
            f"experiments run in a Hermes profile named {PROFILE_NAME}, and "
            f"there is none yet. Create it with `{CREATE_PROFILE_COMMAND}`, "
            f"then sign it in with `{sign_in}`",
            code="forge_profile_missing",
            details={"profile": str(profile)},
        )
    if not is_signed_in(run, executable, provider):
        raise PrerequisiteError(
            f"the Hermes profile {PROFILE_NAME} is not signed in to {provider}. "
            f"Sign it in with `{sign_in}`",
            code="forge_profile_signed_out",
            details={"profile": str(profile), "provider": provider},
        )


def is_signed_in(run: CommandRunner, executable: Path, provider: str) -> bool:
    """Ask Hermes whether the ``techtree`` profile is signed in to ``provider``."""
    completed = run(
        [str(executable), "-p", PROFILE_NAME, "auth", "status", provider],
        _STATUS_TIMEOUT_SECONDS,
    )
    return f"{provider}: logged in" in completed.stdout.splitlines()


def signed_in_providers(run: CommandRunner, executable: Path) -> list[str]:
    """The providers Hermes says the ``techtree`` profile is signed in to.

    Hermes lists the providers the profile holds a credential for, and is then
    asked about each one the way ``forge run`` asks before it starts, so a
    provider whose credential has lapsed is not counted. Read-only throughout.
    """
    listed = run(
        [str(executable), "-p", PROFILE_NAME, "auth", "list"],
        _STATUS_TIMEOUT_SECONDS,
    )
    providers = _PROVIDER_HEADING.findall(listed.stdout)
    return [name for name in providers if is_signed_in(run, executable, name)]


@contextmanager
def hold_profile(profile: Path) -> Iterator[None]:
    """Hold the profile for one run; a second run is refused, not queued."""
    lock = FileLock(profile / _LOCK_FILENAME, timeout=0, mode=0o600)
    try:
        lock.acquire()
    except Timeout as error:
        raise ConflictError(
            f"another experiment is running in the Hermes profile "
            f"{PROFILE_NAME}; start this one when it has finished",
            code="forge_profile_busy",
            details={"profile": str(profile)},
        ) from error
    try:
        yield
    finally:
        lock.release()


def reset_profile(profile: Path) -> None:
    """Empty the profile of everything but the sign-in."""
    for entry in profile.iterdir():
        if entry.name not in _KEPT:
            remove_tree(entry)
