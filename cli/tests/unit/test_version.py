"""Cover the version surface shared by the CLI, the worker, and Doctor."""

from __future__ import annotations

from typer.testing import CliRunner

from techtree import __version__
from techtree.cli.app import create_app
from techtree.version import (
    CLI_SCHEMA_VERSION,
    PROTOCOL_VERSION,
    package_version,
    version_info,
)


def test_package_version_is_reported() -> None:
    assert package_version()
    assert __version__ == package_version()


def test_version_info_reports_package_and_protocol_versions() -> None:
    assert version_info() == {
        "package_version": package_version(),
        "protocol_version": PROTOCOL_VERSION,
        "cli_schema_version": CLI_SCHEMA_VERSION,
    }


def test_cli_version_option_prints_the_package_version() -> None:
    result = CliRunner().invoke(create_app(), ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == package_version()
