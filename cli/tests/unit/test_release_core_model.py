"""The ReleaseCore document and what makes its coordinates real.

Spec section 6.6, decisions document 0026. A ReleaseCore is a contract: every
coordinate in it is one a person chose, and the schema is what makes that true
rather than a convention someone has to remember. So these tests take each kind
of coordinate — a version, an identifier, a digest, an address — and check that
the schema admits the real spelling and nothing that only looks like one.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from techtree.errors import ValidationError
from techtree.release.document import (
    document_digest,
    is_canonical_document,
    parse_release_core,
    render_document,
    render_release_core,
)
from techtree.release.models import (
    ReleaseCore,
    ReleaseInputs,
    object_url_digest,
)

REAL_DIGEST = "sha256:" + "a1" * 32
OTHER_DIGEST = "sha256:" + "b2" * 32
FILE_DIGEST = "sha256:" + "c3" * 32
REAL_OBJECT_URL = f"https://techtree.sh/api/v1/objects/{FILE_DIGEST}"


def coordinates() -> dict[str, Any]:
    """Return one complete ReleaseCore, every coordinate concrete."""
    return {
        "schema_version": "techtree.release-core.v1",
        "release_id": "climb-v0.1.0",
        "cli_version": "0.1.0",
        "protocol_version": "v1alpha1",
        "engine_digest": REAL_DIGEST,
        "catalog_digest": OTHER_DIGEST,
        "intro_climb_reference": "hello-world-climb@1",
        "starter_skill_digest": REAL_DIGEST,
        "starter_skill_object_url": REAL_OBJECT_URL,
        "skill_improver_digest": REAL_DIGEST,
        "minimum_host_hermes_version": "0.19.0",
        "maximum_tested_host_hermes_version": "0.19.3",
        "subject_hermes_version": "0.19.0",
    }


def core(**overrides: Any) -> ReleaseCore:
    """Build a ReleaseCore, overriding any field."""
    return ReleaseCore(**{**coordinates(), **overrides})


def test_a_release_names_its_coordinates_and_nothing_about_its_artifacts() -> None:
    """The document says which release this is, never which build (0026)."""
    assert core().release_id == "climb-v0.1.0"
    assert set(core().model_dump()) == set(coordinates())


@pytest.mark.parametrize(
    "field",
    [
        "release_id",
        "cli_version",
        "protocol_version",
        "engine_digest",
        "catalog_digest",
        "intro_climb_reference",
        "starter_skill_digest",
        "starter_skill_object_url",
        "skill_improver_digest",
        "minimum_host_hermes_version",
        "maximum_tested_host_hermes_version",
        "subject_hermes_version",
    ],
)
def test_every_coordinate_is_required(field: str) -> None:
    incomplete = {name: v for name, v in coordinates().items() if name != field}
    with pytest.raises(PydanticValidationError):
        ReleaseCore.model_validate(incomplete)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("0.0.0-placeholder", id="unchosen"),
        pytest.param("", id="empty"),
        pytest.param("latest", id="moving"),
        pytest.param("0.1", id="two numbers"),
        pytest.param("v0.1.0", id="prefixed"),
    ],
)
def test_a_version_is_three_numbers(value: str) -> None:
    with pytest.raises(PydanticValidationError):
        core(cli_version=value)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("0.0.0-placeholder", id="a version, not a name"),
        pytest.param("", id="empty"),
        pytest.param("Climb-v0.1.0", id="uppercase"),
        pytest.param("climb v0.1.0", id="whitespace"),
    ],
)
def test_a_release_identifier_is_a_name(value: str) -> None:
    with pytest.raises(PydanticValidationError):
        core(release_id=value)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("sha256:" + "0" * 64, id="zeroed"),
        pytest.param("", id="empty"),
        pytest.param("sha256:" + "a" * 63, id="short"),
        pytest.param("sha256:" + "A" * 64, id="uppercase"),
        pytest.param("a" * 64, id="unprefixed"),
    ],
)
def test_a_digest_is_a_measurement(value: str) -> None:
    with pytest.raises(PydanticValidationError):
        core(engine_digest=value)


def test_a_digest_of_almost_all_zeros_is_still_a_measurement() -> None:
    """Only *nothing* hashes to zero; a leading run of zeros is ordinary."""
    assert core(engine_digest="sha256:" + "0" * 63 + "1").engine_digest.endswith("1")


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("https://placeholder.invalid/unchosen", id="unresolvable"),
        pytest.param(
            f"https://placeholder.invalid/objects/{FILE_DIGEST}",
            id="unresolvable content address",
        ),
        pytest.param(
            "https://techtree.sh/objects/SKILL.md", id="not content addressed"
        ),
        pytest.param(f"http://techtree.sh/objects/{FILE_DIGEST}", id="plaintext"),
        pytest.param(f"techtree.sh/objects/{FILE_DIGEST}", id="no scheme"),
        pytest.param(f"/objects/{FILE_DIGEST}", id="relative"),
        pytest.param("https://techtree.sh", id="bare host"),
        pytest.param(f"https://techtree.sh/a b/{FILE_DIGEST}", id="whitespace"),
        pytest.param(f"https://techtree.sh/{FILE_DIGEST}\n", id="trailing newline"),
        pytest.param("", id="empty"),
        pytest.param(f"https://user:token@techtree.sh/{FILE_DIGEST}", id="userinfo"),
        pytest.param(f"https://token@techtree.sh/{FILE_DIGEST}", id="bare userinfo"),
    ],
)
def test_a_starter_skill_address_that_is_not_one_exact_object_is_refused(
    value: str,
) -> None:
    """Spec section 4.1: an exact read-only object URL, or no coordinate.

    The address is a content address, so it ends in the digest of the bytes it
    returns and a fetcher can check a response before it trusts any of it.
    Userinfo is refused for a reason of its own: the coordinate is copied into
    the plugin, the website and an approval packet, so an address that can
    carry a credential is an address that can leak one.
    """
    with pytest.raises(PydanticValidationError):
        core(starter_skill_object_url=value)


def test_a_path_may_still_contain_an_at_sign() -> None:
    """Only the authority is constrained; a versioned path is an ordinary one."""
    url = f"https://techtree.sh/objects/starter@1/{FILE_DIGEST}"
    assert core(starter_skill_object_url=url).starter_skill_object_url == url


def test_the_address_says_which_bytes_it_serves() -> None:
    assert object_url_digest(REAL_OBJECT_URL) == FILE_DIGEST


def test_an_address_that_promises_nothing_says_so() -> None:
    with pytest.raises(ValueError, match="not keyed by the digest"):
        object_url_digest("https://techtree.sh/objects/SKILL.md")


def test_an_unknown_field_is_refused() -> None:
    with pytest.raises(PydanticValidationError):
        ReleaseCore.model_validate(
            {**coordinates(), "website_origin": "https://techtree.sh"}
        )


# ---------------------------------------------------------------------------
# Stored bytes
# ---------------------------------------------------------------------------


def test_stored_bytes_round_trip_exactly() -> None:
    raw = render_release_core(core())
    assert render_release_core(parse_release_core(raw)) == raw


def test_stored_bytes_are_sorted_indented_and_newline_terminated() -> None:
    raw = render_release_core(core())
    text = raw.decode("utf-8")
    assert text.endswith("}\n")
    assert '\n  "catalog_digest"' in text
    assert text.index('"catalog_digest"') < text.index('"cli_version"')


def test_a_reindented_document_is_not_the_published_spelling() -> None:
    raw = render_release_core(core())
    assert is_canonical_document(raw)
    assert not is_canonical_document(raw.replace(b"\n  ", b"\n    "))


def test_the_digest_is_taken_over_the_file_bytes() -> None:
    raw = render_release_core(core())
    assert document_digest(raw) != document_digest(raw + b"\n")


def test_a_document_that_is_not_a_release_core_is_a_typed_failure() -> None:
    with pytest.raises(ValidationError, match="not a valid ReleaseCore"):
        parse_release_core(b'{"schema_version": "techtree.release-core.v1"}')


def test_render_document_refuses_nothing_it_can_spell() -> None:
    assert render_document({"b": 1, "a": [True, None]}) == (
        b'{\n  "a": [\n    true,\n    null\n  ],\n  "b": 1\n}\n'
    )


# ---------------------------------------------------------------------------
# Founder-owned inputs
# ---------------------------------------------------------------------------


def founder_inputs() -> dict[str, Any]:
    """Return one complete set of founder-owned release decisions."""
    return {
        "schema_version": "techtree.release-inputs.v1",
        "release_id": "climb-v0.1.0",
        "cli_version": "0.1.0",
        "intro_climb_reference": "hello-world-climb@1",
        "starter_skill_digest": REAL_DIGEST,
        "starter_skill_object_url": REAL_OBJECT_URL,
        "skill_improver_digest": REAL_DIGEST,
        "minimum_host_hermes_version": "0.19.0",
        "maximum_tested_host_hermes_version": "0.19.3",
    }


def test_release_inputs_accept_only_founder_decisions() -> None:
    assert ReleaseInputs.model_validate(founder_inputs()).cli_version == "0.1.0"


def test_release_inputs_reject_a_derived_coordinate() -> None:
    with pytest.raises(PydanticValidationError):
        ReleaseInputs.model_validate({**founder_inputs(), "engine_digest": REAL_DIGEST})


def test_release_inputs_hold_only_chosen_values() -> None:
    with pytest.raises(PydanticValidationError):
        ReleaseInputs.model_validate(
            {**founder_inputs(), "cli_version": "0.0.0-placeholder"}
        )
