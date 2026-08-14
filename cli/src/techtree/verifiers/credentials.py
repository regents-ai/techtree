"""Whether the evaluation endpoint can authenticate. Spec section 6.9.

Two rules shape everything in this module.

*A secret is checked, never carried.* No function here returns a credential
value, writes one, or puts one in an error message, a detail dictionary, or a
log line. The only object that ever holds the value is the child process
environment :func:`scrubbed_child_environment` builds, and that dictionary is
handed straight to the child. :func:`redacted_environment` exists so that the
same dictionary can be described in a diagnostic without being disclosed.

*Evaluation auth is not host auth.* The credential this module diagnoses buys
model tokens for the evaluated subject. It is unrelated to whatever the
operator's own Hermes is authenticated with, and confusing the two produces the
worst possible failure: a run that looks configured, provisions Docker, and
then discovers thirty seconds later that nothing can answer. Spec sections 6.9
and 6.18 keep them separate, and so does the wording of every message here.

The pinned client resolves a ``PRIME_API_KEY``-named credential from the
environment first and from the active Prime CLI configuration second, returning
the literal string ``"EMPTY"`` when it finds neither
(``docs/verifiers-eval.md``). A missing credential therefore does not fail at
startup; it fails at the first model call, after the container is up. That is
the whole reason this check runs before a child is launched.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final, Literal

from techtree.errors import AuthenticationError
from techtree.models.base import NonEmptyString, ProtocolModel
from techtree.models.campaign import ModelSpec
from techtree.models.cli import NextAction
from techtree.models.engine import EngineInstallation

__all__ = [
    "MODEL_CREDENTIALS_MISSING",
    "PRIME_CONFIG_RELATIVE_PATH",
    "PRIME_CREDENTIAL_ENV",
    "PRIME_ENVIRONMENT",
    "CredentialStatus",
    "credential_status",
    "redacted_environment",
    "require_credentials",
    "scrubbed_child_environment",
]

#: Stable error code. Spec section 6.9.
MODEL_CREDENTIALS_MISSING: Final = "model_credentials_missing"

#: The credential name the pinned client gives its own resolution to. Any other
#: name is read from the environment and nowhere else.
PRIME_CREDENTIAL_ENV: Final = "PRIME_API_KEY"

#: Where the Prime CLI keeps its configuration, relative to ``HOME``.
PRIME_CONFIG_RELATIVE_PATH: Final = (".prime", "config.json")

#: Prime variables the pinned client reads when it resolves an endpoint. The
#: key itself is not here: it is forwarded by name from the Campaign.
PRIME_ENVIRONMENT: Final[tuple[str, ...]] = (
    "PRIME_INFERENCE_URL",
    "PRIME_TEAM_ID",
)

#: The only host variables a child inherits. ``PATH`` so ordinary system tools
#: and the container runtime resolve, ``HOME`` because the Prime CLI
#: configuration and package caches hang off it, ``TMPDIR`` so scratch files
#: land where the host expects them.
_BASE_ENVIRONMENT: Final[tuple[str, ...]] = ("PATH", "HOME", "TMPDIR")

_PRIME_CONFIG_KEY: Final = "api_key"

#: What the Prime CLI configuration under one ``HOME`` supplies.
type _PrimeConfigState = Literal["usable", "signed_out", "malformed", "absent"]


class CredentialStatus(ProtocolModel):
    """Whether one model endpoint can authenticate, and from where.

    ``detail`` is operator-facing prose. It names the variable and the place it
    was looked for, never a value or a fragment of one.

    ``malformed_prime_config`` is its own answer rather than another way of
    saying "missing": a configuration file that cannot be read is a broken
    store, and telling somebody who has signed in that they have not is the
    kind of advice that sends them round the loop again.
    """

    provider: NonEmptyString
    credential_env: NonEmptyString
    available: bool
    source: Literal["environment", "prime_config", "missing", "malformed_prime_config"]
    detail: NonEmptyString


def credential_status(
    model: ModelSpec, *, environ: Mapping[str, str] | None = None
) -> CredentialStatus:
    """Report whether the declared credential can be resolved.

    Presence only. The value is never read into a return, a log, or an error.

    ``environ`` is the environment the question is asked *about*, which is not
    always the one this process happens to have. A readiness check runs in an
    operator's terminal but has to answer for the environment a detached run
    would get, and a check that answered for its own terminal instead would be
    able to say "ready" about a run that cannot authenticate.
    """
    source = os.environ if environ is None else environ
    name = model.credential_env
    if source.get(name):
        return CredentialStatus(
            provider=model.provider,
            credential_env=name,
            available=True,
            source="environment",
            detail=f"{name} is set in this environment.",
        )

    state = (
        _prime_config_state(source.get("HOME"))
        if name == PRIME_CREDENTIAL_ENV
        else "absent"
    )

    if state == "usable":
        return CredentialStatus(
            provider=model.provider,
            credential_env=name,
            available=True,
            source="prime_config",
            detail=(
                "the active Prime CLI configuration holds a key the pinned "
                "evaluation client can use."
            ),
        )

    if state == "malformed":
        return CredentialStatus(
            provider=model.provider,
            credential_env=name,
            available=False,
            source="malformed_prime_config",
            detail=(
                "the Prime CLI configuration on this machine could not be read "
                "as a configuration, so no key can be resolved from it. Signing "
                "in again writes a fresh one."
            ),
        )

    if state == "signed_out":
        return CredentialStatus(
            provider=model.provider,
            credential_env=name,
            available=False,
            source="missing",
            detail=(
                "the Prime CLI configuration on this machine holds no key: this "
                "machine is signed out, or the sign-in has been cleared. This "
                "credential pays for the evaluated subject's model calls; it is "
                "separate from whatever your own agent is signed in with."
            ),
        )

    return CredentialStatus(
        provider=model.provider,
        credential_env=name,
        available=False,
        source="missing",
        detail=(
            f"no active Prime CLI configuration supplies {name}. This credential "
            "pays for the evaluated subject's model calls; it is separate from "
            "whatever your own agent is signed in with."
        ),
    )


def require_credentials(model: ModelSpec) -> CredentialStatus:
    """Return the status, or refuse to go further without a credential."""
    status = credential_status(model)
    if status.available:
        return status
    raise AuthenticationError(
        f"the evaluation model endpoint has no credential: {status.detail}",
        code=MODEL_CREDENTIALS_MISSING,
        details={
            "provider": model.provider,
            "model_id": model.model_id,
            "credential_env": model.credential_env,
        },
        next_actions=[
            NextAction(
                id="sign_in_to_prime",
                label="Sign in to Prime, then start the run again",
                reason=(
                    "A PRIME_API_KEY-named credential resolves from the active "
                    "Prime CLI configuration, which a run can read for itself."
                ),
                cli=["prime", "login"],
                hermes_tool=None,
                hermes_args=None,
                requires_user_confirmation=True,
            ),
            NextAction(
                id="export_evaluation_credential",
                label=(f"Check how {model.credential_env} reaches a run"),
                reason=(
                    "Setting this credential in your own terminal is not "
                    "enough: a run works in a separate background process that "
                    "is not given your terminal's variables. It pays for the "
                    "evaluated subject's model calls and is never stored."
                ),
                cli=["techtree", "doctor", "--for-evaluation"],
                hermes_tool=None,
                hermes_args=None,
                requires_user_confirmation=False,
            ),
        ],
    )


def _prime_config_state(home: str | None) -> _PrimeConfigState:
    """Report what the Prime CLI configuration under ``home`` supplies.

    The file is opened, one key is tested for emptiness, and the value is
    discarded. Nothing read here reaches a caller.

    Three not-usable answers are distinguished because they need three
    different sentences. No file is somebody who has not signed in; a file with
    no key is somebody whose sign-in has gone away; a file that will not parse
    is a broken store, and no amount of signing in explains itself if it is
    described as either of the other two.
    """
    if not home:
        return "absent"
    path = Path(home).joinpath(*PRIME_CONFIG_RELATIVE_PATH)
    try:
        raw = path.read_bytes()
    except OSError:
        return "absent"
    try:
        document = json.loads(raw)
    except ValueError:
        return "malformed"
    if not isinstance(document, dict):
        return "malformed"
    value = document.get(_PRIME_CONFIG_KEY)
    if value is None or (isinstance(value, str) and not value.strip()):
        return "signed_out"
    return "usable" if isinstance(value, str) else "malformed"


def scrubbed_child_environment(
    *,
    model: ModelSpec,
    engine: EngineInstallation,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build a Verifiers child's environment from a narrow allow-list.

    The host environment is not copied. A developer machine carries cloud
    credentials, provider keys for other services, and shell configuration that
    would change how the subject behaves, and none of it belongs inside an
    experiment that claims only one thing differed.

    The engine's own ``bin`` directory is prepended to ``PATH`` so the child
    resolves the tools the pinned engine ships before anything the operator
    happens to have installed, for the same reason the engine invokes its own
    console scripts by absolute path.
    """
    environment = {
        name: os.environ[name] for name in _BASE_ENVIRONMENT if name in os.environ
    }
    environment["PATH"] = _engine_first_path(engine, environment.get("PATH"))

    credential = os.environ.get(model.credential_env)
    if credential:
        environment[model.credential_env] = credential

    for name in PRIME_ENVIRONMENT:
        value = os.environ.get(name)
        if value:
            environment[name] = value

    for name, value in (extra or {}).items():
        environment[name] = value

    return environment


def _engine_first_path(engine: EngineInstallation, inherited: str | None) -> str:
    """Return a ``PATH`` that starts with the engine's own executables."""
    engine_bin = str(Path(engine.python_executable).parent)
    if not inherited:
        return engine_bin
    entries = [engine_bin, *(part for part in inherited.split(os.pathsep) if part)]
    return os.pathsep.join(dict.fromkeys(entries))


def redacted_environment(
    environment: Mapping[str, str], *, secret_names: Iterable[str]
) -> dict[str, str]:
    """Describe a child environment safely enough to put in a diagnostic.

    Named secrets are replaced by their length. That distinguishes an unset
    variable from an empty one from a truncated paste, which is the whole of
    what an operator needs, and discloses nothing usable. Everything else — the
    ``PATH`` the child searched, the ``HOME`` it read configuration from — is
    shown, because hiding it would make the diagnostic useless without making
    anything safer.
    """
    secrets = set(secret_names)
    return {
        name: (f"<set, {len(value)} characters>" if name in secrets else value)
        for name, value in environment.items()
    }
