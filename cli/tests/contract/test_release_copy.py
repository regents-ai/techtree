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
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

import pytest

from techtree.models.campaign import CampaignSpec

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

#: Decision 0025. The Campaign declares a maximum spend and a per-episode
#: timeout, and both are contract values that nothing holds a run to: no code
#: works out what a run will come to before it starts, none watches the
#: spending while it runs, and none ends a run when the declared time is up.
#: Copy may state a declared figure and say that it is declared. Copy may not
#: phrase one as a meter or a cut-off, because a reader told a protection
#: exists will believe they have it.
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

#: Decision 0025 again, for the clock. ``execution.timeout_seconds`` is a
#: declared value the evaluation never receives, so a run has no finishing
#: time anybody can state. The field itself stays: it is protocol, it is
#: compared between the two sides, and the certified derivation carried it.
#: What goes is any sentence that reads as a promise about the clock.
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
    ("a run time limit", re.compile(r"\b(time|run|episode)\s+limits?\b", re.I)),
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
#: happen, in the same breath as the declared figure.
NO_PRICE_FRAMING: Final[re.Pattern[str]] = re.compile(
    r"nothing\s+here\s+works\s+out\s+what\s+the\s+run\s+will\s+come\s+to", re.I
)
NO_CUT_OFF_FRAMING: Final[re.Pattern[str]] = re.compile(
    r"nothing\s+stops\s+(it|the\s+run)", re.I
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


def test_the_review_says_the_declared_limit_is_only_declared() -> None:
    """The line a person answers has to carry both halves of the truth.

    A declared ceiling with no disclaimer beside it reads as a cap. Whichever
    branch the Campaign lands in, the sentence says the figure is declared and
    says that nothing works it out first and nothing stops the run over it.
    """
    from techtree.cli.commands.climb import _cost_line

    released = _released_campaign()
    undeclared = released.model_copy(
        update={"budgets": released.budgets.model_copy(update={"maximum_usd": None})}
    )

    for campaign in (released, undeclared):
        line = _cost_line(campaign)

        assert NO_PRICE_FRAMING.search(line), line
        assert NO_CUT_OFF_FRAMING.search(line), line
        for described, pattern in FORBIDDEN_COST_PROMISE + FORBIDDEN_TIME_PROMISE:
            assert not pattern.search(line), (described, line)

    assert "declares a limit of $1.00" in _cost_line(released)


def test_the_honest_money_and_clock_wording_is_still_allowed() -> None:
    """The guards must not forbid the sentences they exist to require."""
    permitted = (
        "The Campaign declares a limit of $1.00 for this comparison.",
        "That figure is a declared limit and nothing more.",
        "nothing here works out what the run will come to first",
        "nothing stops it if it goes past",
        "What you pay is whatever your model provider charges for the episodes above.",
        "This comparison declares no spending limit.",
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
