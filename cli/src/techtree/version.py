"""Package, protocol, and CLI-schema versions.

Spec section 10.3. This module has no side effects beyond reading installed
distribution metadata, so it is safe to import from anywhere in the package.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version

DISTRIBUTION_NAME = "techtree"

#: Version reported when the package is executed straight from a source tree
#: that has no installed distribution metadata.
SOURCE_VERSION = "0.0.0+source"

PROTOCOL_VERSION = "v1alpha1"
CLI_SCHEMA_VERSION = "techtree.cli.v1"


def package_version() -> str:
    """Return installed package version through importlib.metadata."""
    try:
        return distribution_version(DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return SOURCE_VERSION


def version_info() -> dict[str, str]:
    """Return package and protocol versions for CLI and Doctor output."""
    return {
        "package_version": package_version(),
        "protocol_version": PROTOCOL_VERSION,
        "cli_schema_version": CLI_SCHEMA_VERSION,
    }


__version__ = package_version()
