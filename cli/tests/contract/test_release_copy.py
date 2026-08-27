"""What this repository's public copy may and may not claim. Decision 0013.

Four claims are easy to make by accident and expensive to have made: that
nothing is sent anywhere, that no account is needed, that the model being
measured is the reader's own, and that somebody other than the participant
verified the run. None of the four is true of Techtree v0.1, and each one is
the kind of sentence that gets written by a person trying to be reassuring
rather than by a person trying to be exact.

So the copy is scanned rather than reviewed. Two layers, because one is not
enough:

*The census.* A guard nobody pointed at the copy guards nothing, so the set of
scanned surfaces is derived rather than listed by hand wherever it can be —
every module under ``cli/``, ``presentation/`` and ``doctor/``, plus every
module anywhere in the package that builds a ``NextAction``, whose labels and
reasons are read by a person and by a host agent. A new command in a new file
joins the scan by existing.

*The phrases.* Some overclaims are literals worth banning outright. Others are
true of Techtree's own uploads and false as a description of a run, and those
are caught semantically: a sweeping "nothing is sent" has to be qualified by a
sentence, in the same block, saying model inference goes to the provider. The
plugin's guard learned the per-sentence half of that lesson the hard way — a
provider named for an unrelated reason qualifies nothing — and this one
tightens the other half, because its documents are longer. The block is the
unit a reader meets: one caveat line, one warning bullet, one paragraph. A
provider sentence three caveats away is not a qualification of this one.

What is scanned from a Python module is what a person can end up reading:
every string literal that is not a docstring, plus the docstrings of the
``*_command`` functions, which Typer prints as ``--help``. Ordinary docstrings
are deliberately absent. They are this repository's design notes, they discuss
the very claims being banned in order to explain why they are banned, and a
guard that could demand an edit to one would be a guard that punishes a module
for documenting itself.

``release/skills/hello-world-starter-v1/SKILL.md`` is deliberately absent for
a different reason. It is founder-written and frozen by digest, decisions 0010
item 2 requires it to say nothing about what it is, and a test that could
demand an edit to it would be a test that could break a release coordinate.

One scan here runs the other way round. Decision 0035 settles what v0.1 *is* —
a proof of concept for a stack of three independent parts — and the danger with
that ruling is not a banned word appearing but the frame quietly going missing,
leaving a front page that says what the software does and lets a reader decide
for themselves what it amounts to. So the surface that says what this release
is has to carry the frame, has to name each of the three parts with the project
that made it, and has to say what the release is pinned to.
"""

from __future__ import annotations

import ast
import io
import re
from pathlib import Path
from typing import Final

import pytest
from rich.console import Console

from techtree.models.campaign import CampaignSpec
from techtree.presentation.build import cost_explanation, cost_summary
from techtree.presentation.models import DerivedCost, UpliftPresentationPayload

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[2]
SOURCE_ROOT: Final = REPOSITORY_ROOT / "src" / "techtree"

#: The founder Skill is frozen by digest and says nothing about itself on
#: purpose. Decisions 0010 item 2, 0012.
EXCLUDED_FROM_SCAN: Final = (
    REPOSITORY_ROOT / "release" / "skills" / "hello-world-starter-v1" / "SKILL.md"
)


# What counts as public copy -------------------------------------------------------


def _module_docstring_ids(tree: ast.Module) -> set[int]:
    """Return the docstrings a reader never sees.

    Every docstring except a command function's: Typer prints those as the
    command's ``--help``, which makes them copy rather than commentary.
    """
    hidden: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            continue
        body = node.body
        if not body or not isinstance(body[0], ast.Expr):
            continue
        first = body[0].value
        if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
            continue
        if isinstance(
            node, ast.FunctionDef | ast.AsyncFunctionDef
        ) and node.name.endswith("_command"):
            continue
        hidden.add(id(first))
    return hidden


def _rendered_units(source: Path) -> list[str]:
    """Return everything a Python module can put in front of a person.

    One entry per string literal, because one string literal is one rendered
    unit: a caveat line, a warning bullet, a message, a help line. Read through
    the parser rather than by regular expression, so that copy written as
    several adjacent literals — which most of it is — is one unit and not
    fragments that each look innocent.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    hidden = _module_docstring_ids(tree)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in hidden
    ]


def _next_action_modules() -> list[Path]:
    """Return every module that builds a ``NextAction``, found rather than listed.

    A next action carries a label and a reason straight to a terminal and to a
    host agent, and they are written wherever the refusal that needs one lives.
    Deriving the list is what keeps a service that grows a new refusal from
    growing an unscanned sentence with it.
    """
    return sorted(
        path
        for path in SOURCE_ROOT.rglob("*.py")
        if "NextAction(" in path.read_text(encoding="utf-8")
    )


def _copy_modules() -> list[Path]:
    """Return every Python module whose strings reach a reader."""
    surfaces = {
        *(SOURCE_ROOT / "presentation").glob("*.py"),
        *(SOURCE_ROOT / "cli").rglob("*.py"),
        *(SOURCE_ROOT / "doctor").glob("*.py"),
        # The draft and comparison warnings. They are built here and rendered
        # by the CLI, so the reader meets them without ever meeting this file.
        SOURCE_ROOT / "skills" / "service.py",
        *_next_action_modules(),
    }
    return sorted(path for path in surfaces if "__pycache__" not in path.parts)


#: The prose a reader meets outside the CLI: this repository's front page, the
#: release directory's own README — what a release owner and every downstream
#: repository read before touching the coordinates — and the uninstall runbook,
#: which is the one document whose whole subject is what Techtree keeps and
#: what it cannot reach.
MARKDOWN_SURFACES: Final[tuple[Path, ...]] = (
    REPOSITORY_ROOT / "README.md",
    REPOSITORY_ROOT / "release" / "README.md",
    REPOSITORY_ROOT / "docs" / "uninstall-and-data-retention.md",
)


def _copy_blocks() -> list[tuple[str, str]]:
    """Return the copy as the blocks a reader actually meets it in.

    A block is the unit a claim and its qualification have to share for the
    qualification to be *nearby* in any sense a reader would recognise: one
    string literal in a module, one paragraph in a document. Scanning whole
    files instead — which is what the plugin's guard does — would let a
    provider sentence in an unrelated caveat excuse an unqualified promise in
    the caveat printed above it.
    """
    blocks: list[tuple[str, str]] = []
    for path in _copy_modules():
        name = path.relative_to(REPOSITORY_ROOT).as_posix()
        blocks.extend((name, unit) for unit in _rendered_units(path))
    for document in MARKDOWN_SURFACES:
        name = document.relative_to(REPOSITORY_ROOT).as_posix()
        text = document.read_text(encoding="utf-8")
        blocks.extend((name, paragraph) for paragraph in re.split(r"\n[ \t]*\n", text))
    return blocks


#: Every rendered block, with the surface it came from.
COPY_BLOCKS: Final[tuple[tuple[str, str], ...]] = tuple(_copy_blocks())


def _public_copy() -> dict[str, str]:
    """Return each surface's whole copy, for the scans that need no locality."""
    copy: dict[str, list[str]] = {}
    for name, block in COPY_BLOCKS:
        copy.setdefault(name, []).append(block)
    return {
        name: "\n".join(blocks)
        for name, blocks in copy.items()
        if "".join(blocks).strip()
    }


