"""Local settings and their environment overrides. Spec section 10.11.

Settings are small, so the interesting tests are about the edges: a missing
file yields defaults rather than an error, a malformed file is a typed error
rather than a traceback, and an unrecognized ``TECHTREE_*`` variable is ignored
rather than guessed at.

One test exists purely to hold a rule in place: no provider secret belongs in
this model. A credential is named by the Campaign and read from the environment
at execution time; it is never copied into a file Techtree writes.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from techtree.canonical import sha256_digest_bytes
from techtree.errors import ValidationError
from techtree.paths import TechtreePaths, paths_from_root
from techtree.settings import (
    ENVIRONMENT_OVERRIDES,
    Settings,
    load_settings,
    resolved_settings,
    save_settings,
    settings_from_environment,
)

DIGEST = sha256_digest_bytes(b"engine")


@pytest.fixture
def paths(tmp_path: Path) -> TechtreePaths:
    """Return an isolated path layout for one test."""
    return paths_from_root(tmp_path / "techtree")


@pytest.fixture(autouse=True)
def _clear_techtree_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep a developer's own environment out of these assertions."""
    for variable in ENVIRONMENT_OVERRIDES:
        monkeypatch.delenv(variable, raising=False)


def test_a_missing_file_yields_defaults(paths: TechtreePaths) -> None:
    settings = load_settings(paths)

    assert settings == Settings()
    assert settings.output_mode == "human"
    assert settings.log_level == "INFO"
    assert settings.active_engine_digest is None


def test_settings_round_trip_through_the_file(paths: TechtreePaths) -> None:
    save_settings(paths, Settings(output_mode="json", active_engine_digest=DIGEST))

    reloaded = load_settings(paths)

    assert reloaded.output_mode == "json"
    assert reloaded.active_engine_digest == DIGEST


def test_saving_omits_unset_values(paths: TechtreePaths) -> None:
    save_settings(paths, Settings())

    document = tomllib.loads(paths.config_file.read_text(encoding="utf-8"))

    # The one optional field left. A settings file states what was chosen, so
    # a value nobody chose is absent rather than written as null.
    assert "active_engine_digest" not in document


def test_the_settings_file_is_owner_only(paths: TechtreePaths) -> None:
    save_settings(paths, Settings())

    assert paths.config_file.stat().st_mode & 0o777 == 0o600


def test_a_malformed_file_is_a_typed_error(paths: TechtreePaths) -> None:
    paths.config_file.parent.mkdir(parents=True, exist_ok=True)
    paths.config_file.write_text("this is not toml = = =", encoding="utf-8")

    with pytest.raises(ValidationError, match="not valid TOML"):
        load_settings(paths)


def test_an_invalid_value_in_the_file_is_a_typed_error(paths: TechtreePaths) -> None:
    paths.config_file.parent.mkdir(parents=True, exist_ok=True)
    paths.config_file.write_text('output_mode = "yaml"\n', encoding="utf-8")

    with pytest.raises(ValidationError) as caught:
        load_settings(paths)

    assert caught.value.details["source"] == str(paths.config_file)


def test_an_unknown_key_in_the_file_is_rejected(paths: TechtreePaths) -> None:
    paths.config_file.parent.mkdir(parents=True, exist_ok=True)
    paths.config_file.write_text('api_token = "secret"\n', encoding="utf-8")

    with pytest.raises(ValidationError):
        load_settings(paths)


# ---------------------------------------------------------------------------
# Environment overrides
# ---------------------------------------------------------------------------


def test_no_environment_variables_leaves_settings_untouched() -> None:
    base = Settings(output_mode="json")

    assert settings_from_environment(base) is base


def test_each_supported_variable_overrides_its_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TECHTREE_ACTIVE_ENGINE_DIGEST", DIGEST)
    monkeypatch.setenv("TECHTREE_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("TECHTREE_OUTPUT_MODE", "json")

    settings = settings_from_environment(Settings())

    assert settings.active_engine_digest == DIGEST
    assert settings.log_level == "DEBUG"
    assert settings.output_mode == "json"


def test_an_unrecognized_techtree_variable_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TECHTREE_SOMETHING_ELSE", "value")

    assert settings_from_environment(Settings()) == Settings()


def test_an_invalid_environment_value_is_a_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TECHTREE_OUTPUT_MODE", "yaml")

    with pytest.raises(ValidationError) as caught:
        settings_from_environment(Settings())

    assert caught.value.details["source"] == "environment"


def test_the_environment_wins_over_the_file(
    paths: TechtreePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_settings(paths, Settings(output_mode="human"))
    monkeypatch.setenv("TECHTREE_OUTPUT_MODE", "json")

    assert resolved_settings(paths).output_mode == "json"


def test_resolved_settings_fall_back_to_the_file(paths: TechtreePaths) -> None:
    save_settings(paths, Settings(log_level="WARNING"))

    assert resolved_settings(paths).log_level == "WARNING"


def test_settings_hold_no_credential_field() -> None:
    """A provider secret is named in the Campaign and read from the environment."""
    fields = set(Settings.model_fields)

    assert fields.isdisjoint({"api_key", "token", "password", "credential", "secret"})
