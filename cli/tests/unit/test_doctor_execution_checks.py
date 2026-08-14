"""The gate in front of a real evaluation. Spec section 6.18.

Two of these checks shell out to Docker and are therefore only asserted on
where the answer does not depend on the machine. The rest are pure questions
about a Campaign, a credential name, and an engine directory, and those are
where the interesting rules live: a placeholder Campaign must be refused, and
evaluation authentication must be diagnosed as its own thing rather than folded
into "is the host set up".
"""

from __future__ import annotations

import json
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
from techtree.models.cli import CheckStatus, DoctorCheck
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
#
# Six states, one table. The check must answer for the environment a detached
# run would be given, so a credential exported in this terminal is never one of
# the things that makes it ready — and the terminal it was typed into is the
# one place an operator will have put it.
# ---------------------------------------------------------------------------

SECRET = "sk-doctor-unit-test-never-a-real-key"


def prime_login(home: Path, *, api_key: str | None = SECRET) -> None:
    """Write the configuration a Prime CLI sign-in leaves behind."""
    config = home / ".prime" / "config.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({} if api_key is None else {"api_key": api_key}))


def credential_check() -> DoctorCheck:
    """Run the credential check against the shipped subject's model."""
    return check_prime_auth(executable_campaign().agents[SUBJECT_AGENT].model)


def test_a_valid_prime_login_is_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("PRIME_API_KEY", raising=False)
    prime_login(tmp_path)

    check = credential_check()

    assert check.status is CheckStatus.PASS
    assert not check.blocking
    assert check.metadata["source"] == "prime_config"


def test_an_exported_variable_alone_is_not_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The whole point of the check. A run is a separate background process that
    # is not given this terminal's variables, so an export is not readiness.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PRIME_API_KEY", SECRET)

    check = credential_check()

    assert check.status is CheckStatus.FAIL
    assert check.blocking
    assert check.metadata["exported_in_this_terminal"] is True
    assert "set in this terminal" in check.detail
    assert "nothing exported here can reach it" in check.detail
    assert SECRET not in check.model_dump_json()


def test_a_prime_login_is_ready_even_when_a_variable_is_also_exported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PRIME_API_KEY", SECRET)
    prime_login(tmp_path)

    check = credential_check()

    assert check.status is CheckStatus.PASS
    # Ready through the sign-in, which is the only one of the two a run reads.
    assert check.metadata["source"] == "prime_config"
    assert SECRET not in check.model_dump_json()


def test_neither_a_prime_login_nor_a_variable_is_not_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("PRIME_API_KEY", raising=False)

    check = credential_check()

    assert check.status is CheckStatus.FAIL
    assert check.blocking
    assert check.metadata["source"] == "missing"
    assert check.metadata["exported_in_this_terminal"] is False
    # Evaluation auth is not host auth, and this is where a person meets that.
    assert "your own agent" in check.detail


def test_a_prime_configuration_that_holds_no_key_is_not_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # What a cleared or expired sign-in leaves behind: the configuration is
    # there, and it supplies nothing.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("PRIME_API_KEY", raising=False)
    prime_login(tmp_path, api_key="")

    check = credential_check()

    assert check.status is CheckStatus.FAIL
    assert check.blocking
    assert check.metadata["source"] == "missing"
    assert "signed out" in check.detail


def test_a_malformed_prime_configuration_is_a_typed_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A broken store is its own answer. Telling somebody who has signed in that
    # they have not sends them round the loop again.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("PRIME_API_KEY", raising=False)
    config = tmp_path / ".prime" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text("{not json at all")

    check = credential_check()

    assert check.status is CheckStatus.FAIL
    assert check.blocking
    assert check.metadata["source"] == "malformed_prime_config"
    assert "could not be read" in check.detail


def test_no_credential_value_reaches_the_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PRIME_API_KEY", SECRET)
    prime_login(tmp_path)

    check = credential_check()

    assert SECRET not in check.model_dump_json()


def test_the_repair_for_a_missing_credential_leads_with_signing_in(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Exporting the variable is the repair a person reaches for by themselves,
    # and it does not work; the offered one has to be the one that does.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PRIME_API_KEY", SECRET)
    service = DoctorService(paths_from_root(tmp_path / "techtree"), Settings())

    actions = service.next_actions([credential_check()])

    assert actions[0].cli == ["prime", "login"]
    assert "doctor --for-evaluation" in (actions[0].reason or "")


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
