"""A Skill is a tree, and the tree survives every copy. Decisions 0019 §1.

A Skill version is a content-addressed tree — ``SKILL.md`` plus ``references/``,
``templates/``, and the other declared supporting files — never a single
Markdown document. Every stage between a participant's directory and the
subject's mount copies that tree file by file, and a stage that quietly
flattened one would produce a Skill the subject could not follow while every
digest still checked out, because the digest is computed from the same list
that was flattened.

So this walks one tree with two subdirectories through all four copies and
asserts the nested paths at each of them: the scan, the draft, the run's staged
inputs, and the content-addressed mount the compiled configuration points at.
The mount is the stage that had no test at all; its real form runs inside a
container against a paid provider, and the copy itself needs neither, so it is
driven here directly.

The last test is the reason the rest matter: moving a file out of
``references/`` without changing a byte of it changes the Skill's root digest.
The tree shape is inside the identity, so a comparison between a flattened tree
and a nested one is a comparison between two different Skills.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.runs.support import RunHarness, run_harness
from techtree.engines.registry import EngineRegistry
from techtree.manifests.builder import skill_content_digest
from techtree.models.skill import SkillFile
from techtree.runs.child_registry import ChildRegistry
from techtree.runs.real import RealVerifiersExecutor
from techtree.settings import Settings
from techtree.skills.policy import default_instruction_skill_policy
from techtree.skills.scanner import scan_skill
from techtree.verifiers.compiler import skill_directory_name
from techtree.verifiers.models import RunPaths

pytestmark = pytest.mark.integration

#: The two supporting files decisions 0019 §1 names, beside the entry file every
#: Skill has. Their contents are ordinary prose: what is under test is where
#: they end up, not what they say.
_ENTRY = """# Branch code

Read `references/notes.md` before deciding, and answer in the shape
`templates/answer.md` gives.
"""
_REFERENCE = "A branch is chosen once. The earlier condition wins.\n"
_TEMPLATE = "Answer: <one line, no working shown>\n"

_NESTED_PATHS = ("references/notes.md", "templates/answer.md")


def write_skill_tree(root: Path) -> Path:
    """Write one Skill with two subdirectories and return its directory."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(_ENTRY, encoding="utf-8")
    for relative, text in zip(_NESTED_PATHS, (_REFERENCE, _TEMPLATE), strict=True):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    return write_skill_tree(tmp_path / "branch-code-tree")


@pytest.fixture
def harness(tmp_path: Path, tree: Path) -> RunHarness:
    """Prepare a draft from the multi-file tree and wire the run stack over it."""
    return run_harness(tmp_path / "home", skill_path=tree)


def test_the_scanner_reports_both_nested_files(tree: Path) -> None:
    scan = scan_skill(tree, default_instruction_skill_policy())

    assert [item.relative_path.as_posix() for item in scan.files] == [
        "SKILL.md",
        *_NESTED_PATHS,
    ]


def test_the_draft_holds_the_whole_tree(harness: RunHarness) -> None:
    """The snapshot is what the run will be built from, so it is the tree."""
    draft = harness.draft
    files = harness.drafts.skill_files_dir(draft.id)

    assert list(draft.included_files) == ["SKILL.md", *_NESTED_PATHS]
    assert draft.included_files == sorted(draft.included_files)
    for relative in _NESTED_PATHS:
        assert (files / relative).is_file(), relative
    assert (files / "references" / "notes.md").read_text(encoding="utf-8") == _REFERENCE


def test_the_run_stages_the_whole_tree(harness: RunHarness) -> None:
    """Spec §9: the run owns its own copy, and its own copy is the tree."""
    run_id = harness.start().state.run_id
    files = harness.artifacts.skill_files_dir(run_id)

    for relative in _NESTED_PATHS:
        assert (files / relative).is_file(), relative
    assert [
        entry.path for entry in harness.inputs(run_id).candidate_skill.artifact.files
    ] == [
        "SKILL.md",
        *_NESTED_PATHS,
    ]


def test_the_mount_the_subject_reads_holds_the_whole_tree(
    harness: RunHarness,
) -> None:
    """The stage between the run's inputs and the subject, copied by hand.

    ``_materialize_skill_mounts`` places each declared Skill under the
    content-addressed directory name the compiled configuration hands the
    engine. Its real caller needs a container and a paid provider; the copy
    needs neither, so it is driven directly against the run's own verified
    inputs.
    """
    run_id = harness.start().state.run_id
    inputs = harness.inputs(run_id)
    run_paths = RunPaths.for_run(harness.paths, run_id)
    executor = RealVerifiersExecutor(
        paths=harness.paths,
        engine_registry=EngineRegistry(harness.paths, Settings()),
        child_registry=ChildRegistry(),
    )

    executor._materialize_skill_mounts(inputs, run_paths)

    digest = inputs.candidate_skill.artifact.root_digest
    mounted = run_paths.skill_files_dir / skill_directory_name(digest)
    assert (mounted / "SKILL.md").is_file()
    for relative in _NESTED_PATHS:
        assert (mounted / relative).is_file(), relative
    assert (mounted / "templates" / "answer.md").read_text(
        encoding="utf-8"
    ) == _TEMPLATE


def test_moving_a_file_out_of_its_directory_changes_the_skill(tmp_path: Path) -> None:
    """The tree shape is inside the digest, so a flattened tree is another Skill."""
    nested = scan_skill(
        write_skill_tree(tmp_path / "nested"), default_instruction_skill_policy()
    )

    flat_root = tmp_path / "flat"
    flat_root.mkdir()
    (flat_root / "SKILL.md").write_text(_ENTRY, encoding="utf-8")
    (flat_root / "notes.md").write_text(_REFERENCE, encoding="utf-8")
    (flat_root / "answer.md").write_text(_TEMPLATE, encoding="utf-8")
    flat = scan_skill(flat_root, default_instruction_skill_policy())

    assert {item.digest for item in nested.files} == {
        item.digest for item in flat.files
    }
    assert _content_digest(nested.files) != _content_digest(flat.files)


def _content_digest(files: object) -> str:
    """Return the root digest of one scanned tree."""
    assert isinstance(files, list)
    return skill_content_digest(
        [
            SkillFile(
                path=item.relative_path.as_posix(),
                media_type=item.media_type,
                size=item.size,
                digest=item.digest,
            )
            for item in files
        ]
    )
