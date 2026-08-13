"""The gate in front of a real evaluation. Spec section 6.18.

Two of these checks shell out to Docker and are therefore only asserted on
where the answer does not depend on the machine. The rest are pure questions
about a Campaign, a credential name, and an engine directory, and those are
where the interesting rules live: a placeholder Campaign must be refused, and
evaluation authentication must be diagnosed as its own thing rather than folded
into "is the host set up".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.verifiers.support import (
    SUBJECT_MODEL_ID,
    local_campaign,
    shipped_campaign,
)
from techtree.doctor.execution_checks import (
    check_engine_eval,
    check_live_campaign,
    check_prime_auth,
    check_subject_image,
    execution_checks,
)
from techtree.doctor.service import DoctorService
from techtree.engines.registry import EngineRegistry
from techtree.models.campaign import SUBJECT_AGENT, CampaignSpec, RuntimeSpec
from techtree.models.cli import CheckStatus
from techtree.paths import paths_from_root
from techtree.settings import Settings


def executable_campaign() -> CampaignSpec:
    """Return the same Campaign with real subject coordinates."""
    return local_campaign().campaign


def registry(home: Path) -> EngineRegistry:
    """An engine registry over an empty Techtree home."""
    return EngineRegistry(paths_from_root(home), Settings())


# ---------------------------------------------------------------------------
# The Campaign
# ---------------------------------------------------------------------------


def test_the_shipped_campaign_is_refused_for_a_real_run() -> None:
    check = check_live_campaign(shipped_campaign())

    assert check.status is CheckStatus.FAIL
    assert check.blocking


def test_the_refusal_names_which_coordinates_are_placeholders() -> None:
    """The subject model is still a placeholder; the container is not.

    Decisions document 0007 R5 pins the shipped Campaign's image by content,
    so the only coordinate left waiting on the founder is which model answers.
    """
    check = check_live_campaign(shipped_campaign())

    assert "model_id=development-placeholder" in check.detail
    assert "image=" not in check.detail


def test_a_campaign_with_real_coordinates_is_executable() -> None:
    check = check_live_campaign(executable_campaign())

    assert check.status is CheckStatus.PASS
    assert not check.blocking
    assert SUBJECT_MODEL_ID in check.detail


# ---------------------------------------------------------------------------
# The credential
# ---------------------------------------------------------------------------


def test_a_present_credential_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRIME_API_KEY", "sk-doctor-unit-test-secret")
    subject = executable_campaign().agents[SUBJECT_AGENT]

    check = check_prime_auth(subject.model)

    assert check.status is CheckStatus.PASS


def test_an_absent_credential_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRIME_API_KEY", raising=False)
    monkeypatch.setenv("HOME", "/nonexistent-home-for-this-check")
    subject = executable_campaign().agents[SUBJECT_AGENT]

    check = check_prime_auth(subject.model)

    assert check.status is CheckStatus.FAIL
    assert check.blocking


def test_the_credential_check_says_it_is_not_the_operators_own_sign_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Confusing evaluation auth with host auth is the failure that costs the
    # most: everything looks configured until the first model call.
    monkeypatch.delenv("PRIME_API_KEY", raising=False)
    monkeypatch.setenv("HOME", "/nonexistent-home-for-this-check")
    subject = executable_campaign().agents[SUBJECT_AGENT]

    check = check_prime_auth(subject.model)

    assert "your own agent" in check.detail


def test_no_credential_value_reaches_the_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "sk-doctor-unit-test-secret"
    monkeypatch.setenv("PRIME_API_KEY", secret)
    subject = executable_campaign().agents[SUBJECT_AGENT]

    check = check_prime_auth(subject.model)

    assert secret not in check.model_dump_json()


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------


def test_no_active_engine_blocks_a_real_run(temp_techtree_home: Path) -> None:
    check = check_engine_eval(registry(temp_techtree_home))

    assert check.status is CheckStatus.FAIL
    assert check.blocking


def test_an_engine_that_is_not_installed_blocks(temp_techtree_home: Path) -> None:
    check = check_engine_eval(registry(temp_techtree_home), f"sha256:{'c' * 64}")

    assert check.status is CheckStatus.FAIL
    assert "not installed" in check.detail


# ---------------------------------------------------------------------------
# The image
# ---------------------------------------------------------------------------


def test_an_image_that_is_not_present_locally_blocks() -> None:
    runtime = RuntimeSpec(
        type="docker",
        image=f"techtree-nothing-has-this-name@sha256:{'d' * 64}",
        supported_platforms=["linux/amd64", "linux/arm64"],
        image_platform_digests={
            "linux/amd64": f"sha256:{'e' * 64}",
            "linux/arm64": f"sha256:{'f' * 64}",
        },
        cpu=2.0,
        memory_gb=4.0,
        network_policy="restricted",
    )

    check = check_subject_image(runtime)

    assert check.status is CheckStatus.FAIL
    assert check.blocking
    # Pulling is an explicit setup step, never something a check does quietly.
    assert "pull it" in check.detail
    assert check.metadata["pull"] == f"docker pull {runtime.image}"


# ---------------------------------------------------------------------------
# The whole set
# ---------------------------------------------------------------------------


def test_without_a_campaign_only_the_machine_questions_are_asked(
    temp_techtree_home: Path,
) -> None:
    checks = execution_checks(engine_registry=registry(temp_techtree_home))

    assert [check.id for check in checks] == [
        "execution_docker_platform",
        "execution_engine_eval",
    ]


def test_with_a_campaign_the_subject_questions_are_asked_too(
    temp_techtree_home: Path,
) -> None:
    checks = execution_checks(
        engine_registry=registry(temp_techtree_home),
        campaign=executable_campaign(),
    )

    assert [check.id for check in checks] == [
        "execution_docker_platform",
        "execution_engine_eval",
        "execution_live_campaign",
        "execution_model_credential",
        "execution_subject_image",
    ]


# ---------------------------------------------------------------------------
# What Doctor does with them
# ---------------------------------------------------------------------------


def test_an_ordinary_doctor_asks_none_of_these(temp_techtree_home: Path) -> None:
    # Somebody browsing Climbs is not about to spend money, and telling them
    # their machine is broken would be answering a question they did not ask.
    service = DoctorService(paths_from_root(temp_techtree_home), Settings())

    identifiers = {check.id for check in service.run()}

    assert not any(name.startswith("execution_") for name in identifiers)


def test_the_evaluation_doctor_treats_a_missing_engine_as_a_stop(
    temp_techtree_home: Path,
) -> None:
    service = DoctorService(paths_from_root(temp_techtree_home), Settings())

    checks = service.run(for_evaluation=True)
    blocking = {check.id for check in service.blocking_failures(checks)}

    assert "execution_engine_eval" in blocking


def test_a_host_that_cannot_run_anything_is_not_told_it_is_ready(
    temp_techtree_home: Path,
) -> None:
    service = DoctorService(paths_from_root(temp_techtree_home), Settings())
    checks = service.run(for_evaluation=True, campaign=shipped_campaign())

    reasons = " ".join(action.reason or "" for action in service.next_actions(checks))

    assert "This host is ready" not in reasons
