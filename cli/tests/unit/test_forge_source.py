"""Looking at a Source Skill without running it (U3a).

The tests hold what the source record promises: every entry is listed and
nothing is run or followed; a file the instructions name that Techtree cannot
carry refuses the whole Skill, by name, and no copy is kept; a file nothing
names is left out and said to be; the header is a declaration and grants
nothing; and a reduced copy is a new source whose lineage names the original.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from techtree.cli.app import create_app
from techtree.errors import ValidationError
from techtree.forge.source import (
    SOURCE_FILENAME,
    inspect_source_skill,
    lineage_from_source,
)
from techtree.manifests.builder import skill_content_digest
from techtree.paths import paths_from_root

HEADER = (
    "---\n"
    "name: demo-skill\n"
    "description: Fix the failing test by reading it first.\n"
    "allowed-tools: Bash Read\n"
    "metadata:\n"
    "  author: regents\n"
    "---\n\n"
)


def write_source(root: Path, body: str, files: dict[str, str]) -> Path:
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text(HEADER + body, encoding="utf-8")
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def invoke(home: Path, *arguments: str) -> tuple[int, dict[str, Any]]:
    result = CliRunner().invoke(
        create_app(), ["--home", str(home), "--json", "forge", *arguments]
    )
    return result.exit_code, json.loads(result.stdout)


def source_dirs(home: Path) -> list[Path]:
    sources = home / "forge" / "sources"
    return sorted(sources.iterdir()) if sources.is_dir() else []


def test_a_supported_skill_is_kept_as_hashed_and_what_nothing_names_is_left_out(
    tmp_path: Path, temp_techtree_home: Path
) -> None:
    root = write_source(
        tmp_path / "demo-skill",
        "Read [the recipes](references/recipes.md) before you start.\n",
        {
            "references/recipes.md": "Run `pytest -q` and read the failure.\n",
            "scripts/unused.sh": "#!/bin/sh\ntouch ran\n",
            ".notes.md": "private\n",
        },
    )

    code, envelope = invoke(temp_techtree_home, "inspect-skill", str(root))

    assert code == 0
    assert envelope["operation"] == "plan.prepare"
    status = envelope["facts"]
    record = status["record"]
    assert record["state"] == "admitted"
    assert record["refusals"] == []
    assert record["lineage"] is None
    entries = {entry["path"]: entry for entry in record["entries"]}
    assert set(entries) == {
        ".notes.md",
        "SKILL.md",
        "references/recipes.md",
        "scripts/unused.sh",
    }
    assert entries[".notes.md"]["reason"] == "hidden"
    assert entries[".notes.md"]["digest"] is None
    assert entries["scripts/unused.sh"]["reason"] == "file_type"
    assert entries["scripts/unused.sh"]["required"] is False
    assert entries["references/recipes.md"]["required"] is True
    assert [file["path"] for file in record["admitted_files"]] == [
        "SKILL.md",
        "references/recipes.md",
    ]
    assert record["declaration"]["allowed_tools"] == ["Bash", "Read"]
    assert record["declaration"]["metadata"] == {"author": "regents"}
    [warning] = envelope["warnings"]
    assert warning["id"] == "forge_source_files_left_out"
    assert ".notes.md" in warning["text"] and "scripts/unused.sh" in warning["text"]
    [action] = envelope["next_actions"]
    assert action["prepared_arguments"]["command"] == ["forge", "status"]
    assert action["prepared_arguments"]["arguments"] == [status["source_id"]]
    snapshot = Path(status["snapshot_path"])
    assert sorted(
        path.relative_to(snapshot).as_posix()
        for path in snapshot.rglob("*")
        if path.is_file()
    ) == ["SKILL.md", "references/recipes.md"]
    for relative in ("SKILL.md", "references/recipes.md"):
        assert (snapshot / relative).read_bytes() == (root / relative).read_bytes()
    assert not (tmp_path / "demo-skill" / "ran").exists()

    code, shown = invoke(temp_techtree_home, "status", status["source_id"])
    assert code == 0
    assert shown["facts"]["record"] == record


def test_a_required_script_refuses_the_skill_by_name_and_keeps_no_copy(
    tmp_path: Path, temp_techtree_home: Path
) -> None:
    root = write_source(
        tmp_path / "demo-skill",
        "First run `scripts/setup.sh`, then read references/recipes.md.\n",
        {
            "scripts/setup.sh": "#!/bin/sh\ntouch ran\n",
            "references/recipes.md": "Read the failure.\n",
        },
    )

    code, envelope = invoke(temp_techtree_home, "inspect-skill", str(root))

    assert code == 3
    error = envelope["error"]
    assert error["code"] == "forge_skill_unsupported"
    assert "scripts/setup.sh" in error["message"]
    assert "look at the Skill again" in error["message"]
    [refusal] = error["details"]["refusals"]
    assert refusal == {
        "path": "scripts/setup.sh",
        "reason": "required_unsupported",
        "message": refusal["message"],
    }
    source_id = error["details"]["source_id"]
    [action] = envelope["next_actions"]
    assert action["prepared_arguments"]["arguments"] == [source_id]
    [directory] = source_dirs(temp_techtree_home)
    assert sorted(path.name for path in directory.iterdir()) == [SOURCE_FILENAME]
    assert not (root / "ran").exists()

    code, shown = invoke(temp_techtree_home, "status", source_id)
    assert code == 0
    assert shown["facts"]["record"]["state"] == "refused"
    assert shown["facts"]["snapshot_path"] is None


def test_a_reduced_copy_is_a_new_source_with_lineage_to_the_original(
    tmp_path: Path, temp_techtree_home: Path
) -> None:
    original = write_source(
        tmp_path / "original" / "demo-skill",
        "Run [the helper](scripts/setup.py) first.\n",
        {"scripts/setup.py": "print('setup')\n"},
    )
    _, refused = invoke(temp_techtree_home, "inspect-skill", str(original))
    parent_id = refused["error"]["details"]["source_id"]
    reduced = write_source(
        tmp_path / "reduced" / "demo-skill", "Read the failing test first.\n", {}
    )

    code, envelope = invoke(
        temp_techtree_home,
        "inspect-skill",
        str(reduced),
        "--derived-from",
        parent_id,
    )

    assert code == 0
    record = envelope["facts"]["record"]
    assert record["source_id"] != parent_id
    assert record["state"] == "admitted"
    parent = json.loads(
        (
            temp_techtree_home / "forge" / "sources" / parent_id / SOURCE_FILENAME
        ).read_bytes()
    )
    assert record["lineage"] == {
        "kind": "source",
        "parent_id": parent_id,
        "parent_digest": parent["admitted_digest"],
        "root_digest": parent["admitted_digest"],
    }
    assert record["admitted_digest"] != parent["admitted_digest"]


def test_a_copy_that_admits_what_its_original_admits_is_not_a_derivative(
    tmp_path: Path, temp_techtree_home: Path
) -> None:
    paths = paths_from_root(temp_techtree_home)
    root = write_source(tmp_path / "demo-skill", "Read the failing test.\n", {})
    first = inspect_source_skill(paths, root, lineage=None)

    with pytest.raises(ValidationError) as raised:
        inspect_source_skill(
            paths, root, lineage=lineage_from_source(paths, first.source_id)
        )

    assert raised.value.code == "forge_source_unchanged"
    assert source_dirs(temp_techtree_home) == [Path(first.path)]
    assert first.record.admitted_digest == skill_content_digest(
        first.record.admitted_files
    )


@pytest.mark.parametrize(
    ("body", "reason", "named"),
    [
        ("See [notes](notes.md).\n", "missing_reference", "notes.md"),
        ("See [shared](../shared/SKILL.md).\n", "outside_reference", "../shared"),
    ],
)
def test_a_link_the_skill_cannot_satisfy_refuses_it(
    tmp_path: Path, temp_techtree_home: Path, body: str, reason: str, named: str
) -> None:
    root = write_source(tmp_path / "demo-skill", body, {})

    status = inspect_source_skill(
        paths_from_root(temp_techtree_home), root, lineage=None
    )

    [refusal] = status.record.refusals
    assert (refusal.path, refusal.reason) == ("SKILL.md", reason)
    assert named in refusal.message


def test_a_link_is_recorded_and_never_followed(
    tmp_path: Path, temp_techtree_home: Path
) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("not part of the Skill\n", encoding="utf-8")
    root = write_source(tmp_path / "demo-skill", "Read guide.md.\n", {})
    os.symlink(outside, root / "guide.md")

    status = inspect_source_skill(
        paths_from_root(temp_techtree_home), root, lineage=None
    )

    [entry] = [e for e in status.record.entries if e.path == "guide.md"]
    assert (entry.kind, entry.reason, entry.required) == ("symlink", "symlink", True)
    assert entry.digest is None
    [refusal] = status.record.refusals
    assert (refusal.path, refusal.reason) == ("guide.md", "required_unsupported")


@pytest.mark.parametrize(
    ("header", "words"),
    [
        (
            "---\nname: demo-skill\ndescription: x\nallowed-tools:\n  - Bash\n---\n",
            "line 4",
        ),
        (
            "---\nname: demo-skill\ndescription: x\nmetadata:\n  hermes:\n"
            "    tags: x\n---\n",
            "line 5 nests another level",
        ),
        ("---\nname: other-name\ndescription: x\n---\n", "folder is called demo-skill"),
        ("---\nname: demo-skill\n---\n", "description"),
        ("name: demo-skill\n", "does not begin"),
    ],
)
def test_a_header_techtree_does_not_read_refuses_the_skill(
    tmp_path: Path, temp_techtree_home: Path, header: str, words: str
) -> None:
    root = tmp_path / "demo-skill"
    root.mkdir()
    (root / "SKILL.md").write_text(header + "\nBody.\n", encoding="utf-8")

    status = inspect_source_skill(
        paths_from_root(temp_techtree_home), root, lineage=None
    )

    [refusal] = status.record.refusals
    assert (refusal.path, refusal.reason) == ("SKILL.md", "declaration")
    assert words in refusal.message
    assert status.record.declaration is None
    assert status.snapshot_path is None
