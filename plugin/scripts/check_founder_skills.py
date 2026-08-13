"""Check the founder Skills a release would pin. Specification sections 7.3, 8.5.

    python scripts/check_founder_skills.py [--skills-root DIR]

Reads each founder Skill, checks it against its behavioural contract from
decision 0007, and reports the digest a release would have to name. Exits
non-zero when a Skill is missing, unreadable, or does not carry its contract.

The two founder Skills do not exist yet. Run it against the test fixtures to
see what it will say when they do:

    python scripts/check_founder_skills.py --skills-root tests/fixtures/skills
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from founder_skill_contract import CHECKS, describe

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Check every founder Skill under the given root."""
    parser = argparse.ArgumentParser(prog="check-founder-skills")
    parser.add_argument(
        "--skills-root",
        type=Path,
        default=REPOSITORY_ROOT / "skills",
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
