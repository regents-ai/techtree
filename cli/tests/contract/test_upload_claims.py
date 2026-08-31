"""What may be said about uploading, on every surface that says it.

Decisions 0038, ticket techtree-python-9ar.

Until 2026-08-27 this repository could say, truthfully and everywhere, that
nothing is uploaded: there was no route, no credential and no server, and the
website answered every mutating method with 405. ``techtree publish`` changed
all three of those at once, and the sentences did not change with them.

They did not change because nothing was holding them. The copy guard in
``test_release_copy.py`` scans the CLI's own strings, and it caught the two
lines that live there — but the rendered result caveat, the verification
message, the local-comparison warnings and every Markdown document in ``docs/``
were outside it. Four of them were still promising, in the present tense, that
there is no upload path. A claim that goes stale unnoticed is a claim nothing
was holding, so this file holds them.

*What is scanned.* The strings a person reads out of a result or a proof check,
and the documents somebody reads before they trust either. Frozen material is
deliberately absent for the same reason it always is: ``docs/spec/`` and
``docs/release/`` are records of what was true when they were written, and
``docs/decisions/`` is the authority a change like this one is recorded in
rather than a surface a claim is edited on. Editing history to agree with the
present is the opposite of what an evidence product should do.

*What is banned.* Four sentences, each of which was true and is now false. They
are banned in the affirmative only: saying that publishing exists and is a
person's own choice is the honest copy, and a guard that could not tell the two
apart would forbid the sentences it exists to require.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

import pytest

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[2]
DOCS_ROOT: Final = REPOSITORY_ROOT / "docs"

#: Directories whose documents are records rather than claims. A record says
#: what was true on the day it was written and is not edited afterwards.
FROZEN: Final[tuple[str, ...]] = ("spec", "release", "decisions", "plan", "assets")

#: The handoff and ticket dumps are transcripts of work in progress, kept as
#: they were handed over. They are named individually rather than by directory
#: because they sit beside the living documents.
FROZEN_DOCUMENTS: Final[tuple[str, ...]] = (
    "handoff-v0.1-tickets.md",
    "v0.1-remaining-tickets.md",
    "wp6-handoff.md",
    "verifiers-eval.md",
    "verifiers-pin.md",
    "verifiers-pin-0.3.1.md",
)


def _live_markdown() -> dict[str, str]:
    """Return every document a reader is expected to act on today."""
    documents = {"README.md": (REPOSITORY_ROOT / "README.md").read_text("utf-8")}
    for path in sorted(DOCS_ROOT.rglob("*.md")):
        relative = path.relative_to(DOCS_ROOT)
        if relative.parts[0] in FROZEN or relative.as_posix() in FROZEN_DOCUMENTS:
            continue
        documents[f"docs/{relative.as_posix()}"] = path.read_text("utf-8")
    return documents


LIVE_MARKDOWN: Final[dict[str, str]] = _live_markdown()


#: The rendered sentences that are not in any document: what a result carries,
#: what a proof check reports, and what a local comparison warns about. Each
#: was outside every existing scan.
def _rendered_claims() -> dict[str, str]:
    from techtree.cli.commands.climb import (
        PUBLICATION_STEP_LINE,
        PUBLICATION_TERMS_LINE,
    )
    from techtree.cli.commands.setup import LOCAL_SIGNING_KEY_NOTICE

    return {
        "climb.py:PUBLICATION_STEP_LINE": PUBLICATION_STEP_LINE,
        "climb.py:PUBLICATION_TERMS_LINE": PUBLICATION_TERMS_LINE,
        "setup.py:LOCAL_SIGNING_KEY_NOTICE": LOCAL_SIGNING_KEY_NOTICE,
        "presentation/build.py:no_server_upload": _caveat_text("no_server_upload"),
        "receipts/verify.py:public_publication": _verification_detail(
            "public_publication"
        ),
        "skills/service.py:_replacement_warnings": "\n".join(_replacement_warnings()),
    }


def _caveat_text(code: str) -> str:
    """Return one presentation caveat's words.

    Read out of the source rather than rendered, because rendering one needs a
    finished run and what is being checked is a sentence rather than a
    computation. The parser is what reads it: a caveat is written as half a
    dozen adjacent string literals, and only the parser joins them back into
    the sentence a person actually sees.
    """
    return _keyword_text(
        REPOSITORY_ROOT / "src" / "techtree" / "presentation" / "build.py",
        selector="code",
        identifier=code,
        wanted="text",
    )


def _verification_detail(identifier: str) -> str:
    """Return one verification message's words, the same way."""
    return _keyword_text(
        REPOSITORY_ROOT / "src" / "techtree" / "receipts" / "verify.py",
        selector="id",
        identifier=identifier,
        wanted="detail",
    )