PUBLIC_COPY: Final[dict[str, str]] = _public_copy()


# The four boundaries ----------------------------------------------------------------

#: Privacy claims that are false however they are qualified. Decision 0013 s4:
#: push=false stops the Verifiers upload; it does not make remote inference
#: local.
FORBIDDEN_PRIVACY: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "nothing leaves the laptop",
        re.compile(r"nothing\s+leaves\s+(the|your|this)\s+", re.I),
    ),
    ("nothing is sent anywhere", re.compile(r"nothing\s+is\s+sent\s+anywhere", re.I)),
    (
        "fully offline evaluation",
        re.compile(r"(fully|completely|entirely)\s+offline\s+(evaluation|run)", re.I),
    ),
)

#: Sweeping "we send nothing" claims. True of Techtree's own uploads, false as
#: a description of a run, so each one has to be qualified in its own document.
#:
#: "Nothing left" is only the claim when something is left *somewhere*; the
#: bare phrase is ordinary English for "there is no more of it", which is what
#: Doctor says when it has run out of repairs.
NEEDS_PROVIDER_QUALIFICATION: Final[re.Pattern[str]] = re.compile(
    r"nothing\s+(is|was|gets|ever)\s+(uploaded|sent|published|fetched)"
    r"|nothing\s+(?:ever\s+)?leaves\b"
    r"|nothing\s+left\s+(the|your|this)\b"
    r"|(uploads?|sends?|publishes)\s+nothing",
    re.I,
)

#: The nouns that make a sentence a statement about where inference goes.
_INFERENCE_NOUN: Final[re.Pattern[str]] = re.compile(
    r"\b(model\s+inference|model\s+calls?|inference)\b", re.I
)
_PROVIDER_NOUN: Final[re.Pattern[str]] = re.compile(r"\bprovider\b", re.I)


def _sentences(text: str) -> list[str]:
    """Return the document as sentences, with its line wrapping undone."""
    return re.split(r"(?<=[.!?;])\s+", " ".join(text.split()))


def has_provider_qualification(text: str) -> bool:
    """Whether some one sentence says inference goes to the provider.

    One sentence, not one document: a page that mentions a provider somewhere
    for an unrelated reason has not qualified anything, and the plugin's
    version of this guard was fooled by exactly that.
    """
    return any(
        _INFERENCE_NOUN.search(sentence) and _PROVIDER_NOUN.search(sentence)
        for sentence in _sentences(text)
    )


#: A Prime/provider account, an API credential, and network access may all be
#: needed. Only the Techtree-scoped claim is true, so the ban is on the bare
#: noun rather than on one sentence shape: "no account required" and "no
#: network, no account" are the same promise in different words. "Takes no
#: account of" is the English idiom, not the claim.
FORBIDDEN_ACCOUNT: Final[re.Pattern[str]] = re.compile(
    r"(?<!techtree\s)\bno\s+accounts?\b(?!\s+of\b)", re.I
)

#: The Campaign pins ``qwen/qwen3.7-flash``. Decision 0013 s1.3: the subject is
#: a pinned model run under the participant's credentials, and calling it the
#: reader's own blurs it into the host model they chose. The exact phrase is
#: banned; "your model provider" and "your inference credentials" are the
#: honest ways to say whose account pays. Plural-tolerant, so that the banned
#: literal is the same one the plugin and the website repositories ban.
FORBIDDEN_MODEL: Final[re.Pattern[str]] = re.compile(r"\byour\s+own\s+models?\b", re.I)

#: Nobody but the participant attested this execution. Decision 0013 s1.
FORBIDDEN_ATTESTATION: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "Techtree verified the execution",
        re.compile(r"techtree\s+verified\s+the\s+execution", re.I),
    ),
    ("verified by Techtree", re.compile(r"verified\s+by\s+techtree", re.I)),
    ("independently verified", re.compile(r"independently\s+(verified|proven)", re.I)),
    ("trustless proof", re.compile(r"trustless", re.I)),
    ("proof of honest compute", re.compile(r"proof\s+of\s+honest\s+compute", re.I)),
    ("without trusting us", re.compile(r"without\s+trusting\s+us\b", re.I)),
)

#: The forbidden public name for the introductory Climb. Decision 0009.
FORBIDDEN_NAME: Final[re.Pattern[str]] = re.compile(r"HelloWorldBench", re.I)

