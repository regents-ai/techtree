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
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from support import founder_result_payload
from techtree_hermes.constants import PLUGIN_ROOT
from techtree_hermes.models import CliResponse, ReleaseCore
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
        # A next action's reason is written for the host agent to act on and
        # relay, which makes it copy a person meets at second hand. The demo
        # tool is where the first paid step is offered, so its reasons say
        # what that step commits to.
        "tools/demo.py": _string_literals(PLUGIN_ROOT / "tools" / "demo.py"),
        # The second paid step is offered from the uplift tool's payload, and
        # its reason is read out the same way the first one's is, so it is held
        # to the same boundaries.
        "tools/uplift.py": _string_literals(PLUGIN_ROOT / "tools" / "uplift.py"),
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

#: Decisions 0025 and 0029. What a Campaign declares as a maximum is checked
#: before a run starts and a run that could go past it is refused, so copy may
#: say that much. What still does not exist is a price for the run and a
#: cut-off during it: nothing works out what a run will come to, nothing counts
#: the spending while it goes, and nothing ends one part-way through over
#: money. Every pattern here is a protection the reader would be told about and
#: would not get. Each bans the claim in the affirmative only: saying that none
#: of it happens is the whole point of the honest copy, and a guard that could
#: not tell the two apart would forbid the sentences it exists to require.
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
        "tools/demo.py",
        "tools/uplift.py",
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
        "Techtree checks a Campaign's declared maximum before a run and "
        "refuses one whose enforced limits could add up past it, but that "
        "maximum is a ceiling and never a prediction of the bill.",
        "it works out no figure for what this run will actually come to and "
        "keeps no running total while one is under way",
        "It names no price: what a run costs is settled by the user's own "
        "model provider.",
        "no price is worked out in advance and no running total is kept "
        "while the run goes",
        "no finishing time is published for a run",
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


# The publication terms and the declared maximum ---------------------------------------

#: Ticket q0l. A Climb's DataPolicy describes a result that has been published:
#: entering requires releasing the candidate Skill, and the uplift report is
#: public. Reported beside raw-episode terms that prohibit upload outright,
#: those read as a plan to publish somebody's Skill and their numbers, and two
#: agents stopped and refused to start a run over exactly that. Nothing in this
#: build can publish anything. So the terms are reported unchanged and this is
#: reported with them.
PUBLICATION_TERMS_FRAMING: re.Pattern[str] = re.compile(
    r"nothing\s+is\s+published\s+from\s+this\s+build", re.I
)

#: Every surface that hands a Climb's data rights to a reader or to the host
#: agent that will read them out.
PUBLICATION_SURFACES: tuple[str, ...] = (
    "commands.py",
    "tools/demo.py",
    "skills/operator/SKILL.md",
    "skills/operator/references/approvals.md",
)

#: Every tool whose description tells a host agent to show the data policy.
PUBLICATION_TOOLS: tuple[str, ...] = (
    "techtree_climb_inspect",
    "techtree_demo_prepare",
    "techtree_uplift_prepare",
    "techtree_uplift_propose",
)

#: Ticket 8vj. A dollar figure written into the copy is right for one Campaign
#: and wrong for every other one, which is why an earlier example was removed.
#: The review renders what the prepared draft carried.
A_WRITTEN_DOLLAR_FIGURE: re.Pattern[str] = re.compile(r"\$\s?\d")


@pytest.mark.parametrize("surface", PUBLICATION_SURFACES)
def test_the_publication_terms_are_never_shown_without_their_plain_meaning(
    surface: str,
) -> None:
    """Ticket q0l. The terms describe a published result; this build has none."""
    assert PUBLICATION_TERMS_FRAMING.search(PUBLIC_COPY[surface]), surface


@pytest.mark.parametrize("tool", PUBLICATION_TOOLS)
def test_a_tool_that_reports_the_data_rights_says_what_they_mean_here(
    tool: str,
) -> None:
    """The host agent reads the raw terms out of the envelope, so its schema says."""
    description = all_tool_schemas()[tool]["description"]

    assert PUBLICATION_TERMS_FRAMING.search(description), tool


def test_the_publication_truth_says_where_model_calls_still_go() -> None:
    """Decision 0013 s4. "It stays here" is heard as "nothing goes anywhere"."""
    from techtree_hermes.commands import PUBLICATION_TERMS_LINE

    assert PUBLICATION_TERMS_FRAMING.search(PUBLICATION_TERMS_LINE)
    assert has_provider_qualification(PUBLICATION_TERMS_LINE)
    for described, pattern in FORBIDDEN_PRIVACY:
        assert not pattern.search(PUBLICATION_TERMS_LINE), described


