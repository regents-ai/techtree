"""Cover the version surface shared by the CLI, the worker, and Doctor."""

from __future__ import annotations

from typer.testing import CliRunner

from techtree import __version__, version
from techtree.cli.app import create_app
from techtree.constants import CLI_SCHEMA_VERSION
from techtree.version import (
    PROTOCOL_VERSION,
    package_version,
    version_info,
)


def test_package_version_is_reported() -> None:
    assert package_version()
    assert __version__ == package_version()


def test_version_info_reports_package_and_protocol_versions() -> None:
    """The envelope version is written out, not compared against itself.

    Doctor reports this dictionary from inside an envelope that announces its
    own ``schema_version``. Asserting the constant against the constant would
    hold whichever value it held, which is how the two came to disagree.
    """
    assert version_info() == {
        "package_version": package_version(),
        "protocol_version": PROTOCOL_VERSION,
        "cli_schema_version": "techtree.cli.v2",
    }


def test_the_reported_envelope_version_is_the_one_the_cli_emits() -> None:
    """One value, one definition. There is no second place to change it."""
    assert version_info()["cli_schema_version"] == CLI_SCHEMA_VERSION
    assert not hasattr(version, "CLI_SCHEMA_VERSION")


def test_cli_version_option_prints_the_package_version() -> None:
    result = CliRunner().invoke(create_app(), ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == package_version()
