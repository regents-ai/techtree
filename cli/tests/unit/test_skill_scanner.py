"""Skill policy, validation, and secret scanning. Spec sections 15.1 and 15.2.

The scanner is the boundary between a participant's working directory and an
immutable scientific input, so these tests are written from the position that
the directory is hostile until proven otherwise. Section 26 WP2 names the cases
that have to fail — symlinks, devices, hidden files, oversized and overlarge
skills, binary payloads, and credentials — and each of them appears here with
the specific reason it is refused.

Two properties are checked repeatedly and deliberately:

* A refusal is a typed :class:`~techtree.errors.ValidationError` that says what
  to fix.
* No refusal, and no finding, ever repeats the text that triggered it.

Every credential-shaped string in this file and in the fixtures is the letter
``x`` with the word ``FAKE`` spelled inside it.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path, PurePosixPath

import pytest

from techtree.canonical import sha256_digest_bytes
from techtree.errors import NotFoundError, ValidationError
from techtree.skills.policy import SkillPolicy, default_instruction_skill_policy
from techtree.skills.scanner import (
    MEDIA_TYPES,
    ScannedFile,
    _reject_case_collisions,
    enumerate_files,
    media_type_for,
    resolve_skill_root,
    scan_file_for_secrets,
    scan_skill,
    validate_file,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "skills"
VALID = FIXTURES / "valid-procedure"
INVALID_BINARY = FIXTURES / "invalid-binary"
INVALID_SECRET = FIXTURES / "invalid-secret"
INVALID_SYMLINK = FIXTURES / "invalid-symlink"

#: The body of the fake private key in ``invalid-secret/notes.md``. Findings and
#: error text are asserted never to contain it.
FAKE_KEY_BODY = "xxxxxxxxxxFAKExxxxxxxxxxNOTxxxxxxxxxxAxxxxxxxxxxKEYxxxxxxxxxx"


@pytest.fixture
def policy() -> SkillPolicy:
    return default_instruction_skill_policy()


def write(path: Path, text: str) -> Path:
    """Create a file and any parents it needs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def skill_dir(root: Path, name: str = "skill") -> Path:
    """Create a minimal valid skill directory."""
    directory = root / name
    write(directory / "SKILL.md", "# Skill\n\nDo the thing.\n")
    return directory


def error_text(error: ValidationError) -> str:
    """Everything a caller could see: the message and the machine details."""
    return f"{error.message} {json.dumps(error.details, sort_keys=True)}"


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


def test_default_policy_matches_the_v01_instruction_skill_rules() -> None:
    subject = default_instruction_skill_policy()

    assert subject.required_entrypoint == "SKILL.md"
    assert subject.allowed_suffixes == frozenset(
        {".md", ".txt", ".json", ".yaml", ".yml"}
    )
    assert subject.maximum_files == 64
    assert subject.maximum_file_bytes == 256 * 1024
    assert subject.maximum_total_bytes == 2 * 1024 * 1024
    assert subject.allow_symlinks is False
    assert subject.allow_hidden_files is False


def test_policy_is_frozen(policy: SkillPolicy) -> None:
    with pytest.raises(AttributeError):
        policy.maximum_files = 1_000  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Root resolution
# ---------------------------------------------------------------------------


def test_root_resolves_from_the_directory_and_from_the_entrypoint() -> None:
    assert resolve_skill_root(VALID) == VALID
    assert resolve_skill_root(VALID / "SKILL.md") == VALID


def test_root_rejects_a_directory_without_an_entrypoint(tmp_path: Path) -> None:
    write(tmp_path / "skill" / "notes.md", "# Notes\n")

    with pytest.raises(ValidationError) as caught:
        resolve_skill_root(tmp_path / "skill")

    assert "SKILL.md" in caught.value.message


def test_root_rejects_being_named_by_some_other_file(tmp_path: Path) -> None:
    directory = skill_dir(tmp_path)
    write(directory / "notes.md", "# Notes\n")

    with pytest.raises(ValidationError) as caught:
        resolve_skill_root(directory / "notes.md")

    assert "notes.md" in caught.value.message


def test_root_reports_a_missing_path_as_not_found(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError):
        resolve_skill_root(tmp_path / "absent")


def test_root_rejects_a_broken_symlink(tmp_path: Path) -> None:
    link = tmp_path / "skill"
    os.symlink(tmp_path / "nowhere", link)

    with pytest.raises(ValidationError):
        resolve_skill_root(link)


# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------


def test_enumeration_finds_nested_files_in_a_stable_order() -> None:
    relative = [item.relative_to(VALID).as_posix() for item in enumerate_files(VALID)]

    assert relative == [
        "SKILL.md",
        "config.yaml",
        "data/examples.json",
        "glossary.txt",
        "reference/notes.md",
    ]


def test_enumeration_reports_a_symlink_instead_of_skipping_it() -> None:
    relative = [
        item.relative_to(INVALID_SYMLINK).as_posix()
        for item in enumerate_files(INVALID_SYMLINK)
    ]

    assert relative == ["SKILL.md", "outside.md"]


def test_enumeration_does_not_descend_into_a_symlinked_directory(
    tmp_path: Path,
) -> None:
    directory = skill_dir(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    write(elsewhere / "hidden-treasure.md", "# Not part of the skill\n")
    os.symlink(elsewhere, directory / "linked")

    relative = [
        item.relative_to(directory).as_posix() for item in enumerate_files(directory)
    ]

    assert relative == ["SKILL.md", "linked"]


# ---------------------------------------------------------------------------
# A clean skill
# ---------------------------------------------------------------------------


def test_a_clean_skill_scans_with_sorted_files_and_no_findings(
    policy: SkillPolicy,
) -> None:
    result = scan_skill(VALID, policy)

    assert result.root == VALID
    assert [item.relative_path.as_posix() for item in result.files] == [
        "SKILL.md",
        "config.yaml",
        "data/examples.json",
        "glossary.txt",
        "reference/notes.md",
    ]
    assert result.secret_findings == []
    assert result.warnings == []


def test_scanned_files_carry_size_media_type_and_content_digest(
    policy: SkillPolicy,
) -> None:
    result = scan_skill(VALID, policy)

    for item in result.files:
        data = item.source_path.read_bytes()
        assert item.size == len(data)
        assert item.digest == sha256_digest_bytes(data)
        assert item.media_type == MEDIA_TYPES[item.source_path.suffix]
        assert not item.relative_path.is_absolute()


def test_the_entrypoint_may_be_named_directly(policy: SkillPolicy) -> None:
    from_directory = scan_skill(VALID, policy)
    from_entrypoint = scan_skill(VALID / "SKILL.md", policy)

    assert [item.digest for item in from_directory.files] == [
        item.digest for item in from_entrypoint.files
    ]


def test_scanning_the_same_content_twice_gives_the_same_answer(
    tmp_path: Path, policy: SkillPolicy
) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    for directory in (first, second):
        write(directory / "SKILL.md", "# Skill\n")
        write(directory / "reference/notes.md", "# Notes\n")
    os.utime(second / "SKILL.md", (0, 0))
    (second / "reference" / "notes.md").chmod(0o600)

    assert [item.digest for item in scan_skill(first, policy).files] == [
        item.digest for item in scan_skill(second, policy).files
    ]


# ---------------------------------------------------------------------------
# Media types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("SKILL.md", "text/markdown"),
        ("notes.txt", "text/plain"),
        ("data.json", "application/json"),
        ("config.yaml", "application/yaml"),
        ("config.yml", "application/yaml"),
        ("SHOUTING.MD", "text/markdown"),
    ],
)
def test_media_types_are_fixed_strings(name: str, expected: str) -> None:
    assert media_type_for(Path(name)) == expected


def test_media_type_refuses_a_suffix_it_does_not_define() -> None:
    with pytest.raises(ValidationError):
        media_type_for(Path("diagram.png"))


# ---------------------------------------------------------------------------
# Section 26 WP2: files that must be refused
# ---------------------------------------------------------------------------


def test_external_symlink_is_refused(policy: SkillPolicy) -> None:
    with pytest.raises(ValidationError) as caught:
        scan_skill(INVALID_SYMLINK, policy)

    assert "symlink" in caught.value.message
    assert caught.value.details["path"] == "outside.md"


def test_nested_symlink_is_refused(tmp_path: Path, policy: SkillPolicy) -> None:
    directory = skill_dir(tmp_path)
    (directory / "reference").mkdir()
    os.symlink("/etc/passwd", directory / "reference" / "notes.md")

    with pytest.raises(ValidationError) as caught:
        scan_skill(directory, policy)

    assert caught.value.details["path"] == "reference/notes.md"