def test_the_publication_guard_catches_a_review_that_only_states_the_terms() -> None:
    """The claim the two agents met, in the words they met it in."""
    assert not PUBLICATION_TERMS_FRAMING.search(
        "Public release required in order to enter this Climb. "
        "The uplift report is published."
    )


def test_the_review_that_offers_the_first_paid_run_names_the_declared_maximum() -> None:
    """Ticket 8vj: the terminal review printed this figure and this one did not.

    The figure is the Campaign's and arrives with the prepared draft, so the
    command surface renders it and writes none of its own. A Campaign that
    declares no maximum gets the sentence that says so.
    """
    from techtree_hermes.commands import _declared_maximum_line

    declared = _declared_maximum_line({"campaign_maximum_usd": 2.5})
    undeclared = _declared_maximum_line({})

    assert "$2.50" in declared
    assert "declares no maximum" in undeclared
    for line in (declared, undeclared):
        assert NO_PRICE_FRAMING.search(line), line
        assert NO_METER_FRAMING.search(line), line
        for described, pattern in FORBIDDEN_COST_PROMISE + FORBIDDEN_TIME_PROMISE:
            assert not pattern.search(line), (described, line)


def test_the_review_that_offers_the_second_paid_run_names_the_declared_maximum() -> (
    None
):
    """Ticket jgf: the first run named the figure on both surfaces; this did not.

    The second run has no rendered review of its own — what an operator reads
    is the payload the uplift tool returns with its next action — so that is
    where decision 0019 section 2's budget goes. The reason names the declared
    maximum among the things to show, exactly as the first run's does, and the
    tool that spends the money says what that maximum is and is not, where
    Hermes shows it before asking anybody to confirm.
    """
    offered = PUBLIC_COPY["tools/uplift.py"]
    description = all_tool_schemas()["techtree_uplift_start"]["description"]

    assert "the declared maximum" in offered
    assert "declares it may cost" in description
    assert "never a prediction of the bill" in description
    assert NO_PRICE_FRAMING.search(description)
    assert NO_METER_FRAMING.search(description)


def test_no_copy_writes_a_dollar_figure_of_its_own() -> None:
    """A figure in the copy is right for one Campaign and wrong for the rest."""
    offenders = _offenders(A_WRITTEN_DOLLAR_FIGURE)

    assert not offenders, f"copy names a price of its own: {offenders}"


# The verdict boundary -----------------------------------------------------------------

#: Ticket ip5. A founder's host agent ran the whole journey from one prompt and
#: reported that the run "passed the toy Hello World uplift threshold".
#: Techtree declares no threshold for that comparison and computed no verdict:
#: the agent supplied both, and a reader had no way to tell which half of the
#: sentence was Techtree's evidence and which was the agent's opinion. That is
#: the same failure decision 0013 exists to stop, arriving through the host
#: agent's own wording rather than through the plugin's. The operator Skill is
#: the only surface that steers how a host agent words a result, so the
#: instruction lives there, in the section an agent reads before reporting one.
NO_VERDICT_INSTRUCTION: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "relay what Techtree rendered and stop there",
        re.compile(r"relay\s+what\s+techtree\s+rendered\s+and\s+stop\s+there", re.I),
    ),
    (
        "never passed, failed, good, bad, strong, weak, a success or a win",
        re.compile(
            r"never\s+call\s+a\s+result\s+passed\s+or\s+failed[^.]*"
            r"a\s+success\s+or\s+a\s+win\s+overall",
            re.I,
        ),
    ),
    (
        "never against a threshold Techtree did not declare",
        re.compile(
            r"never\s+hold\s+it\s+against\s+a\s+threshold[^.]*"
            r"techtree\s+did\s+not\s+itself\s+declare\s+and\s+render",
            re.I,
        ),
    ),
    (
        "never works or does not work from one toy comparison",
        re.compile(
            r"never\s+say\s+a\s+skill\s+works[^.]*"
            r"one\s+comparison\s+on\s+a\s+synthetic\s+toy\s+task\s+set",
            re.I,
        ),
    ),
    (
        "the reason, so the rule survives paraphrase",
        re.compile(
            r"verdict\s+techtree\s+did\s+not\s+compute\s+is\s+your\s+opinion\s+"
            r"wearing\s+techtree'?s\s+evidence",
            re.I,
        ),
    ),
)


