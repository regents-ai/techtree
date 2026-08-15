"""What the plugin's public copy may and may not claim. Decision 0013.

Three claims are easy to make by accident and expensive to have made: that
nothing is sent anywhere, that no account is needed, and that somebody other
than the participant verified the run. None of the three is true of Techtree
v0.1, and each one is the kind of sentence that gets written by a person
trying to be reassuring rather than by a person trying to be exact.

So the copy is scanned rather than reviewed. Every surface a user or the host
agent actually reads is here: the model-visible tool schemas, the `/techtree`
command surface, the guided-revision disclosure, the README, and the operator
Skill with its references.

Decision 0018 added a fourth boundary to the three above: the guided revision
may produce nothing useful, and copy may not promise otherwise.

Decision 0025 adds two more, and they are the same mistake twice. The Campaign
declares a maximum spend and a per-episode timeout; nothing works out what a
run will come to before it starts, nothing watches the spending while it runs,
and nothing ends a run when the declared time is up. A declared figure is a
contract value, and copy that phrases one as a meter or a cut-off is telling
the reader a protection exists. So the copy may not promise a price in advance,
may not promise that spending stops a run, and may not promise that a run is
over by any particular time.

`skills/skill-improver/SKILL.md` is deliberately absent. It is founder-written
and frozen by digest, it is never shown to a user, and a test that could
demand an edit to it would be a test that could break a release coordinate.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from techtree_hermes.constants import PLUGIN_ROOT
from techtree_hermes.schemas import all_tool_schemas

# What counts as public copy -------------------------------------------------------


def _string_literals(source: Path) -> str:
    """Return every string a Python copy module carries, as one document.

    Read through the parser rather than by regular expression so that copy
    written as several adjacent literals — which most of it is — is scanned as
    the one sentence it becomes, not as fragments that each look innocent.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    return "\n".join(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


def _public_copy() -> dict[str, str]:
    copy = {
        "schemas.py": _string_literals(PLUGIN_ROOT / "schemas.py"),
        "commands.py": _string_literals(PLUGIN_ROOT / "commands.py"),
        # The guided-revision disclosure is read out to a person verbatim, so
        # it is public copy and is held to the same boundaries.
        "approvals.py": _string_literals(PLUGIN_ROOT / "approvals.py"),
        "README.md": (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8"),
    }
    operator = PLUGIN_ROOT / "skills" / "operator"
    for document in sorted(operator.rglob("*.md")):
        copy[str(document.relative_to(PLUGIN_ROOT))] = document.read_text(
            encoding="utf-8"
        )
    return copy


PUBLIC_COPY = _public_copy()

#: The founder Skill is frozen by digest and never read by a user.
EXCLUDED_FROM_SCAN = PLUGIN_ROOT / "skills" / "skill-improver" / "SKILL.md"


# The four boundaries ----------------------------------------------------------------

#: Privacy claims that are false however they are qualified. Decision 0013 s4:
#: push=false stops the Verifiers upload; it does not make remote inference
#: local.
FORBIDDEN_PRIVACY: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "nothing leaves the laptop",
        re.compile(r"nothing\s+leaves\s+(the|your)\s+", re.I),
    ),
    ("nothing is sent anywhere", re.compile(r"nothing\s+is\s+sent\s+anywhere", re.I)),
    (
        "fully offline evaluation",
        re.compile(r"(fully|completely|entirely)\s+offline\s+evaluation", re.I),
    ),
)

#: Sweeping "we send nothing" claims. True of Techtree's own uploads, false as
#: a description of a run, so each one has to be qualified in its own document.
NEEDS_PROVIDER_QUALIFICATION: re.Pattern[str] = re.compile(
    r"nothing\s+(is|was|gets|ever)\s+(uploaded|sent|published|fetched)"
    r"|nothing\s+(leaves|left)\b"
    r"|(uploads?|sends?|publishes)\s+nothing",
    re.I,
)

