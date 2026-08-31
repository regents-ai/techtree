"""The engine descriptor and the host-platform vocabulary. Decisions 0003 A9.

``normalize_host_platform`` is the single door every raw platform string walks
through. The tests cover the spellings a real host reports — ``aarch64`` on
Linux, ``arm64`` on macOS, ``x86_64`` and ``AMD64`` — and, more importantly,
that anything else is refused with a typed error rather than guessed at. A
wrong guess here does not fail here; it fails much later, inside an engine
install, with a message nobody can act on.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import sha256_digest_bytes
from techtree.constants import ENGINE_SCHEMA_VERSION, SUPPORTED_HOST_PLATFORMS
from techtree.errors import EXIT_PREREQUISITE, PrerequisiteError
from techtree.models.engine import (
    EngineDescriptor,
    EnginePackage,
    EngineStatus,
    normalize_host_platform,
)

PACKAGE_DIGEST = sha256_digest_bytes(b"package")


@pytest.mark.parametrize(
    ("sys_platform", "machine", "expected"),
    [
        ("darwin", "arm64", "darwin/arm64"),
        ("darwin", "aarch64", "darwin/arm64"),
        ("darwin", "x86_64", "darwin/amd64"),
        ("linux", "aarch64", "linux/arm64"),
        ("linux", "arm64", "linux/arm64"),
        ("linux", "x86_64", "linux/amd64"),
        ("linux", "amd64", "linux/amd64"),
        ("Linux", "AMD64", "linux/amd64"),
        ("  darwin ", " ARM64 ", "darwin/arm64"),
    ],
)
def test_known_hosts_normalize(sys_platform: str, machine: str, expected: str) -> None:
    assert normalize_host_platform(sys_platform, machine) == expected


@pytest.mark.parametrize(
    ("sys_platform", "machine"),
    [
        ("win32", "amd64"),
        ("freebsd", "x86_64"),
        ("linux", "riscv64"),
        ("darwin", "ppc64le"),
        ("", ""),
        ("linux/amd64", ""),
    ],
)
def test_unsupported_hosts_raise_a_typed_error(sys_platform: str, machine: str) -> None:
    with pytest.raises(PrerequisiteError) as caught:
        normalize_host_platform(sys_platform, machine)

    assert caught.value.code == "unsupported_host_platform"
    assert caught.value.exit_code == EXIT_PREREQUISITE
    assert caught.value.details["sys_platform"] == sys_platform
    assert caught.value.details["machine"] == machine


def test_the_vocabulary_is_exactly_four_names() -> None:
    normalized = {
        normalize_host_platform(operating_system, architecture)
        for operating_system in ("darwin", "linux")
        for architecture in ("arm64", "amd64")
    }

    assert normalized == set(SUPPORTED_HOST_PLATFORMS)


def descriptor(**overrides: object) -> EngineDescriptor:
    """Build an engine descriptor listing the whole host vocabulary."""
    fields: dict[str, object] = {
        "schema_version": ENGINE_SCHEMA_VERSION,
        "name": "default",
        "python_version": "3.12",
        "verifiers_version": "0.1.0",
        "verifiers_revision": "7e1c47d24d055aae587ee8259f77a3e8e193513a",
        "supported_hosts": list(SUPPORTED_HOST_PLATFORMS),
        "packages": [
            EnginePackage(
                name="procedure-transfer-v1",
                version="1",
                source_digest=PACKAGE_DIGEST,
            )
        ],
    }
    fields.update(overrides)
    return EngineDescriptor(**fields)  # type: ignore[arg-type]


def test_the_initial_descriptor_lists_all_four_hosts() -> None:
    assert descriptor().supported_hosts == list(SUPPORTED_HOST_PLATFORMS)


def test_descriptor_rejects_a_host_outside_the_vocabulary() -> None:
    with pytest.raises(PydanticValidationError):
        descriptor(supported_hosts=["macos-arm64"])


def test_descriptor_rejects_a_repeated_host() -> None:
    with pytest.raises(PydanticValidationError, match="must not repeat"):
        descriptor(supported_hosts=["darwin/arm64", "darwin/arm64"])


def test_descriptor_rejects_an_empty_host_list() -> None:
    with pytest.raises(PydanticValidationError, match="at least one host"):
        descriptor(supported_hosts=[])


def test_descriptor_does_not_contain_its_own_digest() -> None:
    assert "digest" not in EngineDescriptor.model_fields


def test_an_absent_engine_cannot_be_active_or_verified() -> None:
    with pytest.raises(PydanticValidationError, match="cannot be active or verified"):
        EngineStatus(
            digest=PACKAGE_DIGEST,
            installed=False,
            active=True,
            verified=False,
            path="/nowhere",
            python_executable=None,
            detail="not installed",
        )