@pytest.mark.parametrize(
    ("described", "pattern"),
    NO_VERDICT_INSTRUCTION,
    ids=[described for described, _ in NO_VERDICT_INSTRUCTION],
)
def test_the_operator_skill_forbids_a_verdict_of_the_agents_own(
    described: str, pattern: re.Pattern[str]
) -> None:
    """Ticket ip5. Each half of the instruction is load-bearing on its own."""
    skill = " ".join(PUBLIC_COPY["skills/operator/SKILL.md"].split())

    assert pattern.search(skill), f"the operator Skill no longer says: {described}"


def test_the_verdict_guard_catches_a_skill_that_lost_the_instruction() -> None:
    """The Skill as it read before ip5: numbers relayed, verdicts unmentioned."""
    without = (
        "Techtree renders the result and the plugin relays it unchanged. Use "
        "those numbers. Do not compute your own, round them into a better "
        "story, or describe a tie as a win."
    )

    for described, pattern in NO_VERDICT_INSTRUCTION:
        assert not pattern.search(without), described


# What a finished result actually says ------------------------------------------------

#: Ticket tzz. Techtree's own result screen leads with the count a person reads
#: a result in, names what the run cost and where that figure came from, names
#: the attestation gap in plain words, puts the model turns beside the clock,
#: and says how often the provider refused each side. The plugin relays the
#: same payload, and the founder's journey ran through the plugin rather than
#: the terminal — so a relay that dropped any of it would show the person on
#: the primary route strictly less than the terminal shows.
#:
#: These guards hold the relay to the payload. They assert nothing about
#: numbers the plugin invents, because it invents none: every figure below is
#: read out of a payload built here with Techtree's own presentation models, so
#: a field renamed in Techtree fails this file rather than quietly emptying a
#: line in somebody's chat window.


def _relayed_text(payload: Mapping[str, object]) -> str:
    """Return what `/techtree result` shows for this payload."""
    from techtree_hermes.approvals import InstallPlanStore
    from techtree_hermes.commands import handle_slash_command
    from techtree_hermes.release import load_embedded_release_core, release_core_digest
    from techtree_hermes.services.assets import ReleaseSkillProvider
    from techtree_hermes.services.container import PluginServices
    from techtree_hermes.state import SessionStore

    core = load_embedded_release_core()
    services = PluginServices(
        ctx=None,
        root=PLUGIN_ROOT,
        release_core=core,
        release_core_digest=release_core_digest(core),
        bridge=_ResultBridge(payload),
        plans=InstallPlanStore(),
        sessions=SessionStore(),
        assets=ReleaseSkillProvider(),
    )
    return handle_slash_command(f"result {payload['run_id']}", services)


class _ResultBridge:
    """A CLI that answers `run result` with one prepared payload.

    Relaying a result asks the CLI one question, so only ``invoke`` answers.
    The rest of the bridge is written out because the container is given a
    whole CLI boundary, and each one says plainly why the relay may not reach
    it rather than quietly returning something a test could then believe.
    """

    def __init__(self, payload: Mapping[str, object]) -> None:
        self._payload = payload

    def invoke(self, arguments: Sequence[str]) -> dict[str, object]:
        return {
            "schema_version": "techtree.cli.v1",
            "command": "run result",
            "ok": True,
            "data": {
                "report": {"run_id": self._payload["run_id"]},
                "presentation": dict(self._payload),
            },
            "error": None,
            "messages": [],
            "warnings": [],
            "next_actions": [],
        }

    def call(self, arguments: Sequence[str], *, purpose: str = "") -> CliResponse:
        raise AssertionError("relaying a result needs no exit code")

    def invoke_human(self, arguments: Sequence[str]) -> int:
        raise AssertionError("relaying a result runs no terminal command")

    def version(self) -> str:
        raise AssertionError("relaying a result reads no version string")

    def verify_release(self, expected: ReleaseCore) -> dict[str, object]:
        raise AssertionError("relaying a result verifies no release")


def _compact(payload: Mapping[str, object]) -> dict[str, object]:
    """Return what a phone is shown of this payload."""
    from techtree_hermes.services.presentation import compact_presentation

    return compact_presentation(payload)


def test_the_relay_leads_with_the_count_a_person_reads_a_result_in() -> None:
    """Ticket tzz. A mean over a toy task set is not what anybody repeats."""
    text = _relayed_text(founder_result_payload())

    assert "0 of 36 → 24 of 36" in text
    assert "mean 0.000 → 0.667 (+0.667)" in text
    lines = text.splitlines()
    assert lines[1].startswith("Tasks 0 of 36 → 24 of 36"), lines[:3]


