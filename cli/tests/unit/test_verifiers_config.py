"""The allow-list that bounds what Techtree may ask Verifiers to do. Spec §6.7.

Every test here asks the same question from a different direction: can a
document that would spoil the experiment be spelled at all? A validator that
merely reports a bad value still lets a caller construct one and forget to
check; a literal type means the bad document has no representation. The tests
that matter most are therefore the ones that expect a construction to fail.
"""

from __future__ import annotations

import tomllib

import pytest
from pydantic import ValidationError as PydanticValidationError

from techtree.verifiers.config import (
    OPEN_NETWORK,
    DockerRuntimeToml,
    EnvToml,
    EvalClientToml,
    EvalToml,
    HermesHarnessToml,
    SamplingToml,
    SubjectAgentToml,
    TasksetToml,
    config_to_toml_bytes,
)

PINNED_IMAGE = f"ghcr.io/techtree/subject@sha256:{'a' * 64}"
SKILL_DIR = "/runs/run_x/inputs/skill/files/sha256-" + "b" * 64


def docker_runtime(**overrides: object) -> DockerRuntimeToml:
    fields: dict[str, object] = {
        "image": PINNED_IMAGE,
        "allow": [],
        "block": [],
        "cpu": 2.0,
        "memory": 4.0,
    }
    fields.update(overrides)
    return DockerRuntimeToml.model_validate(fields)


def subject(**overrides: object) -> SubjectAgentToml:
    fields: dict[str, object] = {
        "harness": HermesHarnessToml(version="0.19.0", skills=[SKILL_DIR]),
        "runtime": docker_runtime(),
    }
    fields.update(overrides)
    return SubjectAgentToml.model_validate(fields)


def eval_config(**overrides: object) -> EvalToml:
    fields: dict[str, object] = {
        "model": "vendor/small-instruct",
        "client": EvalClientToml(api_key_var="PRIME_API_KEY"),
        "sampling": SamplingToml(temperature=0.0, max_tokens=512),
        "env": EnvToml(
            taskset=TasksetToml(id="procedure-transfer-v1"), subject=subject()
        ),
        "num_tasks": 36,
        "max_concurrent": 4,
        "output_dir": "/runs/run_x/verifiers/baseline/run",
    }
    fields.update(overrides)
    return EvalToml.model_validate(fields)


# ---------------------------------------------------------------------------
# The settings that must not be spellable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("push", True),
        ("rich", True),
        ("shuffle", True),
        ("num_rollouts", 2),
    ],
)
def test_the_settings_that_would_spoil_a_run_have_no_representation(
    field: str, value: object
) -> None:
    with pytest.raises(PydanticValidationError):
        eval_config(**{field: value})


def test_a_bundled_skill_catalogue_cannot_be_requested() -> None:
    with pytest.raises(PydanticValidationError):
        HermesHarnessToml.model_validate(
            {"version": "0.19.0", "use_bundled_skill": True}
        )


def test_disabled_tools_is_not_a_field_a_compiled_harness_has() -> None:
    # The native Hermes harness accepts this at config time and refuses it
    # mid-run, so the only safe rejection is at construction.
    with pytest.raises(PydanticValidationError):
        HermesHarnessToml.model_validate(
            {"version": "0.19.0", "disabled_tools": ["bash"]}
        )


def test_a_harness_other_than_hermes_cannot_be_named() -> None:
    with pytest.raises(PydanticValidationError):
        HermesHarnessToml.model_validate({"id": "bash", "version": "0.19.0"})


def test_a_runtime_other_than_docker_cannot_be_named() -> None:
    with pytest.raises(PydanticValidationError):
        docker_runtime(type="subprocess")


def test_an_unknown_key_anywhere_is_refused() -> None:
    with pytest.raises(PydanticValidationError):
        eval_config(server=True)


# ---------------------------------------------------------------------------
# Credentials and headers
# ---------------------------------------------------------------------------


def test_the_client_names_a_variable_and_never_a_value() -> None:
    with pytest.raises(PydanticValidationError):
        EvalClientToml(api_key_var="sk-live-not-a-variable-name")


def test_the_client_declares_no_headers_of_its_own() -> None:
    with pytest.raises(PydanticValidationError):
        EvalClientToml(api_key_var="PRIME_API_KEY", headers={"X-Prime-Team-ID": "t"})


def test_the_base_url_is_omitted_so_the_pinned_client_resolves_it() -> None:
    client = EvalClientToml(api_key_var="PRIME_API_KEY")
    assert client.base_url is None
    assert "base_url" not in client.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------------------
# Paths, bounds and the network policy
# ---------------------------------------------------------------------------


def test_a_relative_output_directory_is_refused() -> None:
    with pytest.raises(PydanticValidationError):
        eval_config(output_dir="outputs/baseline")


def test_a_relative_skill_path_is_refused() -> None:
    with pytest.raises(PydanticValidationError):
        HermesHarnessToml(version="0.19.0", skills=["skill/files/candidate"])


def test_the_same_skill_cannot_be_mounted_twice() -> None:
    with pytest.raises(PydanticValidationError):
        HermesHarnessToml(version="0.19.0", skills=[SKILL_DIR, SKILL_DIR])


def test_agent_concurrency_cannot_exceed_the_episode_bound() -> None:
    with pytest.raises(PydanticValidationError):
        eval_config(
            max_concurrent=1,
            env=EnvToml(
                taskset=TasksetToml(id="procedure-transfer-v1"),
                subject=subject(),
                max_concurrent_agents=2,
            ),
        )


def test_an_empty_allow_list_is_how_a_restricted_runtime_is_spelled() -> None:
    restricted = docker_runtime(allow=[], block=[])
    assert restricted.network_is_restricted is True
    assert docker_runtime(allow=list(OPEN_NETWORK)).network_is_restricted is False


def test_a_concrete_allow_list_and_a_block_list_cannot_be_combined() -> None:
    with pytest.raises(PydanticValidationError):
        docker_runtime(allow=["registry.example"], block=["example.test"])


def test_a_digest_pinned_image_is_recognised_and_a_tagged_one_is_not() -> None:
    assert docker_runtime().image_is_digest_pinned is True
    assert docker_runtime(image="python:3.12-slim").image_is_digest_pinned is False


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_the_same_configuration_always_serializes_to_the_same_bytes() -> None:
    assert config_to_toml_bytes(eval_config()) == config_to_toml_bytes(eval_config())


def test_the_emitted_document_reads_back_as_the_engine_would_read_it() -> None:
    document = tomllib.loads(config_to_toml_bytes(eval_config()).decode("utf-8"))

    assert document["push"] is False
    assert document["rich"] is False
    assert document["shuffle"] is False
    assert document["num_rollouts"] == 1
    assert document["env"]["subject"]["harness"]["use_bundled_skill"] is False
    assert "disabled_tools" not in document["env"]["subject"]["harness"]
    assert "base_url" not in document["client"]


def test_optional_bounds_are_absent_rather_than_null() -> None:
    # TOML cannot represent a null, and the engine drops None the same way, so
    # an unset bound must not appear in either document.
    document = tomllib.loads(config_to_toml_bytes(eval_config()).decode("utf-8"))
    assert "max_turns" not in document["env"]["subject"]
    assert "max_total_tokens" not in document["env"]["subject"]
