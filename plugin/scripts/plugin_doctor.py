"""Run the plugin doctor. Specification sections 7.4, 9.18.

    python scripts/plugin_doctor.py [--json] [--root PATH]

Exits non-zero when a blocking check fails.
"""

from __future__ import annotations

import sys
from importlib import import_module
from typing import cast

from _plugin_package import PACKAGE_NAME, load_plugin_package


def main() -> int:
    """Run the doctor over this checkout."""
    load_plugin_package()
    doctor = import_module(f"{PACKAGE_NAME}.doctor")
    return cast(int, doctor.main(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