#: The nouns that make a sentence a statement about where inference goes.
_INFERENCE_NOUN: re.Pattern[str] = re.compile(
    r"\b(model\s+inference|model\s+calls?|inference)\b", re.I
)
_PROVIDER_NOUN: re.Pattern[str] = re.compile(r"\bprovider\b", re.I)


def _sentences(text: str) -> list[str]:
    """Return the document as sentences, with its line wrapping undone."""
    return re.split(r"(?<=[.!?;])\s+", " ".join(text.split()))


def has_provider_qualification(text: str) -> bool:
    """Whether some one sentence says inference goes to the provider.

    One sentence, not one document: a page that mentions a provider somewhere
    for an unrelated reason has not qualified anything, and an earlier version
    of this guard was fooled by exactly that.
    """
    return any(
        _INFERENCE_NOUN.search(sentence) and _PROVIDER_NOUN.search(sentence)
        for sentence in _sentences(text)
    )


#: A Prime/provider account, an API credential, and network access may all be
#: needed. Only the Techtree-scoped claim is true.
FORBIDDEN_ACCOUNT: re.Pattern[str] = re.compile(
    r"(?<!techtree\s)\bno\s+account\s+(is\s+)?(required|needed)\b", re.I
)

#: Nobody but the participant attested this execution. Decision 0013 s1.
FORBIDDEN_ATTESTATION: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "Techtree verified the execution",
        re.compile(r"techtree\s+verified\s+the\s+execution", re.I),
    ),
    ("verified by Techtree", re.compile(r"verified\s+by\s+techtree", re.I)),
    ("independently verified", re.compile(r"independently\s+(verified|proven)", re.I)),
    ("trustless proof", re.compile(r"trustless\s+proof", re.I)),
    ("proof of honest compute", re.compile(r"proof\s+of\s+honest\s+compute", re.I)),
    ("without trusting us", re.compile(r"without\s+trusting\s+us\b", re.I)),
)

#: The forbidden public name for the introductory Climb. Decision 0009.
FORBIDDEN_NAME: re.Pattern[str] = re.compile(r"HelloWorldBench", re.I)

#: Decision 0013 s3, sharpened by WP11g S8. The Campaign pins the subject
#: model, so it is never the reader's own; and two different providers are in
#: play at once, so a possessive is exactly the wrong word. Only the literal
#: phrase is banned — "your model provider" is a true and useful thing to say.
FORBIDDEN_OWNERSHIP: re.Pattern[str] = re.compile(r"\byour\s+own\s+models?\b", re.I)

#: Decision 0018 s5. The guided revision may produce nothing useful, and the
#: approved framing says so. These say the opposite — that the agent is an
#: improving thing which will get there — and each one is a promise about an
#: outcome no one has measured yet.
FORBIDDEN_AGENCY: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "your agent will fix the Skill",
        re.compile(r"\byour\s+agent\s+will\b|\bwill\s+fix\s+the\s+skill\b", re.I),
    ),
    (
        "it learns from its mistakes",
        re.compile(r"\blearns?\s+from\s+(its|their|your)\s+(mistakes|errors)\b", re.I),
    ),
    ("it will close the gap", re.compile(r"\bclos(e|es|ing)\s+the\s+gap\b", re.I)),
)

#: The framing that has to be there instead, wherever the revision is offered.
MAY_FAIL_FRAMING: re.Pattern[str] = re.compile(
    r"may\s+be\s+unusable\s+or\s+may\s+fail\s+to\s+improve", re.I
)

#: An exact score is not what was calibrated. Decision 0015 s6: the claim is
#: the 20-27/36 band, or "roughly two-thirds of the toy tasks". Either dash
#: spelling of the band counts, which is why the pattern names both.
FORBIDDEN_EXACT_SCORE: re.Pattern[str] = re.compile(
    r"\bscor(e|es|ed)\s+\d+\b"
    r"|\bsolves?\s+\d+\s+(of|out\s+of)\s+\d+\b"
    r"|\b\d{1,2}\s*/\s*36\b",
    re.I,
)

