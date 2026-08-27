"""Local Techtree settings. Spec section 10.11.

Settings are user preferences plus one pointer: which managed engine is active.
They live in ``config.toml`` under the Techtree root and are read with the
standard library, written atomically, and then overlaid with any supported
``TECHTREE_*`` environment variable.

No provider secret belongs in this model. A subject's credential is named by
an environment variable in the Campaign, and the value is read from the
environment at execution time; it is never copied into settings, into a run
directory, or into any protocol document.
"""

from __future__ import annotations

import os
import tomllib
from typing import Final, Literal

import tomli_w
from pydantic import ValidationError as PydanticValidationError

from techtree.errors import ValidationError
from techtree.fs import atomic_write_text
from techtree.models.base import Digest, StateModel
from techtree.models.cli import NextAction
from techtree.paths import TechtreePaths

__all__ = [
    "ENVIRONMENT_OVERRIDES",
    "Settings",
    "load_settings",
    "resolved_settings",
    "save_settings",
    "settings_from_environment",
]

OutputMode = Literal["human", "json"]


class Settings(StateModel):
    """Local preferences and the active engine pointer."""

    active_engine_digest: Digest | None = None
    log_level: str = "INFO"
    output_mode: OutputMode = "human"
    #: Where ``techtree proof publish`` sends a proof bundle. Decisions 0038.
    #: It is a setting rather than a value in the command because the address
    #: of the public log is an operational fact about a deployment, and a build
    #: that has not been told one refuses to publish rather than inventing
    #: somewhere to send a run's evidence.
    publication_endpoint: str | None = None


#: Environment variable to settings field. Only these four are supported; an
#: unrecognized ``TECHTREE_*`` variable is ignored rather than guessed at.
ENVIRONMENT_OVERRIDES: Final[dict[str, str]] = {
    "TECHTREE_ACTIVE_ENGINE_DIGEST": "active_engine_digest",
    "TECHTREE_LOG_LEVEL": "log_level",
    "TECHTREE_OUTPUT_MODE": "output_mode",
    "TECHTREE_PUBLICATION_ENDPOINT": "publication_endpoint",
}


def load_settings(paths: TechtreePaths) -> Settings:
    """Load TOML or return defaults."""
    try:
        raw = paths.config_file.read_bytes()
    except FileNotFoundError:
        return Settings()

    try:
        document = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ValidationError(
            f"settings file is not valid TOML: {paths.config_file}",
            details={"path": str(paths.config_file)},
            next_actions=[_repair_settings_action(str(paths.config_file))],
        ) from error

    return _validate(document, source=str(paths.config_file))


def save_settings(paths: TechtreePaths, settings: Settings) -> None:
    """Atomically write TOML."""
    document = {
        name: value
        for name, value in settings.model_dump().items()
        if value is not None
    }
    atomic_write_text(paths.config_file, tomli_w.dumps(document))


def settings_from_environment(base: Settings) -> Settings:
    """Apply supported ``TECHTREE_*`` environment overrides."""
    document = base.model_dump()
    applied = False
    for variable, field in ENVIRONMENT_OVERRIDES.items():
        value = os.environ.get(variable)
        if value is None:
            continue
        document[field] = value
        applied = True

    if not applied:
        return base
    return _validate(document, source="environment")


def resolved_settings(paths: TechtreePaths) -> Settings:
    """Load file settings and apply environment values."""
    return settings_from_environment(load_settings(paths))


def _validate(document: object, *, source: str) -> Settings:
    try:
        return Settings.model_validate(document)
    except PydanticValidationError as error:
        raise ValidationError(
            f"invalid Techtree settings from {source}: {error.errors()[0]['msg']}",
            details={"source": source},
            next_actions=[_repair_settings_action(source)],
        ) from error


def _repair_settings_action(source: str) -> NextAction:
    """Point at the file to fix; deleting it restores working defaults."""
    return NextAction(
        id="repair_settings",
        label="Fix or remove the settings file",
        reason=(
            f"the settings file at {source} cannot be read; deleting it "
            "restores the defaults and techtree recreates it on demand"
        ),
        cli=["rm", source],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=True,
    )