#: An exact score is not what was calibrated. Decision 0015 s6: the claim is
#: the 20-27/36 band, or "roughly two-thirds of the toy tasks". Either dash
#: spelling of the band counts, which is why the pattern names both.
FORBIDDEN_EXACT_SCORE: Final[re.Pattern[str]] = re.compile(
    r"\bscor(e|es|ed)\s+\d+\b"
    r"|\bsolves?\s+\d+\s+(of|out\s+of)\s+\d+\b"
    r"|\b\d{1,2}\s*/\s*36\b",
    re.I,
)

#: The band itself, removed before the exact-score scan. A check that flagged
#: the honest phrasing for containing the dishonest one would be a check that
#: punishes candour.
PERMITTED_BAND: Final[re.Pattern[str]] = re.compile(
    "\\b20\\s*[-\\u2013]\\s*27\\s*/\\s*36\\b"
)

#: Ticket 637. On this Climb the bar a candidate has to clear is: beat a
#: baseline of zero by any margin at all, on a synthetic toy task family, at
#: proof grade P1, with no publication eligibility. "Accepted" and "met the
#: threshold" are both literally true of that and both read like passing a
#: benchmark, which is the one thing the result is not. What may be said is
#: what was measured — that the Skill improved on this task family, how much of
#: it is still failing, and that none of it is broad-capability evidence.
#:
#: Each pattern bans the claim in the affirmative only. Saying that a candidate
#: did NOT clear the bar the Campaign declared is exactly what the honest copy
#: has to do, and a guard that could not tell the two apart would forbid the
#: sentences it exists to require. That is why the verbs are only ever the ones
#: that assert success — "met", "cleared", "passed" — and never the bare
#: infinitives a negation is built from.
FORBIDDEN_BENCHMARK_VERDICT: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "a bar that was met",
        re.compile(
            r"\b(met|meets|meeting|passed|passes|passing|cleared|clears|clearing"
            r"|reached|reaches|reaching|achieved|achieves|achieving|beat|beats"
            r"|beating)\b[^.]{0,60}\b(threshold|thresholds|bar|standard|standards)\b",
            re.I,
        ),
    ),
    (
        "a verdict word standing in for what was measured",
        re.compile(
            r"\baccepted\b\s*[:.]"
            r"|\b(candidate|skill|result|report)s?\s+(was\s+|were\s+|is\s+|are\s+)?"
            r"accepted\b",
            re.I,
        ),
    ),
    ("benchmark framing", re.compile(r"\bbenchmark(s|ed|ing)?\b", re.I)),
)

#: The other half of ticket 637. Removing the overclaim leaves the headline
#: free to say nothing about what the result does not establish, which is how a
#: reader ends up assuming it anyway. Both channels lead with this line.
NOT_BROAD_CAPABILITY_FRAMING: Final[re.Pattern[str]] = re.compile(
    r"not\s+broad-capability\s+evidence", re.I
)

#: Decisions 0025 and 0029. What a run is held to changed; what it is not held
#: to did not. Since 0029 the declared limits are enforced and the declared
#: maximum spend is a precondition: before a real run starts, the most the
#: comparison can cost under those limits is computed and a Campaign that could
#: amount to more than it declares is refused. What still does not exist is a
#: meter — nothing counts the spend while a run is under way, and nothing ends
#: one part-way through over money. Copy may say what is checked. Copy may not
#: phrase any of it as a running total or a mid-run cut-off, because a reader
#: told a protection exists will believe they have it.
#:
#: Each pattern bans the claim in the affirmative only. Saying that none of
#: this happens is exactly what the honest copy has to do, and a guard that
#: could not tell the two apart would forbid the sentences it exists to
#: require.
FORBIDDEN_COST_PROMISE: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("a cost bound", re.compile(r"\bcost\s+(bound|ceiling|cap)s?\b", re.I)),
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

#: Decisions 0025 and 0029 again, for the clock. ``execution.timeout_seconds``
#: is now handed to the evaluation as the per-episode rollout timeout, so an
#: episode does have an enforced time limit and copy may say so. A *run* is a
#: different question: how long a comparison takes is how long its episodes
#: take, and nothing publishes a finishing time for one. What goes is any
#: sentence that reads as a promise about when a run is over.
FORBIDDEN_TIME_PROMISE: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("the declared 600 seconds", re.compile(r"\b600[\s-]*seconds?\b", re.I)),
    (
        "a stated run duration",
        re.compile(
            r"\b(up\s+to|no\s+more\s+than|at\s+most|within|under|less\s+than)\s+"
            r"\d+\s*(seconds?|minutes?|hours?)\b",
            re.I,
        ),
    ),
    (
        "a time-bounded run",
        re.compile(r"\btime[-\s](bound|bounded|limited|capped|boxed)\b", re.I),
    ),
    ("a run time limit", re.compile(r"\brun\s+(time\s+)?limits?\b", re.I)),
    (
        "a promised finish",
        re.compile(
            r"\b(finish|finishes|complete|completes|end|ends|done)\s+"
            r"(in|within|after)\s+\d+\s*(seconds?|minutes?|hours?)\b",
            re.I,
        ),
    ),
)

#: The other half of the money ban. Removing an overclaim leaves a surface free
#: to say nothing, which is how a reader ends up assuming the protection anyway.
#: The review a person answers before a run starts has to say what does not
#: happen, in the same breath as whatever it says does.
NO_METER_FRAMING: Final[re.Pattern[str]] = re.compile(
    r"nothing\s+keeps\s+a\s+running\s+total", re.I
)
NO_CUT_OFF_FRAMING: Final[re.Pattern[str]] = re.compile(
    r"nothing\s+ends\s+it\s+part-?way\s+through", re.I
)

