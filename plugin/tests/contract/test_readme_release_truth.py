"""Release-truth regression checks for the Hermes v0.1 README."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _bash_blocks(document: str) -> tuple[str, ...]:
    return tuple(
        match.group(1)
        for match in re.finditer(r"```bash\n(.*?)\n```", document, re.DOTALL)
    )


def test_readme_names_the_supported_host_and_open_release_path() -> None:
    assert "Supported host: Hermes 0.20.1." in README
    assert "evaluated subject remains the separately\npinned Hermes 0.19.0" in README

    for stale in (
        "Supported host: Hermes 0.20.0.",
        "## Not here yet",
        "stops short of preparing a\ncomparison",
        "the guided\nrevision stops",
    ):
        assert stale not in README

    for required in (
        "This build carries the concrete Climb v0.1 release contract.",
        "It names the\nstarter Skill and the founder-frozen `skill-improver`",
        "The stable release remains an inactive candidate",
    ):
        assert required in README


def test_installation_is_routed_through_the_exact_pinned_guide() -> None:
    for required in (
        "[techtree.sh/start](https://techtree.sh/start)",
        "exact 40-character plugin\ncommit",
        "shows the command argument for argument",
        "needs your approval and installs only the version pinned",
        "A paid\ncomparison has its own separate approval",
    ):
        assert required in README

    for block in _bash_blocks(README):
        assert "<full-40-character-plugin-commit>" not in block
        assert re.search(r"\b(main|latest)\b", block) is None


def test_agent_first_opening_keeps_all_three_approval_boundaries() -> None:
    opening = README.split("## What loading the plugin does", maxsplit=1)[0]

    assert "Ask before installing the plugin" in opening
    assert "installing\n> the Techtree CLI" in opening
    assert "or starting a paid run" in opening
    assert "restart Hermes once" in opening