#: The band itself, removed before the exact-score scan. The same idiom the
#: presentation guard uses: a check that flagged the honest phrasing for
#: containing the dishonest one would be a check that punishes candour.
PERMITTED_BAND: re.Pattern[str] = re.compile("\\b20\\s*[-\\u2013]\\s*27\\s*/\\s*36\\b")

#: Decision 0025. Nothing works out a price before a run and nothing ends a run
#: for spending too much, so every one of these is a protection the reader
#: would be told about and would not get. Each pattern bans the claim in the
#: affirmative only: saying that none of it happens is the whole point of the
#: honest copy, and a guard that could not tell the two apart would forbid the
#: sentences it exists to require.
FORBIDDEN_COST_PROMISE: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("a cost bound", re.compile(r"\bcost\s+(bound|ceiling|cap|limit)s?\b", re.I)),
    (
        "a budget estimate",
        re.compile(r"\b(budget|cost|spending|spend|price)\s+estimates?\b", re.I),
    ),
    (
        "a price worked out in advance",
        re.compile(
            r"\b(estimates?|calculates?|computes?|predicts?|projects?|forecasts?"
            r"|works?\s+out|tells?\s+you)\s+(the\s+|your\s+)?"
            r"(cost|price|spend|spending|bill|total)\b"
            r"|\b(shows?|tells?)\s+you\s+what\s+(this|it|the\s+run)\s+"
            r"(costs?|will\s+cost|comes?\s+to)\b",
            re.I,
        ),
    ),
    (
        "an estimated cost",
        re.compile(r"\bestimated\s+(cost|spend|spending|price|bill|budget)\b", re.I),
    ),
    (
        "a run that stops itself over money",
        re.compile(
            r"\b(abort|aborts|aborted|halt|halts|halted|kill|kills|stop|stops"
            r"|stopped|cut\s+off|cuts\s+off)\b[^.]{0,50}"
            r"\b(budget|ceiling|spending\s+limit|cost\s+limit|spending\s+cap"
            r"|overspend|over\s+budget)\b",
            re.I,
        ),
    ),
    (
        "a promise about the bill",
        re.compile(
            r"\b(won'?t|will\s+not|never)\s+(cost|spend|exceed|charge)\b"
            r"|\b(at\s+most|no\s+more\s+than|up\s+to)\s+\$\s?\d",
            re.I,
        ),
    ),
)

#: Decision 0025 again, for the clock. The Campaign's declared timeout is
#: enforced by nothing, so a run has no finishing time anybody can state.
FORBIDDEN_TIME_PROMISE: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("the declared 600 seconds", re.compile(r"\b600[\s-]*seconds?\b", re.I)),
    (
        "a stated run duration",
        re.compile(
            r"\b(up\s+to|no\s+more\s+than|at\s+most|within|under|less\s+than)\s+"
            r"\d+\s*(seconds?|minutes?|hours?|s|m)\b",
            re.I,
        ),
    ),
    (
        "a time-bounded run",
        re.compile(r"\btime[-\s](bound|bounded|limited|capped|boxed)\b", re.I),
    ),
    ("a run time limit", re.compile(r"\b(time|run|episode)\s+limits?\b", re.I)),
    (
        "a timeout",
        re.compile(r"\btimeouts?\b|\btimes?\s+out\b|\btimed\s+out\b", re.I),
    ),
    ("a deadline", re.compile(r"\bdeadlines?\b", re.I)),
    (
        "a promised finish",
        re.compile(
            r"\b(finish|finishes|complete|completes|end|ends|done)\s+"
            r"(in|within|after)\s+\d+\s*(seconds?|minutes?|hours?)\b",
            re.I,
        ),
    ),
)

