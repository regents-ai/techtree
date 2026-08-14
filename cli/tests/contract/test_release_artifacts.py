"""The committed release artifacts. Spec sections 9.3.1, 9.4 and 9.6.

`release/` is a contract with three consumers who do not run this code: the
plugin repository copies the ReleaseCore verbatim, the website wraps it, and an
operator hashes it. These tests hold the parts of that contract a regeneration
could break without anybody noticing — that the committed bytes are the ones
this tree produces, that the two copies of the document are one document, that
generating twice produces the same bytes, and that the generator can be asked
whether the tree is current without writing to it.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from fixtures.starter import tree_digest
from techtree.release.document import (
    document_digest,
    is_canonical_document,
    packaged_release_core_bytes,
    parse_release_core,
)
from techtree.release.models import PLACEHOLDER_DIGEST, PLACEHOLDER_OBJECT_URL

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RELEASE_DIRECTORY = REPOSITORY_ROOT / "release"
PACKAGED_COPY = (
    REPOSITORY_ROOT / "src" / "techtree" / "resources" / "release" / "release-core.json"
)


def generator() -> Any:
    """Import the release generator from the tools tree.

    ``tools`` is a scripts directory rather than an installed package, so it is
    loaded by path. Importing it is what lets these tests compare the committed
    artifacts against what the generator produces, instead of against
    themselves.
    """
    location = REPOSITORY_ROOT / "tools" / "build_release_core.py"
    spec = importlib.util.spec_from_file_location(
        "techtree_build_release_core", location
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def artifacts() -> dict[Path, bytes]:
    """Return every release artifact this source tree produces right now."""
    produced: dict[Path, bytes] = generator().release_artifacts()
    return produced


# ---------------------------------------------------------------------------
# What is committed
# ---------------------------------------------------------------------------


def test_every_release_artifact_is_committed(artifacts: dict[Path, bytes]) -> None:
    assert {path.relative_to(REPOSITORY_ROOT).as_posix() for path in artifacts} == {
        "release/build-info.json",
        "release/release-core.json",
        "release/release-core.schema.json",
        "src/techtree/resources/release/release-core.json",
    }
    for path in artifacts:
        assert path.is_file(), f"{path} was never generated"


def test_the_committed_artifacts_are_the_ones_this_tree_produces(
    artifacts: dict[Path, bytes],
) -> None:
    assert generator().drift(artifacts) == []


def test_the_shipped_copy_and_the_staged_copy_are_one_document() -> None:
    staged = (RELEASE_DIRECTORY / "release-core.json").read_bytes()
    assert staged == PACKAGED_COPY.read_bytes()
    assert staged == packaged_release_core_bytes()


def test_the_committed_release_core_is_in_the_published_spelling() -> None:
    assert is_canonical_document(packaged_release_core_bytes())


def test_the_build_record_names_the_bytes_it_produced() -> None:
    record = json.loads((RELEASE_DIRECTORY / "build-info.json").read_text("utf-8"))
    core_digest = document_digest(packaged_release_core_bytes())
    assert record["artifacts"]["release/release-core.json"] == core_digest
    assert (
        record["artifacts"]["src/techtree/resources/release/release-core.json"]
        == core_digest
    )


def test_the_build_record_reads_no_clock(artifacts: dict[Path, bytes]) -> None:
    """A timestamp would make every drift check a coin toss."""
    record = json.loads(
        artifacts[RELEASE_DIRECTORY / "build-info.json"].decode("utf-8")
    )
    assert "generated_at" not in record
    assert "timestamp" not in json.dumps(record)


def test_the_published_schema_describes_the_committed_document() -> None:
    schema = json.loads(
        (RELEASE_DIRECTORY / "release-core.schema.json").read_text("utf-8")
    )
    document = json.loads(packaged_release_core_bytes())
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(document)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_generating_twice_produces_the_same_bytes() -> None:
    first = generator().release_artifacts()
    second = generator().release_artifacts()
    assert {path.name: data for path, data in first.items()} == {
        path.name: data for path, data in second.items()
    }


def test_a_second_generator_process_agrees_with_the_first(
    artifacts: dict[Path, bytes],
) -> None:
    """A freshly imported generator is a proxy for a second machine."""
    assert generator().release_artifacts() == artifacts


# ---------------------------------------------------------------------------
# The generator's dry run
# ---------------------------------------------------------------------------


def test_the_dry_run_reports_a_current_tree_and_writes_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    before = {path: path.read_bytes() for path in _committed_paths()}
    assert generator().main(["--check"]) == 0
    assert {path: path.read_bytes() for path in _committed_paths()} == before
    assert "match this source tree" in capsys.readouterr().out


def test_the_dry_run_reports_an_artifact_nobody_generated() -> None:
    absent = RELEASE_DIRECTORY / "release-core.not-generated.json"
    assert generator().drift({absent: b"{}\n"}) == [
        "release/release-core.not-generated.json is missing"
    ]
    assert not absent.exists()


def test_the_dry_run_notices_an_edited_artifact() -> None:
    before = PACKAGED_COPY.read_bytes()
    assert generator().drift({PACKAGED_COPY: b"{}\n"}) == [
        "src/techtree/resources/release/release-core.json is not what this "
        "source tree generates"
    ]
    assert PACKAGED_COPY.read_bytes() == before


# ---------------------------------------------------------------------------
# What the document says about itself
# ---------------------------------------------------------------------------


def test_this_build_carries_a_self_declaring_placeholder_release() -> None:
    core = parse_release_core(packaged_release_core_bytes())
    assert core.placeholder_release is True
    assert core.placeholder_fields == [
        "cli_source_commit",
        "cli_version",
        "maximum_tested_host_hermes_version",
        "release_id",
        "skill_improver_digest",
        "starter_skill_digest",
        "starter_skill_object_url",
    ]


def test_the_release_names_the_climb_and_harness_this_build_ships() -> None:
    core = parse_release_core(packaged_release_core_bytes())
    assert core.intro_climb_reference == "hello-world-climb@1"
    assert core.subject_hermes_version == "0.19.0"
    assert core.protocol_version == "v1alpha1"


# ---------------------------------------------------------------------------
# The founder-supplied starter Skill
# ---------------------------------------------------------------------------
#
# The wheel carries no Skill bytes, so the starter Skill is not a generated
# artifact and not package data. It is a founder decision, like the inputs
# beside it, and `starter_skill_digest` is the coordinate it answers to. These
# tests hold the two things about it that a careless edit could break: that it
# is the pack's own text with exactly the one change the founder directed, and
# that it never tells the model what it is.


STARTER_SKILL = RELEASE_DIRECTORY / "skills" / "hello-world-starter-v1" / "SKILL.md"
PACK_STARTER_SKILL = (
    REPOSITORY_ROOT
    / "docs"
    / "spec"
    / "closeout-helloworld"
    / "skills"
    / "hello-world-starter-v1"
    / "SKILL.md"
)

#: Decisions 0010 item 3, verbatim. The procedure must never move into the
#: frontmatter: discovery metadata that carried it would hand the subject the
#: intervention without the Skill ever being opened.
STARTER_DESCRIPTION = "Apply BranchCode v1 and return a BRANCH-XX token."


def test_the_installed_starter_skill_is_the_pack_text_with_one_change() -> None:
    """Decisions 0010 item 3: the description, and nothing else."""
    installed = STARTER_SKILL.read_text().splitlines(keepends=True)
    supplied = PACK_STARTER_SKILL.read_text().splitlines(keepends=True)
    differing = [
        (before, after)
        for before, after in zip(supplied, installed, strict=True)
        if before != after
    ]

    assert len(differing) == 1
    before, after = differing[0]
    assert before.startswith("description:")
    assert after == f"description: {STARTER_DESCRIPTION}\n"


def test_the_starter_skill_keeps_the_procedure_out_of_its_frontmatter() -> None:
    """A description that taught the procedure would bypass the Skill itself."""
    frontmatter = STARTER_SKILL.read_text().split("---", 2)[1]

    assert f"description: {STARTER_DESCRIPTION}" in frontmatter
    assert "modulo" not in frontmatter
    assert "position" not in frontmatter
    assert "distinct" not in frontmatter
    assert "character" not in frontmatter


def test_the_starter_skill_says_nothing_about_being_incomplete() -> None:
    """Decisions 0010 item 2: the release metadata discloses, the Skill does not.

    Mounting the disclosure would change what the evaluation measures — the
    subject would be reading a warning rather than a procedure. Every place
    the disclosure does belong is outside these bytes.
    """
    mounted = STARTER_SKILL.read_text().lower()

    for phrase in ("incomplete", "intentional", "deliberate", "defect", "calibrat"):
        assert phrase not in mounted, phrase


def test_the_starter_skill_is_licensed_the_way_the_founder_chose() -> None:
    """Decisions 0011: MIT everywhere, and no edit needed before hashing."""
    assert "license: MIT" in STARTER_SKILL.read_text().split("---", 2)[1]


#: The digest the release will bind ``starter_skill_digest`` to. Decisions 0008
#: item 1 makes it the ordered content-tree digest the scanner computes, not the
#: SHA-256 of the file, and decision 0012 ratified these bytes at this path. The
#: value is written out rather than recomputed so that an edit to the Skill has
#: to be an edit to the coordinate as well.
STARTER_SKILL_TREE_DIGEST = (
    "sha256:596d1368ac157975accce7ceff835eed6bfb789eaf68528a0aefa25a68793b0b"
)


def test_the_starter_skill_still_hashes_to_the_digest_the_release_will_pin() -> None:
    """The Skill and the coordinate that names it cannot drift apart silently."""
    assert tree_digest(STARTER_SKILL.parent) == STARTER_SKILL_TREE_DIGEST


def test_the_starter_skill_coordinates_are_both_still_unchosen() -> None:
    """A digest with no address names bytes nobody can fetch, and vice versa.

    Both halves are founder decisions taken at the same moment, so this build
    carries both placeholders or neither. The pair is asserted rather than
    assumed because binding one alone would produce a release that verifies and
    still cannot hand anybody a Skill.
    """
    core = parse_release_core(packaged_release_core_bytes())
    assert core.starter_skill_digest == PLACEHOLDER_DIGEST
    assert core.starter_skill_object_url == PLACEHOLDER_OBJECT_URL


def _committed_paths() -> list[Path]:
    return [
        RELEASE_DIRECTORY / "build-info.json",
        RELEASE_DIRECTORY / "release-core.json",
        RELEASE_DIRECTORY / "release-core.schema.json",
        PACKAGED_COPY,
    ]