def _keyword_text(path: Path, *, selector: str, identifier: str, wanted: str) -> str:
    """Return the ``wanted`` string of the one call whose ``selector`` matches."""
    tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        keywords = {
            keyword.arg: keyword.value
            for keyword in node.keywords
            if keyword.arg is not None
        }
        chosen = keywords.get(selector)
        if not isinstance(chosen, ast.Constant) or chosen.value != identifier:
            continue
        text = keywords.get(wanted)
        if isinstance(text, ast.Constant) and isinstance(text.value, str):
            return text.value
    raise AssertionError(
        f"{path.name} has no {selector}={identifier!r} with a {wanted}"
    )


def _replacement_warnings() -> list[str]:
    """Return the warnings a local Skill-against-Skill comparison carries."""
    path = REPOSITORY_ROOT / "src" / "techtree" / "skills" / "service.py"
    tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    body = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_replacement_warnings"
    )
    return [
        node.value
        for node in ast.walk(body)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


RENDERED_CLAIMS: Final[dict[str, str]] = _rendered_claims()

#: The four sentences that stopped being true on 2026-08-27.
STALE_UPLOAD_CLAIMS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "there is no route to publish through",
        re.compile(
            r"\bno\s+(ingest|upload|publication)\s+(route|path|endpoint)s?\b", re.I
        ),
    ),
    (
        "the website is read-only",
        re.compile(r"\bread[-\s]only\s+(web)?site\b", re.I),
    ),
    (
        "the website accepts nothing",
        re.compile(
            r"never\s+receives\s+anything"
            r"|receives?\s+no\s+(proof|submission|result)"
            r"|accepts?\s+nothing",
            re.I,
        ),
    ),
    (
        "nothing is uploaded, full stop",
        re.compile(
            r"nothing\s+uploads\b(?!\s+unless)"
            r"|nothing\s+(is|was|gets|ever)\s+uploaded\b(?!\s+unless)"
            r"|uploads?\s+nothing\b(?!\s+unless)"
            r"|nothing\s+is\s+published\s+from\s+this\s+build",
            re.I,
        ),
    ),
)


def _offenders(surfaces: dict[str, str], pattern: re.Pattern[str]) -> list[str]:
    found = []
    for name, text in surfaces.items():
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            found.append(f"{name}:{line}: {match.group(0)!r}")
    return found


# The census ---------------------------------------------------------------------


def test_the_scan_reads_the_documents_a_reader_acts_on() -> None:
    """A guard nobody pointed at a document guards no document."""
    assert set(LIVE_MARKDOWN) >= {
        "README.md",
        "docs/product-architecture.md",
        "docs/agent-handoff.md",
        "docs/protocol-v1alpha1.md",
        "docs/uninstall-and-data-retention.md",
    }
    assert not any(name.startswith("docs/spec/") for name in LIVE_MARKDOWN)
    assert not any(name.startswith("docs/decisions/") for name in LIVE_MARKDOWN)


def test_the_scan_reads_the_sentences_that_are_in_no_document() -> None:
    """The four that had no guard at all, which is why they went stale."""
    assert set(RENDERED_CLAIMS) == {
        "climb.py:PUBLICATION_STEP_LINE",
        "climb.py:PUBLICATION_TERMS_LINE",
        "setup.py:LOCAL_SIGNING_KEY_NOTICE",
        "presentation/build.py:no_server_upload",
        "receipts/verify.py:public_publication",
        "skills/service.py:_replacement_warnings",
    }
    assert all(text.strip() for text in RENDERED_CLAIMS.values())