#: The other half of each ban. Forbidding the overclaim leaves a surface free
#: to say nothing at all, which is how a promise gets deleted and the reader
#: still walks away expecting one. Wherever the plugin tells a host agent to
#: spend somebody's money, it also has to say that no price is worked out and
#: nothing is watching the spending.
NO_PRICE_FRAMING: re.Pattern[str] = re.compile(
    r"works?\s+out\s+no\s+figure|no\s+price\s+is\s+worked\s+out|names\s+no\s+price",
    re.I,
)
NO_METER_FRAMING: re.Pattern[str] = re.compile(
    r"keeps\s+no\s+running\s+total|no\s+running\s+total\s+is\s+kept", re.I
)


def _offenders(
    pattern: re.Pattern[str], scrub: re.Pattern[str] | None = None
) -> list[str]:
    """Return every surface whose copy matches, with the sentence that did."""
    found = []
    for name, text in PUBLIC_COPY.items():
        for sentence in _sentences(scrub.sub("", text) if scrub else text):
            if pattern.search(sentence):
                found.append(f"{name}: {sentence.strip()}")
    return found


# The scans ---------------------------------------------------------------------------


def test_the_scan_reads_every_public_surface() -> None:
    """A guard nobody pointed at the copy guards nothing."""
    assert set(PUBLIC_COPY) >= {
        "schemas.py",
        "commands.py",
        "README.md",
        "skills/operator/SKILL.md",
    }
    assert all(text.strip() for text in PUBLIC_COPY.values())
    assert str(EXCLUDED_FROM_SCAN.relative_to(PLUGIN_ROOT)) not in PUBLIC_COPY


@pytest.mark.parametrize(
    ("described", "pattern"),
    FORBIDDEN_PRIVACY,
    ids=lambda value: getattr(value, "pattern", value),
)
def test_no_copy_claims_the_work_is_local(
    described: str, pattern: re.Pattern[str]
) -> None:
    """Decision 0013 s4. Model inference is sent to the provider, always."""
    offenders = _offenders(pattern)

    assert not offenders, f"copy claims {described!r}: {offenders}"


def test_a_claim_that_nothing_is_sent_is_qualified_where_it_is_made() -> None:
    """A sweeping "we send nothing" needs the provider sentence beside it."""
    unqualified = [
        f"{name}: {sentence.strip()}"
        for name, text in PUBLIC_COPY.items()
        if not has_provider_qualification(text)
        for sentence in _sentences(text)
        if NEEDS_PROVIDER_QUALIFICATION.search(sentence)
    ]

    assert not unqualified, (
        "these say nothing is sent, in a document that never says model "
        f"inference goes to the provider: {unqualified}"
    )


def test_an_unrelated_mention_of_a_provider_does_not_qualify_anything() -> None:
    """The bug this guard had once: a provider named for another reason."""
    assert not has_provider_qualification(
        "Nothing is uploaded, ever. A model provider may not expose an "
        "immutable revision for the model it serves."
    )
    assert has_provider_qualification(
        "Nothing Techtree holds is uploaded. Model inference still goes to "
        "the model provider you configured."
    )


def test_no_copy_says_no_account_is_required() -> None:
    """Decision 0013 s2. Only the Techtree-scoped claim is true."""
    offenders = _offenders(FORBIDDEN_ACCOUNT)

    assert not offenders, f"copy overclaims about accounts: {offenders}"


def test_the_techtree_scoped_account_claim_is_still_allowed() -> None:
    """The guard must permit the sentence the release is meant to use."""
    assert not FORBIDDEN_ACCOUNT.search("No Techtree account is required.")
    assert FORBIDDEN_ACCOUNT.search("No account is required.")


@pytest.mark.parametrize(
    ("described", "pattern"),
    FORBIDDEN_ATTESTATION,
    ids=lambda value: getattr(value, "pattern", value),
)
def test_no_copy_claims_somebody_else_verified_the_run(
    described: str, pattern: re.Pattern[str]
) -> None:
    """Decision 0013 s1. The participant attested it; nobody reproduced it."""
    offenders = _offenders(pattern)

    assert not offenders, f"copy claims {described!r}: {offenders}"