def test_a_reward_with_no_such_count_has_none_invented_for_it() -> None:
    """The count is a real fact about an all-or-nothing reward, or nothing."""
    text = _relayed_text(
        founder_result_payload(
            baseline_tasks_scored_full=None, candidate_tasks_scored_full=None
        )
    )

    assert "of 36" not in text
    assert "Mean score 0.000 → 0.667 (+0.667)" in text


def test_the_relay_carries_the_cost_and_the_kind_of_figure_it_is() -> None:
    """Decision 0007 R6: the word that tells them apart travels with the figure."""
    text = _relayed_text(founder_result_payload())

    assert "Cost: about $4.87, worked out here, not billed" in text
    assert "Computed from 1,900,000 input and 542,125 output tokens" in text
    assert "Your provider's bill is what you actually pay." in text
    assert "410,000 of those input tokens came back from the provider's cache" in text


def test_a_figure_the_provider_reported_is_relayed_as_that_and_not_as_derived() -> None:
    """The better-sourced figure exists only when the provider gave one."""
    text = _relayed_text(
        founder_result_payload(
            cost_usd=5.12, cost_provenance="provider_reported", derived_cost=None
        )
    )

    assert "Cost: $5.12, reported by the provider" in text
    assert "worked out here" not in text
    assert "Computed from" not in text


def test_a_run_with_no_cost_says_which_half_of_one_it_is_missing() -> None:
    """ "Unavailable" alone leaves a reader unable to tell what went missing."""
    reason = (
        "This run wrote no signed execution record, so there is no signed "
        "token total to work a cost out from."
    )
    text = _relayed_text(
        founder_result_payload(derived_cost=None, cost_unavailable_reason=reason)
    )

    assert "Cost: unavailable" in text
    assert reason in text


def test_the_relay_carries_every_qualification_and_names_the_attestation_gap() -> None:
    """Room is made by cutting detail, never by cutting a qualification."""
    payload = founder_result_payload()
    text = _relayed_text(payload)

    warnings = [
        caveat["text"] for caveat in payload["caveats"] if caveat["severity"] != "info"
    ]
    for warning in warnings:
        assert warning in text, warning
    assert "not provably the same model build" in text
    assert "refused 3 model calls with a rate limit on the baseline side" in text


def test_the_relay_puts_the_model_turns_beside_the_clock() -> None:
    """Turns are a property of the work; the clock is a property of the day."""
    text = _relayed_text(founder_result_payload())

    assert "the candidate side took 412 model turns against the baseline's 388" in text
    assert "finished in 598.4s against 612.0s" in text
    assert "Turns are a property of the work." in text


def test_a_run_with_no_recorded_turns_still_reports_the_clock() -> None:
    """A run whose traces could not be read says the part it does have."""
    text = _relayed_text(
        founder_result_payload(
            baseline_model_turns=None,
            candidate_model_turns=None,
            baseline_rate_limited_calls=None,
            candidate_rate_limited_calls=None,
            every_rollout_completed=None,
        )
    )

    assert "Time: baseline 612.0s, candidate 598.4s" in text
    assert "model turns" not in text


def test_the_relay_adds_no_verdict_of_its_own() -> None:
    """Ticket ip5's boundary, held on the surface that does the relaying.

    Every word Techtree wrote is removed first, and what is left is the
    plugin's own contribution. A verdict may not appear in it.
    """
    payload = founder_result_payload()
    remainder = _relayed_text(payload)
    for caveat in payload["caveats"]:
        remainder = remainder.replace(caveat["text"], "")
    verdicts = re.compile(
        r"\b(passed|failed|succeeded|success|good|bad|strong|weak|threshold"
        r"|works|improvement)\b",
        re.I,
    )

    assert not verdicts.search(remainder), remainder


def test_the_relayed_result_makes_no_claim_the_copy_boundaries_forbid() -> None:
    """The relayed text is copy a person reads, and is held to the same lines."""
    text = _relayed_text(founder_result_payload())

    for described, pattern in (
        *FORBIDDEN_PRIVACY,
        *FORBIDDEN_ATTESTATION,
        *FORBIDDEN_AGENCY,
    ):
        assert not pattern.search(text), described
    assert not FORBIDDEN_OWNERSHIP.search(text)
    assert not FORBIDDEN_ACCOUNT.search(text)