#: And the half that is now true. A Campaign that declares a maximum is checked
#: against it before anything is spent, so the review says so rather than
#: leaving a person to discover the refusal by being refused.
PRE_RUN_CHECK_FRAMING: Final[re.Pattern[str]] = re.compile(
    r"cannot\s+add\s+up\s+past\s+the\s+\$\d", re.I
)

#: Founder directive, 2026-08-26. What a run actually spends is model tokens on
#: inference, and that is true of somebody answering from their own hardware as
#: much as of somebody on a hosted provider. Saying only that would understate
#: it for most readers, who are on a provider that turns those tokens into a
#: charge. So the surfaces that offer to spend them say where a charge lands as
#: well as what is spent — the same shape as the two bans above: state the true
#: half a reader would otherwise supply for themselves, wrongly.
BILLING_FRAMING: Final[re.Pattern[str]] = re.compile(
    r"provider\s+(that\s+)?charges\s+for\s+tokens", re.I
)


def _released_campaign() -> CampaignSpec:
    """Return the Campaign this build ships, read from the catalog it ships in.

    The review's cost line is checked against the released contract rather than
    an invented one, so a regeneration that changed the declared ceiling would
    have to come back through this guard.
    """
    document = (
        SOURCE_ROOT / "resources" / "catalog" / "campaigns" / "hello-world-climb.json"
    )
    return CampaignSpec.model_validate_json(document.read_text(encoding="utf-8"))


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


# The census ---------------------------------------------------------------------------


def test_the_scan_reads_every_surface_a_person_meets() -> None:
    """A guard nobody pointed at the copy guards nothing."""
    assert set(PUBLIC_COPY) >= {
        "README.md",
        "release/README.md",
        "src/techtree/cli/app.py",
        "src/techtree/cli/commands/run.py",
        "src/techtree/doctor/checks.py",
        "src/techtree/presentation/rich.py",
        "src/techtree/presentation/compact.py",
        "src/techtree/skills/service.py",
        "docs/uninstall-and-data-retention.md",
    }
    assert all(text.strip() for text in PUBLIC_COPY.values())


def test_every_module_that_writes_a_next_action_is_scanned() -> None:
    """Labels and reasons are copy, wherever the refusal that needs one lives."""
    scanned = set(PUBLIC_COPY)

    for path in _next_action_modules():
        assert path.relative_to(REPOSITORY_ROOT).as_posix() in scanned


def test_the_frozen_founder_skill_is_not_scanned() -> None:
    """A test that could demand an edit to it could break a release coordinate."""
    assert EXCLUDED_FROM_SCAN.is_file()
    assert EXCLUDED_FROM_SCAN.relative_to(REPOSITORY_ROOT).as_posix() not in PUBLIC_COPY


def test_a_command_help_string_is_read_and_a_design_note_is_not() -> None:
    """The extraction has to make exactly this distinction, so it is tested.

    ``techtree proof verify``'s summary line is printed by ``--help``. The
    module docstring above it is a design note that discusses the boundaries
    this file polices, and reading it would make the guard fight the
    documentation that explains the guard.
    """
    proof = PUBLIC_COPY["src/techtree/cli/commands/proof.py"]

    assert "Check a local proof, offline, from the bytes it stored." in proof
    assert "Spec section" not in proof


# The scans ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("described", "pattern"),
    FORBIDDEN_PRIVACY,
    ids=[described for described, _ in FORBIDDEN_PRIVACY],
)
def test_no_copy_claims_the_work_is_local(
    described: str, pattern: re.Pattern[str]
) -> None:
    """Decision 0013 s4. Model inference is sent to the provider, always."""
    offenders = _offenders(pattern)

    assert not offenders, f"copy claims {described!r}: {offenders}"


def test_a_claim_that_nothing_is_sent_is_qualified_where_it_is_made() -> None:
    """A sweeping "we send nothing" needs the provider sentence beside it.

    Beside it, not somewhere in the same file: a caveat is printed as its own
    line and read as its own promise.
    """
    unqualified = [
        f"{name}: {sentence.strip()}"
        for name, block in COPY_BLOCKS
        if not has_provider_qualification(block)
        for sentence in _sentences(block)
        if NEEDS_PROVIDER_QUALIFICATION.search(sentence)
    ]

    assert not unqualified, (
        "these say nothing is sent, in a block that never says model "
        f"inference goes to the provider: {unqualified}"
    )


def test_an_unrelated_mention_of_a_provider_does_not_qualify_anything() -> None:
    """The bug the plugin's version of this guard had once."""
    assert not has_provider_qualification(
        "Nothing is uploaded, ever. A model provider may not expose an "
        "immutable revision for the model it serves."
    )
    assert has_provider_qualification(
        "Nothing Techtree holds is uploaded. Model inference still goes to "
        "the model provider you configured."
    )


def test_a_qualification_in_a_neighbouring_block_does_not_travel() -> None:
    """The locality rule, stated as the thing it refuses.

    Two caveats printed one after the other are two promises. A guard that
    read them as one document would let the honest one launder the other, and
    the reader who stops after the first line would have been misled by a
    passing test.
    """
    claim = "Nothing was uploaded."
    qualification = "Model inference was sent to the model provider this run used."

    assert NEEDS_PROVIDER_QUALIFICATION.search(claim)
    assert not has_provider_qualification(claim)
    assert has_provider_qualification(f"{claim} {qualification}")


def test_the_doctor_running_out_of_repairs_is_not_a_privacy_claim() -> None:
    """ "Nothing left to fix" is English, not a promise about the network."""
    assert not NEEDS_PROVIDER_QUALIFICATION.search(
        "Nothing left to fix automatically; each failed check says what it needs."
    )
    assert NEEDS_PROVIDER_QUALIFICATION.search("Nothing left this machine.")


