"""Export the model-visible tool schemas. Specification section 7.3.

    python scripts/export_tool_schemas.py [--out DIRECTORY]

Without ``--out`` the whole set is printed as one JSON object, which is what
review and release notes quote. With ``--out`` each tool is written to its own
file for diffing between releases.
"""

from __future__ import annotations

import argparse
import json
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from _plugin_package import PACKAGE_NAME, load_plugin_package


def main() -> int:
    """Write or print every declared tool schema."""
    parser = argparse.ArgumentParser(prog="export-tool-schemas")
    parser.add_argument("--out", type=Path, help="directory to write one file per tool")
    arguments = parser.parse_args()

    load_plugin_package()
    schemas_module = import_module(f"{PACKAGE_NAME}.schemas")
    schemas = cast(dict[str, Any], dict(schemas_module.all_tool_schemas()))

    if arguments.out is None:
        print(json.dumps(schemas, indent=2, sort_keys=True))
        return 0

    arguments.out.mkdir(parents=True, exist_ok=True)
    for name, schema in sorted(schemas.items()):
        path = arguments.out / f"{name}.json"
        path.write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
