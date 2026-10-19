"""The regents-cli the contract tests ask is the release this plugin names.

The Makefile pins the regents-cli the real_cli tests run; release-core.json
names the regents-cli release this plugin belongs to. They move together.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_pinned_cli_is_the_release_the_core_names() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    pinned = re.search(r"^REGENTS_CLI_VERSION := (\S+)$", makefile, re.MULTILINE)
    core = json.loads((ROOT / "release-core.json").read_text(encoding="utf-8"))

    assert pinned is not None, "the Makefile names no REGENTS_CLI_VERSION"
    assert pinned.group(1) == core["cli_version"]