def test_the_offline_proof_check_wording_is_still_allowed() -> None:
    """Decision 0013 s4 bans offline *evaluation*, not the offline proof check.

    Verifying a bundle really does read nothing but the bytes it stored, and
    that is the one place "offline" is the exact word. A guard that took it
    away would trade a true sentence for a vaguer one.
    """
    permitted = (
        "Check a local proof offline, from the bytes the run stored.",
        "local proof verified offline",
        "signature verified offline",
        "It checks offline, from the bytes the run stored.",
        "an offline-verifiable evidence bundle",
    )

    for sentence in permitted:
        for described, pattern in FORBIDDEN_PRIVACY:
            assert not pattern.search(sentence), (described, sentence)
        assert not NEEDS_PROVIDER_QUALIFICATION.search(sentence), sentence


def test_no_copy_says_no_account_is_required() -> None:
    """Decision 0013 s2. Only the Techtree-scoped claim is true."""
    offenders = _offenders(FORBIDDEN_ACCOUNT)

    assert not offenders, f"copy overclaims about accounts: {offenders}"


def test_the_techtree_scoped_account_claim_is_still_allowed() -> None:
    """The guard must permit the sentence the release is meant to use, and

    must catch the paraphrases that promise the same thing without the word
    "required" — which is how the claim actually gets written.
    """
    assert not FORBIDDEN_ACCOUNT.search("No Techtree account is required.")
    assert not FORBIDDEN_ACCOUNT.search("It takes no account of the second run.")

    for refused in (
        "No account is required.",
        "no account needed",
        "no network, no account, and no state of its own",
        "There are no accounts to make.",
    ):
        assert FORBIDDEN_ACCOUNT.search(refused), refused


def test_no_copy_calls_the_subject_the_readers_own_model() -> None:
    """Decision 0013 s1.3. The Campaign pins the subject model; it is not theirs."""
    offenders = _offenders(FORBIDDEN_MODEL)

    assert not offenders, f"copy blurs the pinned subject model: {offenders}"


def test_the_honest_model_wording_is_still_allowed() -> None:
    """Whose credentials pay is a true and useful thing to say."""
    for permitted in (
        "using your own inference credentials",
        "the model provider you configured",
        "a pinned subject model runs twice under the same configuration",
    ):
        assert not FORBIDDEN_MODEL.search(permitted), permitted

    assert FORBIDDEN_MODEL.search("bring your own model")


@pytest.mark.parametrize(
    ("described", "pattern"),
    FORBIDDEN_ATTESTATION,
    ids=[described for described, _ in FORBIDDEN_ATTESTATION],
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
        "Nobody else has verified that this run happened as described.",
    )

    for sentence in permitted:
        for described, pattern in FORBIDDEN_ATTESTATION:
            assert not pattern.search(sentence), (described, sentence)


def test_no_copy_uses_the_forbidden_climb_name() -> None:
    """Decision 0009: the public name is Techtree Hello World."""
    assert not _offenders(FORBIDDEN_NAME)


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
    """Decision 0025. The declared timeout reaches no evaluation and ends nothing."""
    offenders = _offenders(pattern)

    assert not offenders, f"copy promises {described!r}: {offenders}"


def test_the_review_says_what_is_checked_and_what_is_not() -> None:
    """The line a person answers has to carry both halves of the truth.

    A declared maximum with no disclaimer beside it reads as a meter. Whichever
    branch the Campaign lands in, the sentence says that nothing keeps a
    running total and nothing ends the run part-way through, and it says where
    a charge for the tokens lands; where there is a maximum, it also says that
    the run is refused if the enforced limits could amount to more than it.
    """
    from techtree.cli.commands.climb import _cost_line

    released = _released_campaign()
    undeclared = released.model_copy(
        update={"budgets": released.budgets.model_copy(update={"maximum_usd": None})}
    )

    for campaign in (released, undeclared):
        line = _cost_line(campaign)

        assert NO_METER_FRAMING.search(line), line
        assert NO_CUT_OFF_FRAMING.search(line), line
        assert BILLING_FRAMING.search(line), line
        for described, pattern in FORBIDDEN_COST_PROMISE + FORBIDDEN_TIME_PROMISE:
            assert not pattern.search(line), (described, line)

    released_line = _cost_line(released)
    assert PRE_RUN_CHECK_FRAMING.search(released_line), released_line
    assert "$2.50 maximum it declares" in released_line
    assert not PRE_RUN_CHECK_FRAMING.search(_cost_line(undeclared))


def test_the_billing_guard_catches_a_review_that_only_names_the_tokens() -> None:
    """Founder directive, 2026-08-26. The token frame alone understates it.

    A run spends model tokens on inference whoever is answering, which is why
    the copy says that and not "money". For most readers those tokens arrive as
    a charge from a provider, and a review that stopped at the tokens would let
    them find that out afterwards. So the guard has to fail exactly the wording
    that leaves the charge unsaid, and pass the wording that names it.
    """
    silent = (
        "This run spends model tokens on inference.",
        "Nothing keeps a running total while the run is under way.",
        "Each episode has enforced turn, token, and time limits.",
        "The tokens go to the model provider you configured.",
    )
    honest = (
        "A provider that charges for tokens bills the episodes above to your "
        "own account, and a model you run yourself sends no bill.",
        "If that provider charges for tokens, what you pay is whatever it charges.",
    )

    for sentence in silent:
        assert not BILLING_FRAMING.search(sentence), sentence
    for sentence in honest:
        assert BILLING_FRAMING.search(sentence), sentence