def test_symlinked_directory_is_refused(tmp_path: Path, policy: SkillPolicy) -> None:
    directory = skill_dir(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    write(elsewhere / "notes.md", "# Elsewhere\n")
    os.symlink(elsewhere, directory / "reference")

    with pytest.raises(ValidationError) as caught:
        scan_skill(directory, policy)

    assert "symlink" in caught.value.message


def test_symlinked_root_is_refused(tmp_path: Path, policy: SkillPolicy) -> None:
    directory = skill_dir(tmp_path)
    link = tmp_path / "linked-skill"
    os.symlink(directory, link)

    with pytest.raises(ValidationError) as caught:
        scan_skill(link, policy)

    assert "symlink" in caught.value.message


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="no FIFOs on this platform")
def test_fifo_is_refused(tmp_path: Path, policy: SkillPolicy) -> None:
    directory = skill_dir(tmp_path)
    os.mkfifo(directory / "pipe.txt")

    with pytest.raises(ValidationError) as caught:
        scan_skill(directory, policy)

    assert "FIFO" in caught.value.message


def test_dot_env_is_refused_as_hidden(tmp_path: Path, policy: SkillPolicy) -> None:
    directory = skill_dir(tmp_path)
    write(directory / ".env", "TECHTREE_MODEL_API_KEY=xxxxFAKExxxx\n")

    with pytest.raises(ValidationError) as caught:
        scan_skill(directory, policy)

    assert "hidden" in caught.value.message
    assert caught.value.details["path"] == ".env"
    assert "FAKE" not in error_text(caught.value)


def test_hidden_directory_is_refused(tmp_path: Path, policy: SkillPolicy) -> None:
    directory = skill_dir(tmp_path)
    write(directory / ".git" / "config.txt", "[core]\n")

    with pytest.raises(ValidationError) as caught:
        scan_skill(directory, policy)

    assert caught.value.details["hidden_component"] == ".git"