# The scans ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("described", "pattern"),
    STALE_UPLOAD_CLAIMS,
    ids=lambda value: getattr(value, "pattern", value),
)
def test_no_living_document_still_says_it(
    described: str, pattern: re.Pattern[str]
) -> None:
    offenders = _offenders(LIVE_MARKDOWN, pattern)

    assert not offenders, f"a document still claims {described}: {offenders}"


@pytest.mark.parametrize(
    ("described", "pattern"),
    STALE_UPLOAD_CLAIMS,
    ids=lambda value: getattr(value, "pattern", value),
)
def test_no_rendered_sentence_still_says_it(
    described: str, pattern: re.Pattern[str]
) -> None:
    offenders = _offenders(RENDERED_CLAIMS, pattern)

    assert not offenders, f"a rendered sentence still claims {described}: {offenders}"


def test_each_rewritten_sentence_says_the_thing_that_replaced_the_promise() -> None:
    """Banning the old wording leaves a surface free to say nothing at all.

    That is how a promise gets deleted and the reader still walks away
    expecting one, so each of these has to carry the fact the ban removed:
    who decides, and what the decision sends.
    """
    required = {
        "climb.py:PUBLICATION_STEP_LINE": ("separate step", "never the episodes"),
        "climb.py:PUBLICATION_TERMS_LINE": (
            "unless you publish a finished run yourself",
            "never the episodes",
        ),
        "setup.py:LOCAL_SIGNING_KEY_NOTICE": (
            "The private half never leaves the key directory.",
            "The public half travels inside the proofs it signs",
        ),
        "presentation/build.py:no_server_upload": (
            "never its episodes",
            "unless you publish this run yourself",
        ),
        "receipts/verify.py:public_publication": (
            "sealed before anybody could have been asked",
            "not a statement about whether the run was published afterwards",
        ),
        "skills/service.py:_replacement_warnings": (
            "unless you publish this run yourself",
            "never the episodes",
        ),
    }

    missing = [
        f"{name}: {phrase!r}"
        for name, phrases in required.items()
        for phrase in phrases
        if phrase not in RENDERED_CLAIMS[name]
    ]

    assert not missing, f"these lost the fact that replaced the promise: {missing}"


def test_the_guard_catches_every_sentence_it_was_written_for() -> None:
    """The four, in the exact words they were found in on 2026-08-27."""
    found = {
        "no ingest route": "The website is read-only and has no ingest route at all.",
        "read-only website": "techtree-ash — the read-only website (Elixir/Phoenix).",
        "never receives anything": (
            "It serves content-addressed release records over GET only and "
            "never receives anything."
        ),
        "nothing uploads": (
            "**Nothing uploads.** No receipt, episode, trace, proof, or Skill "
            "proposal leaves the machine."
        ),
        "nothing is published from this build": (
            "Nothing is published from this build: your Skill, the episodes "
            "and the report stay on this machine."
        ),
    }

    for name, sentence in found.items():
        assert any(pattern.search(sentence) for _, pattern in STALE_UPLOAD_CLAIMS), name


def test_the_guard_leaves_the_true_sentences_alone() -> None:
    """The replacements, which say more than the promise they replaced."""
    true_now = (
        "Nothing uploads unless somebody publishes a finished run.",
        "Nothing is published unless you publish a finished run yourself, and "
        "what travels then is the run's proof — the signed report and its "
        "receipts — and never the episodes.",
        "Publishing is a separate step, taken after a run finishes and only if "
        "you choose to.",
        "The raw episodes stay on this machine. They are not in the proof "
        "directory and nothing sends them.",
        "It has one address that accepts anything, and what that address "
        "accepts is a signed run somebody chose to publish.",
        "Raw episodes: retained locally; not uploaded",
    )

    for sentence in true_now:
        for described, pattern in STALE_UPLOAD_CLAIMS:
            assert not pattern.search(sentence), (described, sentence)