def test_the_honest_money_and_clock_wording_is_still_allowed() -> None:
    """The guards must not forbid the sentences they exist to require."""
    permitted = (
        "Before anything starts, Techtree checks that this Campaign's enforced "
        "per-episode limits cannot add up past the $2.50 maximum it declares, "
        "and refuses to run it if they could.",
        "Each episode has enforced turn, token, and time limits.",
        "Nothing keeps a running total while the run is under way and nothing "
        "ends it part-way through.",
        "A provider that charges for tokens bills the episodes above to your "
        "own account, and a model you run yourself sends no bill.",
        "This run evaluates the agent for real and spends model tokens on "
        "inference with prime. If that provider charges for tokens, what you "
        "pay is whatever it charges; a model you run yourself sends no bill.",
        "This Campaign declares no maximum.",
        "The cost shown is an estimate. It is not a figure the provider "
        "reported and it is not what you were charged.",
        "The run continues after this command returns.",
    )

    for sentence in permitted:
        for described, pattern in FORBIDDEN_COST_PROMISE + FORBIDDEN_TIME_PROMISE:
            assert not pattern.search(sentence), (described, sentence)


def test_the_money_and_clock_guards_catch_what_they_are_for() -> None:
    """The claims decision 0025 removed, in the words they were written in."""
    refused = (
        "It shows you what this costs and what it changes.",
        "how many tasks it runs, its cost bound, its proof grade",
        "the episode and budget estimate",
        "review the Skill-only change and the estimated cost",
        "The run aborts when it goes over budget.",
        "It will never cost more than the ceiling.",
        "Each run may take up to 600 seconds.",
        "Every run is time-bounded.",
        "There is a run limit of ten minutes.",
        "It finishes within 600 seconds.",
    )

    for sentence in refused:
        assert any(
            pattern.search(sentence)
            for _, pattern in FORBIDDEN_COST_PROMISE + FORBIDDEN_TIME_PROMISE
        ), sentence


@pytest.mark.parametrize(
    ("described", "pattern"),
    FORBIDDEN_BENCHMARK_VERDICT,
    ids=[described for described, _ in FORBIDDEN_BENCHMARK_VERDICT],
)
def test_no_copy_frames_the_result_as_a_benchmark_that_was_passed(
    described: str, pattern: re.Pattern[str]
) -> None:
    """Ticket 637. The bar is a baseline of zero, beaten by any margin at all."""
    offenders = _offenders(pattern)

    assert not offenders, f"copy claims {described!r}: {offenders}"


def test_the_result_says_what_it_does_not_establish_in_the_lines_that_lead() -> None:
    """Ticket 637. Removing an overclaim is only half of the fix.

    Both channels are rendered from one payload and checked as a reader meets
    them, because the line has to be at the top rather than merely present
    somewhere in the module the guard above scans.
    """
    from techtree.presentation.compact import render_uplift_markdown
    from techtree.presentation.rich import render_uplift_console

    payload = _generated_payload()
    assert payload.decision == "accepted"

    output = io.StringIO()
    render_uplift_console(payload, Console(file=output, width=100, no_color=True))
    terminal = output.getvalue()
    gateway = render_uplift_markdown(payload)

    for text in (terminal, gateway):
        assert NOT_BROAD_CAPABILITY_FRAMING.search(text), text
        for described, pattern in FORBIDDEN_BENCHMARK_VERDICT:
            assert not pattern.search(text), (described, text)
    # In the opening block of each, not in a footer a reader scrolls past.
    for text in (terminal, gateway):
        head = "\n".join(text.splitlines()[:8])
        assert NOT_BROAD_CAPABILITY_FRAMING.search(head), head


def test_the_honest_verdict_wording_is_still_allowed() -> None:
    """The guard must not forbid the sentences it exists to require."""
    permitted = (
        "Improved on this development task family",
        "Did not clear the bar this Climb declared",
        "Not broad-capability evidence",
        "Solved 24 of 36 · 12 still failing · 0 regressions",
        "A rejected candidate is a measurement, not a failed run: this Skill "
        "did not meet the threshold the Campaign declared in advance.",
        "Global options are accepted anywhere on the command line.",
        "The data policy is shown and accepted again before the second run starts.",
    )

    for sentence in permitted:
        for described, pattern in FORBIDDEN_BENCHMARK_VERDICT:
            assert not pattern.search(sentence), (described, sentence)


def test_the_benchmark_guard_catches_what_it_is_for() -> None:
    """The claims ticket 637 removed, in the words they were written in."""
    refused = (
        "Accepted: the candidate met the threshold this Campaign declared.",
        "The Skill met the Campaign's threshold",
        "The candidate cleared the bar the Campaign declared.",
        "The Skill passed the benchmark.",
        "The candidate was accepted.",
        "It reaches the standard this Campaign set.",
    )

    for sentence in refused:
        assert any(
            pattern.search(sentence) for _, pattern in FORBIDDEN_BENCHMARK_VERDICT
        ), sentence


def test_the_band_wording_is_still_allowed() -> None:
    """The guard must permit the phrasings decision 0015 s6 fixed."""
    for permitted in (
        "calibrated to the 20–27/36 band",
        "calibrated to the 20-27/36 band",
        "solves roughly two-thirds of the toy tasks; individual runs may vary",
    ):
        assert not FORBIDDEN_EXACT_SCORE.search(PERMITTED_BAND.sub("", permitted))

    for refused in ("the starter Skill scores 24", "it reaches 24/36"):
        assert FORBIDDEN_EXACT_SCORE.search(PERMITTED_BAND.sub("", refused))


# What this release is ----------------------------------------------------------------

#: Decision 0035. Every other scan here removes a claim. This one requires one,
#: because the honest name for v0.1 is the frame around everything else it says:
#: a proof of concept for a stack of three independent parts, which claims less
#: than the copy already claimed and settles several boundaries at once.
PROOF_OF_CONCEPT_FRAME: Final[re.Pattern[str]] = re.compile(
    r"\bproof[\s-]of[\s-]concept\b", re.I
)