def test_the_honest_attestation_wording_is_still_allowed() -> None:
    """The guard must not punish the sentences the release is meant to use."""
    permitted = (
        "participant-attested local execution",
        "integrity verified",
        "offline-verifiable evidence bundle",
        "it has not been independently reproduced",
    )

    for sentence in permitted:
        for _, pattern in FORBIDDEN_ATTESTATION:
            assert not pattern.search(sentence), sentence


def test_no_copy_uses_the_forbidden_climb_name() -> None:
    """Decision 0009: the public name is Techtree Hello World."""
    assert not _offenders(FORBIDDEN_NAME)


def test_no_copy_calls_the_subject_model_the_readers_own() -> None:
    """Decision 0013 s3 / WP11g S8: the Campaign pins the model, not the user."""
    offenders = _offenders(FORBIDDEN_OWNERSHIP)

    assert not offenders, f"copy says the model is the reader's own: {offenders}"


def test_the_ban_is_the_exact_phrase_and_not_the_useful_one() -> None:
    """ "your model provider" has to stay sayable; "your own model" does not."""
    assert FORBIDDEN_OWNERSHIP.search("it runs your own model twice")
    assert FORBIDDEN_OWNERSHIP.search("bring your own models")
    assert not FORBIDDEN_OWNERSHIP.search("sent to your model provider")
    assert not FORBIDDEN_OWNERSHIP.search("under your provider's policies")


def test_the_guided_revision_says_where_the_skill_text_goes() -> None:
    """WP11g S2: the host agent's provider sees the Skill and the context."""
    surfaces = {
        "schemas.py": PUBLIC_COPY["schemas.py"],
        "skills/operator/SKILL.md": PUBLIC_COPY["skills/operator/SKILL.md"],
    }

    for name, text in surfaces.items():
        collapsed = " ".join(text.split()).lower()
        assert "model provider" in collapsed, name
        assert "not the one the evaluated run uses" in collapsed, name


@pytest.mark.parametrize(
    ("described", "pattern"),
    FORBIDDEN_AGENCY,
    ids=lambda value: getattr(value, "pattern", value),
)
def test_no_copy_promises_the_agent_will_improve_itself(
    described: str, pattern: re.Pattern[str]
) -> None:
    """Decision 0018 s5. The revision may produce nothing, and copy must allow it."""
    offenders = _offenders(pattern)

    assert not offenders, f"copy promises {described!r}: {offenders}"


def test_the_may_fail_framing_is_the_one_that_is_used() -> None:
    """Forbidding the overclaim is only half of it; the honest line has to be there."""
    from techtree_hermes.approvals import GUIDED_REVISION_DISCLOSURE

    assert MAY_FAIL_FRAMING.search(" ".join(GUIDED_REVISION_DISCLOSURE))


def test_the_agency_ban_leaves_ordinary_description_alone() -> None:
    """It must stay possible to say what the step does."""
    for allowed in (
        "Your Hermes model will propose one revision.",
        "Techtree will test it.",
        "the agent this person is talking to",
        "a proposal may be unusable or may fail to improve the score",
    ):
        for _, pattern in FORBIDDEN_AGENCY:
            assert not pattern.search(allowed), allowed


def test_no_copy_claims_an_exact_score() -> None:
    """Decision 0015 s6: the calibrated claim is a band, not a number."""
    offenders = _offenders(FORBIDDEN_EXACT_SCORE, scrub=PERMITTED_BAND)

    assert not offenders, f"copy claims an exact score: {offenders}"


@pytest.mark.parametrize(
    ("described", "pattern"),
    FORBIDDEN_COST_PROMISE,
    ids=[described for described, _ in FORBIDDEN_COST_PROMISE],
)
def test_no_copy_promises_a_price_or_a_spending_cut_off(
    described: str, pattern: re.Pattern[str]
) -> None:
    """Decision 0025. Neither the figure nor the cut-off exists."""
    offenders = _offenders(pattern)

    assert not offenders, f"copy promises {described!r}: {offenders}"


