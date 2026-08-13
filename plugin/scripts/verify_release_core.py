"""Verify the embedded release. Specification sections 7.4, 9.4.

    python scripts/verify_release_core.py [--expected sha256:...]

Prints the release digest. With ``--expected`` it also requires that digest,
which is how a release checks that the plugin, the CLI wheel, and the website
all point at the same ReleaseCore.
"""

from __future__ import annotations

import argparse
from importlib import import_module
from typing import Any, cast

from _plugin_package import PACKAGE_NAME, load_plugin_package


def main() -> int:
    """Verify the release bytes shipped in this checkout."""
    parser = argparse.ArgumentParser(prog="verify-release-core")
    parser.add_argument(
        "--expected",
        help="the sha256: digest this release is required to have",
    )
    parser.add_argument(
        "--against-installed-cli",
        action="store_true",
        help="also ask the installed Techtree CLI which release it belongs to",
    )
    arguments = parser.parse_args()

    load_plugin_package()
    release = import_module(f"{PACKAGE_NAME}.release")
    errors = import_module(f"{PACKAGE_NAME}.errors")

    try:
        core: Any = release.load_embedded_release_core()
    except errors.PluginError as error:
        print(f"release-core.json is not valid: {error}")
        return 1

    digest = cast(str, release.release_core_digest(core))
    print(digest)
    print(f"release {core.release_id} pins CLI {core.cli_version}")

    if arguments.expected and arguments.expected != digest:
        print(f"expected {arguments.expected}")
        return 1

    if arguments.against_installed_cli:
        return _compare_with_installed_cli(core)
    return 0


def _compare_with_installed_cli(core: Any) -> int:
    """Run the frozen read-only release command and report any disagreement."""
    bridge = import_module(f"{PACKAGE_NAME}.bridge")
    errors = import_module(f"{PACKAGE_NAME}.errors")

    try:
        result = cast(dict[str, Any], bridge.verify_cli_release(core))
    except errors.PluginError as error:
        print(f"could not ask the installed CLI: {error}")
        return 1

    if result["compatible"]:
        print("the installed CLI belongs to this release")
        return 0
    print(f"the installed CLI disagrees about: {', '.join(result['mismatches'])}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
