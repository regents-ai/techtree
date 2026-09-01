"""Release-truth regression checks for the v0.1 closeout documentation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = (ROOT / "README.md").read_text(encoding="utf-8")
WP11E = (ROOT / "docs" / "release" / "contracts" / "wp11e.md").read_text(
    encoding="utf-8"
)
DECISION = (
    ROOT / "docs" / "decisions" / "0027-stable-channel-implementation-plan.md"
).read_text(encoding="utf-8")


def _prose(text: str) -> str:
    """Normalize ordinary Markdown line wrapping before checking its prose."""
    return " ".join(text.split())


README_PROSE = _prose(README)
WP11E_PROSE = _prose(WP11E)
DECISION_PROSE = _prose(DECISION)


def test_readme_describes_the_real_v01_path() -> None:
    stale_claims = (
        "Implementation is in progress",
        "WP0–WP5 implementation",
        "fake baseline/candidate executor",
        "Development-only runs",
        "There is no live signing",
        "never read by the fake executor",
    )

    for claim in stale_claims:
        assert claim not in README_PROSE

    for required in (
        "The CLI component contains the real evaluation path",
        "participant-attested",
        "has not been independently reproduced",
        "Release acceptance journeys use a pinned Python 3.12 interpreter",
        # Decision 0038 made publishing a thing somebody can choose, so the
        # flat claim became false. What must survive is the shape of it: the
        # default is that nothing goes, and what goes when somebody asks is
        # the receipt rather than the episodes.
        "Techtree uploads nothing unless you publish a run yourself",
        "the receipt, never the episodes",
        "Model inference is sent to the selected provider",
    ):
        assert required in README_PROSE


def test_wp11e_uses_the_standing_decision_0025_budget() -> None:
    for stale in (
        "3.00 programme cap",
        "~1.03",
        "1.03 of",
    ):
        assert stale not in WP11E_PROSE

    for required in (
        "USD 10.00 programme cap",
        "USD 2.4957",
        "USD 0.30 per comparison",
        "USD 0.30 per host-model call",
        "no retry of any paid outcome",
    ):
        assert required in WP11E_PROSE


def test_founder_channel_and_rollback_ruling_is_recorded() -> None:
    for required in (
        "The Climb v0.1 release channel is `stable`.",
        "non-installable placeholder",
        "rollback floor",
        "All implementation pull requests are drafts.",
        "`regents-ai/techtree-python`",
        "`regents-ai/techtree-hermes`",
        "`regents-ai/techtree-ash`",
    ):
        assert required in DECISION_PROSE

    assert "this implementation-plan approval is not release approval" in DECISION_PROSE