#: Two of the three parts are somebody else's work, so each is named with the
#: project that made it. A proof of concept that reads as though we built the
#: whole stack is the same class of overclaim as any other.
STACK_ATTRIBUTION: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "Prime Intellect's Verifiers, the evaluation engine",
        re.compile(r"Prime\s+Intellect[’']s\s+Verifiers", re.I),
    ),
    (
        "Nous Research's Hermes, the agent host",
        re.compile(r"Nous\s+Research[’']s\s+Hermes", re.I),
    ),
    (
        "Techtree, the campaign kernel and evidence layer",
        re.compile(r"Techtree\s+as\s+the\s+campaign\s+kernel", re.I),
    ),
)

#: "Stack" is the word that tells a reader where the seams are. An engine, a
#: host and a container are each pinned, and the release is only as reproducible
#: as those pins. That is a strength stated plainly rather than a weakness
#: confessed, and a frame that leaves it out is only half the ruling.
STACK_SEAMS: Final[re.Pattern[str]] = re.compile(
    r"only\s+as\s+reproducible\s+as\s+those\s+pins", re.I
)

#: The surface that says what this release is. Decision 0035 names the
#: repository front pages among the places the frame applies; this repository
#: has one, and it is already scanned by everything above.
RELEASE_CLAIM_SURFACES: Final[tuple[str, ...]] = ("README.md",)


def _frame_faults(text: str) -> list[str]:
    """Return what a surface still owes a reader about what this release is."""
    missing = []
    if not PROOF_OF_CONCEPT_FRAME.search(text):
        missing.append("the proof-of-concept frame")
    missing.extend(
        described
        for described, pattern in STACK_ATTRIBUTION
        if not pattern.search(text)
    )
    if not STACK_SEAMS.search(text):
        missing.append("what the release is pinned to")
    return missing


@pytest.mark.parametrize("surface", RELEASE_CLAIM_SURFACES)
def test_a_surface_that_says_what_this_release_is_carries_the_frame(
    surface: str,
) -> None:
    """Decision 0035. Dropping any part of it fails."""
    missing = _frame_faults(PUBLIC_COPY[surface])

    assert not missing, f"{surface} does not carry {missing}"


def test_the_frame_guard_catches_what_it_is_for() -> None:
    """The copy that stood before the ruling, and each half-done version of it."""
    refused = (
        # What the front page said before decision 0035: what the software
        # does, and nothing about what the release amounts to.
        "Techtree Climb v0.1 is a toy, synthetic demonstration of Skill uplift.",
        # The frame with the parts passed off as ours.
        "Techtree Climb v0.1 is a proof of concept for a stack of three parts: "
        "our evaluation engine, our agent host, and our evidence layer. The "
        "release is only as reproducible as those pins.",
        # The frame and the attribution, with the seams left for the reader.
        "Techtree Climb v0.1 is a proof of concept for a stack of three "
        "independent parts: Prime Intellect’s Verifiers as the evaluation "
        "engine, Nous Research’s Hermes as the agent host, and Techtree as "
        "the campaign kernel and evidence layer.",
    )

    for text in refused:
        assert _frame_faults(text), text


# The publication terms ---------------------------------------------------------------

#: Ticket q0l. A DataPolicy's publication terms describe a result that has been
#: published: entering a Climb requires releasing the candidate Skill, and the
#: uplift report is public. Shown beside raw-episode terms that prohibit upload
#: outright, they read as a plan to publish somebody's Skill and their numbers,
#: and two readers stopped and refused to start a run over exactly that.
#: Nothing in this build can publish anything — there is no upload path, no
#: result is publication-eligible, and every proof is graded development_only.
#: So the terms stay exactly as the policy states them, and the plain truth is
#: shown with them.
PUBLICATION_TERMS_FRAMING: Final[re.Pattern[str]] = re.compile(
    r"nothing\s+is\s+published\s+from\s+this\s+build", re.I
)

#: What makes a function a place where those terms are put in front of a
#: person: the row that renders the release permission, or the rights summary
#: that spells the terms out in sentences. Derived rather than listed, so a new
#: review surface joins this guard by existing.
PUBLICATION_TERM_MARKERS: Final[tuple[str, ...]] = (
    '"Public release"',
    "policy_acceptance.summary",
)


def _functions_showing_publication_terms() -> list[tuple[str, str]]:
    """Return every CLI function that shows a DataPolicy's publication terms."""
    found: list[tuple[str, str]] = []
    for path in sorted((SOURCE_ROOT / "cli").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            segment = ast.get_source_segment(text, node) or ""
            if any(marker in segment for marker in PUBLICATION_TERM_MARKERS):
                name = f"{path.relative_to(REPOSITORY_ROOT).as_posix()}:{node.name}"
                found.append((name, segment))
    return found


def test_the_publication_terms_are_never_shown_without_their_plain_meaning() -> None:
    """Ticket q0l. The terms describe a published result; this build has none.

    Derived, not listed: any function that renders the release permission or
    prints the rights summary is a place a person reads the terms, and every
    one of them has to print the line that says what they mean here.
    """
    sites = _functions_showing_publication_terms()
    names = {name for name, _ in sites}

    assert names >= {
        "src/techtree/cli/commands/climb.py:approve_run",
        "src/techtree/cli/commands/climb.py:_render_show",
        "src/techtree/cli/commands/climb.py:_render_prepare",
        "src/techtree/cli/commands/uplift.py:_render_prepare",
    }
    missing = [
        name for name, segment in sites if "PUBLICATION_TERMS_LINE" not in segment
    ]
    assert not missing, (
        f"these show the publication terms and not what they mean: {missing}"
    )


def test_the_publication_truth_says_where_model_calls_still_go() -> None:
    """Decision 0013 s4. "It stays here" is heard as "nothing goes anywhere"."""
    from techtree.cli.commands.climb import PUBLICATION_TERMS_LINE

    assert PUBLICATION_TERMS_FRAMING.search(PUBLICATION_TERMS_LINE)
    assert has_provider_qualification(PUBLICATION_TERMS_LINE)
    for described, pattern in FORBIDDEN_PRIVACY:
        assert not pattern.search(PUBLICATION_TERMS_LINE), described


def test_the_publication_guard_catches_a_review_that_only_states_the_terms() -> None:
    """The claim the two readers met, in the words they met it in."""
    assert not PUBLICATION_TERMS_FRAMING.search(
        "Public release required in order to enter this Climb. "
        "The uplift report is published."
    )


# The money a result reports ----------------------------------------------------------

#: A figure Techtree worked out from recorded tokens is not a bill, and the
#: sentence that says so has to be in the same breath as the number. Ticket nom
#: put a dollar figure in front of a reader for the first time; these are the
#: words that would make it read as one the provider charged.
FORBIDDEN_BILLED: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "a figure the reader was charged",
        re.compile(
            r"\b(you\s+(were\s+charged|paid|owe)|what\s+you\s+(paid|were\s+charged)"
            r"|the\s+provider\s+charged\s+you|your\s+bill\s+(is|was)\s+\$)",
            re.I,
        ),
    ),
    (
        "a total the run kept",
        re.compile(r"\b(running\s+total|total\s+so\s+far|spent\s+so\s+far)\b", re.I),
    ),
)