def test_unsupported_suffix_is_refused(tmp_path: Path, policy: SkillPolicy) -> None:
    directory = skill_dir(tmp_path)
    (directory / "diagram.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    with pytest.raises(ValidationError) as caught:
        scan_skill(directory, policy)

    assert caught.value.details["suffix"] == ".png"


def test_binary_content_under_a_text_suffix_is_refused(policy: SkillPolicy) -> None:
    with pytest.raises(ValidationError) as caught:
        scan_skill(INVALID_BINARY, policy)

    assert "binary" in caught.value.message
    assert caught.value.details["path"] == "payload.txt"


def test_invalid_utf8_is_refused(tmp_path: Path, policy: SkillPolicy) -> None:
    directory = skill_dir(tmp_path)
    (directory / "notes.md").write_bytes(b"# Notes\n\xff\xfe not text\n")

    with pytest.raises(ValidationError) as caught:
        scan_skill(directory, policy)

    assert "UTF-8" in caught.value.message


def test_oversized_file_is_refused(tmp_path: Path, policy: SkillPolicy) -> None:
    directory = skill_dir(tmp_path)
    write(directory / "big.md", "x" * (policy.maximum_file_bytes + 1))

    with pytest.raises(ValidationError) as caught:
        scan_skill(directory, policy)

    assert caught.value.details["maximum_file_bytes"] == policy.maximum_file_bytes


def test_overlarge_skill_is_refused(tmp_path: Path, policy: SkillPolicy) -> None:
    directory = skill_dir(tmp_path)
    chunk = "x" * (200 * 1024)
    for index in range(12):
        write(directory / f"part-{index:02d}.md", chunk)

    with pytest.raises(ValidationError) as caught:
        scan_skill(directory, policy)

    assert caught.value.details["maximum_total_bytes"] == policy.maximum_total_bytes


def test_too_many_files_is_refused(tmp_path: Path, policy: SkillPolicy) -> None:
    directory = skill_dir(tmp_path)
    for index in range(policy.maximum_files):
        write(directory / f"note-{index:03d}.md", "# Note\n")

    with pytest.raises(ValidationError) as caught:
        scan_skill(directory, policy)

    assert caught.value.details["count"] == policy.maximum_files + 1
    assert caught.value.details["maximum_files"] == policy.maximum_files


def test_exactly_the_file_limit_is_allowed(tmp_path: Path, policy: SkillPolicy) -> None:
    directory = skill_dir(tmp_path)
    for index in range(policy.maximum_files - 1):
        write(directory / f"note-{index:03d}.md", "# Note\n")

    assert len(scan_skill(directory, policy).files) == policy.maximum_files


def test_missing_entrypoint_is_refused(tmp_path: Path, policy: SkillPolicy) -> None:
    directory = tmp_path / "skill"
    write(directory / "notes.md", "# Notes\n")

    with pytest.raises(ValidationError) as caught:
        scan_skill(directory, policy)

    assert "SKILL.md" in caught.value.message


def test_empty_directory_is_refused(tmp_path: Path, policy: SkillPolicy) -> None:
    directory = tmp_path / "skill"
    directory.mkdir()

    with pytest.raises(ValidationError):
        scan_skill(directory, policy)


def test_paths_differing_only_by_case_are_refused(
    tmp_path: Path, policy: SkillPolicy
) -> None:
    directory = skill_dir(tmp_path)
    write(directory / "README.md", "# Readme\n")
    if (directory / "readme.md").exists():
        pytest.skip("this filesystem folds case, so the pair cannot be created")
    write(directory / "readme.md", "# readme\n")

    with pytest.raises(ValidationError) as caught:
        scan_skill(directory, policy)

    assert caught.value.details["paths"] == ["README.md", "readme.md"]


def test_the_case_collision_rule_holds_on_a_case_folding_filesystem(
    tmp_path: Path,
) -> None:
    """Check the rule where the pair cannot be created.

    macOS folds case by default, so the test above skips there and this one
    hands the same pair to the rule directly. The rule protects a skill written
    on Linux from being unpacked on a machine where the two paths are one file.
    """
    directory = skill_dir(tmp_path)
    entrypoint = directory / "SKILL.md"
    data = entrypoint.read_bytes()
    pair = [
        ScannedFile(
            source_path=entrypoint,
            relative_path=PurePosixPath(name),
            size=len(data),
            media_type="text/markdown",
            digest=sha256_digest_bytes(data),
        )
        for name in ("reference/Notes.md", "reference/notes.md")
    ]

    with pytest.raises(ValidationError) as caught:
        _reject_case_collisions(pair)

    assert caught.value.details["paths"] == ["reference/Notes.md", "reference/notes.md"]


def test_validate_file_refuses_a_path_outside_the_root(
    tmp_path: Path, policy: SkillPolicy
) -> None:
    directory = skill_dir(tmp_path)
    outsider = write(tmp_path / "outsider.md", "# Outside\n")

    with pytest.raises(ValidationError) as caught:
        validate_file(outsider, directory, policy)

    assert "outside" in caught.value.message


def test_validate_file_accepts_a_plain_nested_file(
    tmp_path: Path, policy: SkillPolicy
) -> None:
    directory = skill_dir(tmp_path)
    nested = write(directory / "reference" / "notes.md", "# Notes\n")

    validate_file(nested, directory, policy)


def test_an_unreadable_file_is_reported_as_a_refusal(tmp_path: Path) -> None:
    directory = skill_dir(tmp_path)
    os.symlink(tmp_path / "nowhere.md", directory / "dangling.md")
    permissive = SkillPolicy(allow_symlinks=True)

    with pytest.raises(ValidationError) as caught:
        scan_skill(directory, permissive)

    assert "cannot be read" in caught.value.message
    assert caught.value.details["path"] == "dangling.md"


def test_a_permissive_policy_can_admit_hidden_files(tmp_path: Path) -> None:
    directory = skill_dir(tmp_path)
    write(directory / ".notes.md", "# Hidden but allowed\n")
    permissive = SkillPolicy(allow_hidden_files=True)

    result = scan_skill(directory, permissive)

    assert [item.relative_path.as_posix() for item in result.files] == [
        ".notes.md",
        "SKILL.md",
    ]


# ---------------------------------------------------------------------------
# Secret scanning
# ---------------------------------------------------------------------------


BLOCKING_SAMPLES = [
    ("private_key_block", "-----BEGIN PRIVATE KEY-----"),
    ("private_key_block", "-----BEGIN OPENSSH PRIVATE KEY-----"),
    ("authorization_header", "Authorization: Bearer xxxxFAKExxxxTOKENxxxx"),
    ("authorization_header", "authorization = Basic xxxxFAKExxxxBASICxxxx"),
    ("provider_token_prefix", "use sk-xxxxxxxxFAKExxxxxxxx when calling out"),
    ("provider_token_prefix", "ghp_xxxxxxxxxxxxxxxxxxxxFAKExxxx"),
    ("provider_token_prefix", "xoxb-xxxxxxxxxxFAKExxxx"),
    ("aws_access_key_id", "AKIAXXXXXXXXXXXXFAKE"),
    ("aws_secret_assignment", "aws_secret_access_key = xxxxFAKExxxx"),
]


@pytest.mark.parametrize(("rule_id", "line"), BLOCKING_SAMPLES)
def test_credential_shapes_are_blocking(
    tmp_path: Path, rule_id: str, line: str
) -> None:
    path = write(tmp_path / "notes.md", f"# Notes\n\n{line}\n")

    findings = scan_file_for_secrets(path)

    blocking = [item for item in findings if item.severity == "blocking"]
    assert [item.rule_id for item in blocking] == [rule_id]
    assert blocking[0].line == 3


CLEAN_SAMPLES = [
    "Never paste an API key into a skill file.",
    # A Skill is prose about a procedure, and the Hello World task family is
    # about returning a token, so these are the sentences it is written in.
    "The final output must contain only that token: no reasoning, arithmetic",
    "Return exactly one token: nothing else.",
    "Authorization headers are set by the runtime, not by you.",
    "sha256:9f2c0b1d5e4a3f6b8c7d0e1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e",
]


@pytest.mark.parametrize("line", CLEAN_SAMPLES)
def test_ordinary_documentation_is_not_a_finding(tmp_path: Path, line: str) -> None:
    path = write(tmp_path / "notes.md", f"# Notes\n\n{line}\n")

    assert scan_file_for_secrets(path) == []


def test_an_opaque_run_is_a_warning_and_does_not_block(
    tmp_path: Path, policy: SkillPolicy
) -> None:
    directory = skill_dir(tmp_path)
    write(directory / "notes.md", "# Notes\n\nBuild id AAAAbbbb" + "Zz09" * 10 + "\n")

    result = scan_skill(directory, policy)

    assert [item.rule_id for item in result.secret_findings] == ["high_entropy_string"]
    assert [item.severity for item in result.secret_findings] == ["warning"]
    assert result.warnings and "notes.md:3" in result.warnings[0]


def test_a_blocking_finding_stops_the_scan(policy: SkillPolicy) -> None:
    with pytest.raises(ValidationError) as caught:
        scan_skill(INVALID_SECRET, policy)

    assert "credential" in caught.value.message
    findings = caught.value.details["findings"]
    assert isinstance(findings, list)
    assert {"path": "notes.md", "rule_id": "private_key_block", "line": 7} in findings


def test_no_refusal_repeats_the_text_that_triggered_it(policy: SkillPolicy) -> None:
    with pytest.raises(ValidationError) as caught:
        scan_skill(INVALID_SECRET, policy)

    assert FAKE_KEY_BODY not in error_text(caught.value)
    assert "BEGIN PRIVATE KEY" not in error_text(caught.value)


def test_a_finding_carries_no_matched_text(tmp_path: Path) -> None:
    path = write(tmp_path / "notes.md", "AKIAXXXXXXXXXXXXFAKE\n")

    findings = scan_file_for_secrets(path)

    assert findings
    for finding in findings:
        assert "FAKE" not in json.dumps(
            {
                "path": finding.path,
                "rule_id": finding.rule_id,
                "line": finding.line,
                "severity": finding.severity,
            }
        )


def test_findings_report_the_relative_path_not_the_participants_directory(
    tmp_path: Path, policy: SkillPolicy
) -> None:
    directory = skill_dir(tmp_path)
    write(directory / "reference" / "keys.md", "AKIAXXXXXXXXXXXXFAKE\n")

    with pytest.raises(ValidationError) as caught:
        scan_skill(directory, policy)

    assert str(tmp_path) not in error_text(caught.value)
    assert "reference/keys.md" in error_text(caught.value)


# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------


def test_scanned_file_describes_one_file(policy: SkillPolicy) -> None:
    entry = scan_skill(VALID, policy).files[0]

    assert isinstance(entry, ScannedFile)
    assert entry.relative_path == PurePosixPath("SKILL.md")
    assert entry.source_path == VALID / "SKILL.md"
    assert stat.S_ISREG(entry.source_path.stat().st_mode)
