"""Check the founder Skills a release would pin. Specification sections 7.3, 8.5.

    make plugin-founder-skills

Reads each founder Skill from the plugin checkout beside this repository,
checks it against its behavioural contract from decision 0007, and reports the
digest a release would have to name. Exits non-zero when a Skill is missing,
unreadable, or does not carry its contract.

Point it somewhere else to see what it says about a Skill that is not the
released one — the suite's fixtures, for instance:

    python tools/plugin/check_founder_skills.py \\
        --skills-root tests/plugin/fixtures/skills
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from _plugin_package import plugin_checkout
from founder_skill_contract import CHECKS, describe


def main() -> int:
    """Check every founder Skill under the given root."""
    parser = argparse.ArgumentParser(prog="check-founder-skills")
    parser.add_argument(
        "--skills-root",
        type=Path,
        default=plugin_checkout() / "skills",
        help="the directory holding one subdirectory per Skill",
    )
    arguments = parser.parse_args()

    failures = 0
    for name, check in sorted(CHECKS.items()):
        path = arguments.skills_root / name / "SKILL.md"
        print(f"{name}:")
        if not path.is_file():
            print("- not present in this build")
            failures += 1
            continue

        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        problems = check(text)
        print(f"  digest sha256:{hashlib.sha256(raw).hexdigest()}")
        print("  " + describe(problems).replace("\n", "\n  "))
        failures += 1 if problems else 0

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