#: The other half. Removing the overclaim leaves a number free to be read as a
#: bill, so a derived figure states what it is and whose number the real one is.
DERIVED_COST_FRAMING: Final[re.Pattern[str]] = re.compile(
    r"worked\s+out\s+here,\s+not\s+billed", re.I
)
PROVIDER_BILL_FRAMING: Final[re.Pattern[str]] = re.compile(
    r"your\s+provider'?s\s+bill\s+is\s+what\s+you\s+actually\s+pay", re.I
)


def _dollar_formatting_functions() -> set[str]:
    """Return every presentation function that puts a dollar sign on a number.

    Derived rather than listed, like the rest of this file: a second place that
    formats money would be a second place a figure could be shown without the
    sentence that says what kind of figure it is, and it joins this guard by
    existing.
    """
    found: set[str] = set()
    for path in sorted((SOURCE_ROOT / "presentation").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        hidden = _module_docstring_ids(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            drawn = [
                inner.value
                for inner in ast.walk(node)
                if isinstance(inner, ast.Constant)
                and isinstance(inner.value, str)
                and id(inner) not in hidden
            ]
            if any("$" in unit for unit in drawn):
                found.add(f"{path.relative_to(REPOSITORY_ROOT).as_posix()}:{node.name}")
    return found


def _generated_payload() -> UpliftPresentationPayload:
    """Return the payload the golden builder produces from real evidence."""
    golden = REPOSITORY_ROOT / "tests" / "golden" / "presentation-payload.json"
    return UpliftPresentationPayload.model_validate_json(
        golden.read_text(encoding="utf-8")
    )


def _derived_payload() -> UpliftPresentationPayload:
    """Return that payload with a worked-out cost figure on it."""
    return _generated_payload().model_copy(
        update={
            "cost_unavailable_reason": None,
            "derived_cost": DerivedCost(
                usd=0.1809,
                input_tokens=5_612_192,
                output_tokens=96_583,
                cached_input_tokens=2_244_480,
                prices_name_a_cached_rate=False,
                model_id="qwen/qwen3.7-flash",
                input_usd_per_mtok=0.03,
                output_usd_per_mtok=0.13,
                prices_recorded_on="2026-08-20",
            ),
        }
    )


def test_every_place_that_formats_money_is_covered_by_this_guard() -> None:
    """A guard nobody pointed at the money guards no money."""
    assert _dollar_formatting_functions() == {
        "src/techtree/presentation/build.py:cost_summary"
    }


def test_a_worked_out_cost_never_reads_as_one_the_provider_billed() -> None:
    """Ticket nom. The figure and what kind of figure it is travel together."""
    payload = _derived_payload()
    summary = cost_summary(payload)
    explanation = " ".join(cost_explanation(payload))

    assert DERIVED_COST_FRAMING.search(summary), summary
    assert PROVIDER_BILL_FRAMING.search(explanation), explanation
    for described, pattern in FORBIDDEN_BILLED:
        assert not pattern.search(f"{summary} {explanation}"), described
    for described, pattern in FORBIDDEN_COST_PROMISE + FORBIDDEN_TIME_PROMISE:
        assert not pattern.search(f"{summary} {explanation}"), described


def test_a_worked_out_cost_says_what_it_was_worked_out_from() -> None:
    """Ticket nom. A number nobody can check is a number nobody should trust."""
    explanation = " ".join(cost_explanation(_derived_payload()))

    assert "5,612,192 input and 96,583 output tokens" in explanation
    assert "the prices this release recorded" in explanation
    # The unstated cached rate, said out loud rather than assumed away.
    assert "2,244,480" in explanation
    assert "on the high side" in explanation


def test_a_cost_that_cannot_be_worked_out_names_what_is_missing() -> None:
    """Ticket nom. Printing nothing is what sent the founder to the raw record."""
    payload = _generated_payload()

    assert payload.derived_cost is None
    assert cost_summary(payload) == "unavailable"
    assert cost_explanation(payload) == [payload.cost_unavailable_reason]
    assert "recorded no provider prices" in str(payload.cost_unavailable_reason)


def test_the_billed_guard_catches_what_it_is_for() -> None:
    """The sentences that would turn a computed figure into a charge."""
    for refused in (
        "About $0.18, which is what you were charged.",
        "This is what you paid your provider.",
        "The provider charged you $0.18 for this comparison.",
        "The running total for this run is $0.18.",
    ):
        assert any(pattern.search(refused) for _, pattern in FORBIDDEN_BILLED), refused