@pytest.mark.parametrize(
    ("described", "pattern"),
    FORBIDDEN_TIME_PROMISE,
    ids=[described for described, _ in FORBIDDEN_TIME_PROMISE],
)
def test_no_copy_promises_a_run_is_over_by_a_certain_time(
    described: str, pattern: re.Pattern[str]
) -> None:
    """Decision 0025. The declared timeout is enforced by nothing."""
    offenders = _offenders(pattern)

    assert not offenders, f"copy promises {described!r}: {offenders}"


def test_the_surfaces_that_spend_money_say_no_price_is_worked_out() -> None:
    """Deleting the overclaim is half of it; the honest line has to be there.

    The two tools that spend somebody's money and the command surface that
    offers the first one are the places a person decides, so each of them says
    what does not happen rather than leaving the reader to assume it does.
    """
    schemas = all_tool_schemas()

    for name in ("techtree_climb_start", "techtree_uplift_start"):
        description = schemas[name]["description"]
        assert NO_PRICE_FRAMING.search(description), name
        assert NO_METER_FRAMING.search(description), name

    assert NO_PRICE_FRAMING.search(PUBLIC_COPY["commands.py"])
    assert NO_METER_FRAMING.search(PUBLIC_COPY["commands.py"])
    assert NO_PRICE_FRAMING.search(PUBLIC_COPY["skills/operator/SKILL.md"])
    assert NO_METER_FRAMING.search(PUBLIC_COPY["skills/operator/SKILL.md"])


def test_the_honest_money_and_clock_wording_is_still_allowed() -> None:
    """The guards must not forbid the sentences they exist to require."""
    permitted = (
        "Techtree works out no figure before a run and keeps no running "
        "total while one is under way.",
        "It names no price: what a run costs is settled by the user's own "
        "model provider.",
        "no price is worked out in advance and no running total is kept "
        "while the run goes",
        "nothing stops it if it goes past",
        "This spends real money on model calls.",
        "A Climb is slow work, and nothing ends one at a set time.",
        "Never quote a price or a finishing time; neither one exists.",
        "The offer expires after a few minutes, and works once.",
        "Only stop a run with techtree_run_cancel when the person asks you to.",
    )

    for sentence in permitted:
        for described, pattern in FORBIDDEN_COST_PROMISE + FORBIDDEN_TIME_PROMISE:
            assert not pattern.search(sentence), (described, sentence)


def test_the_money_and_clock_guards_catch_what_they_are_for() -> None:
    """The claims decision 0025 removed, in the words they were written in."""
    refused = (
        "how many tasks it runs, its cost bound, its proof grade",
        "the episode and budget estimate",
        "review the Skill-only change and the estimated cost",
        "It estimates the cost before anything starts.",
        "The run aborts when it goes over budget.",
        "It will never cost more than the ceiling.",
        "Each run may take up to 600 seconds.",
        "Every run is time-bounded.",
        "There is a run limit of ten minutes.",
        "The comparison times out and stops itself.",
        "Each episode has a deadline.",
    )

    for sentence in refused:
        assert any(
            pattern.search(sentence)
            for _, pattern in FORBIDDEN_COST_PROMISE + FORBIDDEN_TIME_PROMISE
        ), sentence


def test_the_band_wording_is_still_allowed() -> None:
    """The guard must permit the phrasings decision 0015 s6 fixed."""
    for permitted in (
        "calibrated to the 20\u201327/36 band",
        "calibrated to the 20-27/36 band",
        "solves roughly two-thirds of the toy tasks; individual runs may vary",
    ):
        assert not FORBIDDEN_EXACT_SCORE.search(PERMITTED_BAND.sub("", permitted))

    for refused in ("the starter Skill scores 24", "it reaches 24/36"):
        assert FORBIDDEN_EXACT_SCORE.search(PERMITTED_BAND.sub("", refused))