def test_the_phone_is_shown_the_counts_the_turns_the_throttling_and_the_cost() -> None:
    """Ticket tzz. The whitelist dropped every one of these before this."""
    compact = _compact(founder_result_payload())

    assert compact["baseline_tasks_scored_full"] == 0
    assert compact["candidate_tasks_scored_full"] == 24
    assert compact["task_count"] == 36
    assert compact["baseline_model_turns"] == 388
    assert compact["candidate_model_turns"] == 412
    assert compact["baseline_rate_limited_calls"] == 3
    assert compact["candidate_rate_limited_calls"] == 11
    assert compact["every_rollout_completed"] is True
    assert compact["derived_cost"]["usd"] == 4.87  # type: ignore[index]
    assert compact["cost_usd"] is None
    assert compact["cost_provenance"] == "unavailable"


def test_the_phone_carries_the_qualifications_and_never_a_note_instead() -> None:
    """A phone is where a number is most likely to be quoted onwards."""
    compact = _compact(founder_result_payload())
    caveats = compact["caveats"]
    assert isinstance(caveats, list)

    assert len(caveats) == 3
    assert "not provably the same model build" in caveats[0]
    assert all("No external evidence service" not in text for text in caveats)


def test_the_phone_whitelist_is_still_a_whitelist() -> None:
    """A field reaches a phone because it was named, never because it existed."""
    compact = _compact(
        founder_result_payload(a_field_nobody_whitelisted="this must not travel")
    )

    assert "a_field_nobody_whitelisted" not in compact
    assert "task_rows" not in compact
    assert "baseline_skill" not in compact
    assert "next_actions" not in compact


def test_the_phone_answer_still_fits_the_channel_it_is_read_in() -> None:
    """An answer over the budget is replaced whole, so it has to fit."""
    from techtree_hermes.models import ChannelKind
    from techtree_hermes.release import load_embedded_release_core
    from techtree_hermes.services.presentation import PresentationService
    from techtree_hermes.tools import tool_result

    payload = founder_result_payload()
    service = PresentationService(release=load_embedded_release_core())
    answer = tool_result(
        service.deterministic_only(
            result_envelope={
                "ok": True,
                "data": {"report": {}, "presentation": payload},
            },
            channel=ChannelKind.GATEWAY,
        ),
        ChannelKind.GATEWAY,
    )

    assert '"truncated"' not in answer
    assert "0 of 36" not in answer  # the count travels as two fields, not as prose
    assert json.loads(answer)["presentation"]["candidate_tasks_scored_full"] == 24
    assert "not provably the same model build" in answer


def test_a_result_whose_qualifications_are_long_keeps_the_answer_whole() -> None:
    """The one part of a compact answer a run can make arbitrarily long."""
    from techtree_hermes.models import ChannelKind
    from techtree_hermes.release import load_embedded_release_core
    from techtree_hermes.services.presentation import PresentationService
    from techtree_hermes.tools import tool_result

    payload = founder_result_payload(
        caveats=[
            {"code": f"long_{index}", "severity": "warning", "text": "detail " * 120}
            for index in range(6)
        ]
    )
    service = PresentationService(release=load_embedded_release_core())
    relayed = service.deterministic_only(
        result_envelope={"ok": True, "data": {"report": {}, "presentation": payload}},
        channel=ChannelKind.GATEWAY,
    )
    answer = tool_result(relayed, ChannelKind.GATEWAY)

    assert '"truncated"' not in answer
    assert relayed["presentation"]["caveats"]
    assert relayed["presentation"]["caveats_not_shown"]


# The interpreter the plugin offers to install onto -----------------------------------


def test_the_plugin_offers_the_python_this_release_actually_supports() -> None:
    """The plugin's copy of the interpreter must be the package's own floor.

    Decision 0031 pinned the interpreter in the published install command and
    bound the website document's copy to the command it publishes. The plugin
    offers that same command from its own checkout and carries no bootstrap
    document to read the number out of - it ships only the release contract,
    which deliberately holds no install command at all.

    So its copy is bound here instead, to the floor of the range the techtree
    package declares. That is the value an installer obeys and the doctor
    reports, so a plugin naming anything else would offer a command whose
    result the product then refuses - which is the report decision 0031 came
    from, arriving by a different door. The range is read from the package
    metadata rather than written down again: repeating the parsing is not
    repeating the fact.
    """
    import tomllib

    from techtree_hermes.constants import CLI_PYTHON_SERIES

    root = Path(__file__).resolve().parents[3]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    floor = metadata["project"]["requires-python"].split(",")[0].strip().lstrip(">=")

    assert ".".join(floor.split(".")[:2]) == CLI_PYTHON_SERIES
