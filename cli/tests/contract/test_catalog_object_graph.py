"""The resolved Climb graph. Spec sections 14 and 27.3, decisions 0003 A2/A4.

The packaged catalog of this build is valid and empty, so these tests resolve a
complete synthetic catalog instead. It is built by
``tests/fixtures/catalog/build_complete.py``, its digests are computed from the
real contents of the real files, and the first test here fails if the committed
fixture is not exactly what that script produces.

What is being tested is a chain of trust rather than a parser. The index says a
file contains a particular object; the repository proves it by recomputing the
digest. The Climb says it wraps a particular Campaign; the graph proves it by
comparing digests rather than names. So each negative test breaks exactly one
link — a path, a kind, a digest, a rights promise — and expects the specific
typed failure that link is protected by.

The CLI is exercised from both ends: against the complete fixture, so that a
populated listing and a full ``show`` are rendered and validated, and against
the real packaged catalog, which is empty and must say so usefully.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from typer.testing import CliRunner

from techtree.canonical import canonical_json_bytes, digest_object, sha256_digest_bytes
from techtree.catalog.repository import EmbeddedCatalogRepository
from techtree.catalog.service import (
    CatalogService,
    HostInfo,
    InstalledEngineStatus,
    current_host_info,
)
from techtree.cli.app import create_app
from techtree.errors import (
    EXIT_NOT_FOUND,
    EXIT_OK,
    NotFoundError,
    PolicyError,
    ValidationError,
    VerificationError,
)
from techtree.models.catalog import ClimbSummary, EngineCompatibilityStatus
from techtree.paths import TechtreePaths, paths_from_root

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "catalog"
COMPLETE_FIXTURE = FIXTURE_ROOT / "complete"

#: A host Techtree supports, stated rather than detected so that the answers
#: these tests assert on do not depend on the machine running them.
SUPPORTED_HOST = HostInfo(
    operating_system="linux", architecture="x86_64", python_version="3.12.0"
)


def builder() -> ModuleType:
    """Import the fixture builder from the fixtures tree.

    ``tests/fixtures`` is data rather than an importable package, so the
    builder is loaded by path — the same way the schema tests load the
    exporter. Importing it is what lets a test compose a deliberately broken
    variant of the fixture out of the same pieces the good one is made of.
    """
    location = FIXTURE_ROOT / "build_complete.py"
    spec = importlib.util.spec_from_file_location("techtree_catalog_fixture", location)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before execution because a dataclass defined in the module
    # resolves its own annotations through ``sys.modules``.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def catalog_root(tmp_path: Path) -> Path:
    """Return a writable copy of the complete fixture."""
    destination = tmp_path / "catalog"
    shutil.copytree(COMPLETE_FIXTURE, destination)
    return destination


@pytest.fixture
def paths(temp_techtree_home: Path) -> TechtreePaths:
    """Return paths under an isolated home with no engine installed."""
    return paths_from_root(temp_techtree_home)


@pytest.fixture
def service(catalog_root: Path, paths: TechtreePaths) -> CatalogService:
    """Return a service over the complete fixture on a supported host."""
    return CatalogService(
        EmbeddedCatalogRepository(catalog_root),
        SUPPORTED_HOST,
        InstalledEngineStatus(paths),
    )


def read_index(root: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((root / "catalog.json").read_text("utf-8"))
    return document


def write_index(root: Path, document: dict[str, Any]) -> None:
    (root / "catalog.json").write_text(
        json.dumps(document, indent=2, sort_keys=True), encoding="utf-8"
    )


def edit_index(root: Path, edit: Callable[[dict[str, Any]], None]) -> None:
    """Apply one change to the committed index of a fixture copy."""
    document = read_index(root)
    edit(document)
    write_index(root, document)


def repository(root: Path) -> EmbeddedCatalogRepository:
    return EmbeddedCatalogRepository(root)


# ---------------------------------------------------------------------------
# The fixture itself
# ---------------------------------------------------------------------------


def test_the_committed_fixture_is_exactly_what_the_builder_produces(
    tmp_path: Path,
) -> None:
    """A fixture nobody can regenerate is a fixture nobody can trust."""
    rebuilt = tmp_path / "rebuilt"
    builder().build(rebuilt)

    committed = sorted(
        path.relative_to(COMPLETE_FIXTURE)
        for path in COMPLETE_FIXTURE.rglob("*")
        if path.is_file()
    )
    produced = sorted(
        path.relative_to(rebuilt) for path in rebuilt.rglob("*") if path.is_file()
    )
    assert committed == produced

    for relative in committed:
        assert (COMPLETE_FIXTURE / relative).read_bytes() == (
            rebuilt / relative
        ).read_bytes(), f"{relative} is not what the builder produces"


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def test_a_climb_resolves_its_campaign_data_policy_and_receipt(
    service: CatalogService,
) -> None:
    resolved = service.get_climb("synthetic-open@1")

    assert resolved.climb.metadata.slug == "synthetic-open"
    assert resolved.climb.campaign_spec_digest == resolved.campaign_digest
    assert resolved.campaign.data_policy_digest == resolved.data_policy_digest
    assert resolved.campaign.taskset.validation_receipt_digest == (
        resolved.publisher_validation_digest
    )
    assert resolved.publisher_validation.status == "valid"


def test_every_digest_in_the_resolved_graph_verifies(service: CatalogService) -> None:
    """Each object hashes to the digest the graph reached it by."""
    resolved = service.get_climb("synthetic-open@1")

    assert digest_object(resolved.climb) == resolved.climb_digest
    assert digest_object(resolved.campaign) == resolved.campaign_digest
    assert digest_object(resolved.data_policy) == resolved.data_policy_digest
    assert digest_object(resolved.publisher_validation) == (
        resolved.publisher_validation_digest
    )


def test_the_shipped_validation_evidence_resolves_and_matches_the_receipt(
    catalog_root: Path, service: CatalogService
) -> None:
    """Decisions 0003 A4: a referenced artifact is reachable, or not referenced."""
    resolved = service.get_climb("synthetic-open@1")
    reference = resolved.publisher_validation.normalized_evidence
    assert reference is not None

    evidence = repository(catalog_root).load_validation_evidence(reference.digest)

    assert evidence.taskset_lock_digest == (
        resolved.publisher_validation.taskset_lock_digest
    )
    assert [task.task_hash for task in evidence.tasks] == (
        resolved.campaign.taskset.membership.ordered_task_hashes
    )


def test_a_reference_resolves_by_slug_by_version_and_by_public_identifier(
    service: CatalogService, catalog_root: Path
) -> None:
    by_version = service.get_climb("synthetic-open@1")
    by_slug = service.get_climb("synthetic-open")
    by_id = repository(catalog_root).load_climb(by_version.climb.metadata.id)

    assert by_slug.climb_digest == by_version.climb_digest
    assert by_id.metadata.slug == "synthetic-open"


def test_an_unknown_reference_names_what_the_catalog_does_ship(
    service: CatalogService,
) -> None:
    with pytest.raises(NotFoundError) as failure:
        service.get_climb("no-such-climb")

    assert failure.value.code == "climb_not_found"
    assert "synthetic-open@1" in failure.value.details["available"]  # type: ignore[operator]


def test_listing_defaults_to_what_a_reader_could_enter(service: CatalogService) -> None:
    """Available means open plus the development fixtures, never closed."""
    available = [summary.reference for summary in service.list_climbs()]
    everything = [summary.reference for summary in service.list_climbs(status="all")]

    assert available == ["synthetic-open@1", "synthetic-development@1"]
    assert "synthetic-closed@1" in everything


def test_an_object_can_be_read_as_a_document_and_still_be_verified(
    catalog_root: Path,
) -> None:
    """Reading an object untyped does not mean reading it unchecked."""
    digest = _digest_of_kind(read_index(catalog_root), "data_policy")

    document = repository(catalog_root).load_object(digest)

    assert isinstance(document, dict)
    assert document["schema_version"] == "techtree.data-policy.v1alpha1"

    (catalog_root / "data-policies" / "synthetic.json").write_bytes(
        canonical_json_bytes({**document, "version": 2})
    )
    with pytest.raises(VerificationError):
        repository(catalog_root).load_object(digest)


def test_the_repository_reports_what_the_index_contains(catalog_root: Path) -> None:
    metadata = repository(catalog_root).catalog_metadata()

    assert metadata == {
        "schema_version": "techtree.catalog.v1alpha1",
        "climb_count": 3,
        "object_count": 4,
    }


# ---------------------------------------------------------------------------
# Broken links
# ---------------------------------------------------------------------------


def test_a_catalog_that_lists_a_file_it_does_not_ship_fails(
    catalog_root: Path,
) -> None:
    (catalog_root / "campaigns" / "synthetic.json").unlink()

    with pytest.raises(NotFoundError) as failure:
        repository(catalog_root).list_climb_references()

    assert failure.value.code == "catalog_file_missing"


def test_a_file_that_drifted_from_its_digest_fails_verification(
    catalog_root: Path, service: CatalogService
) -> None:
    """Reformatting is fine; changing a value is not."""
    campaign = catalog_root / "campaigns" / "synthetic.json"
    document = json.loads(campaign.read_text("utf-8"))
    campaign.write_text(json.dumps(document, indent=4), encoding="utf-8")
    service.get_climb("synthetic-open@1")

    document["metadata"]["version"] = 2
    campaign.write_bytes(canonical_json_bytes(document))

    with pytest.raises(VerificationError) as failure:
        service.get_climb("synthetic-open@1")
    assert failure.value.code == "catalog_digest_mismatch"


def test_an_object_filed_under_the_wrong_kind_fails(catalog_root: Path) -> None:
    """The kind is part of the address, so it is checked before any parsing."""
    index = read_index(catalog_root)
    campaign_digest = _digest_of_kind(index, "campaign")
    index["objects"][campaign_digest]["kind"] = "data_policy"
    write_index(catalog_root, index)

    with pytest.raises(ValidationError) as failure:
        repository(catalog_root).load_campaign(campaign_digest)

    assert failure.value.code == "catalog_kind_mismatch"


def test_a_file_holding_the_wrong_object_fails_to_parse(catalog_root: Path) -> None:
    """A DataPolicy sitting where a Campaign should be is not a Campaign."""
    (catalog_root / "campaigns" / "synthetic.json").write_bytes(
        (catalog_root / "data-policies" / "synthetic.json").read_bytes()
    )
    campaign_digest = _digest_of_kind(read_index(catalog_root), "campaign")

    with pytest.raises(ValidationError) as failure:
        repository(catalog_root).load_campaign(campaign_digest)

    assert failure.value.code == "catalog_object_invalid"


def test_a_path_that_climbs_out_of_the_catalog_is_refused(
    catalog_root: Path,
) -> None:
    edit_index(
        catalog_root,
        lambda document: document["climbs"][0].update(
            {"path": "../elsewhere/synthetic-open.json"}
        ),
    )

    with pytest.raises(ValidationError) as failure:
        repository(catalog_root).list_climb_references()

    assert failure.value.code == "catalog_index_invalid"


def test_a_link_pointing_out_of_the_catalog_is_refused(
    catalog_root: Path, tmp_path: Path
) -> None:
    """A legal-looking path that resolves elsewhere is still an escape."""
    outside = tmp_path / "outside.json"
    outside.write_bytes((catalog_root / "climbs" / "synthetic-open.json").read_bytes())
    escape = catalog_root / "climbs" / "escaped.json"
    escape.symlink_to(outside)
    edit_index(
        catalog_root,
        lambda document: document["climbs"][0].update({"path": "climbs/escaped.json"}),
    )

    with pytest.raises(ValidationError) as failure:
        repository(catalog_root).list_climb_references()

    assert failure.value.code == "catalog_path_traversal"


def test_two_digests_cannot_claim_the_same_file(catalog_root: Path) -> None:
    """A digest-to-path map that is not one-to-one cannot be verified."""
    index = read_index(catalog_root)
    campaign_digest = _digest_of_kind(index, "campaign")
    index["objects"][sha256_digest_bytes(b"a second claim")] = {
        "kind": "campaign",
        "media_type": "application/json",
        "path": index["objects"][campaign_digest]["path"],
    }
    write_index(catalog_root, index)

    with pytest.raises(ValidationError) as failure:
        repository(catalog_root).list_climb_references()

    assert failure.value.code == "catalog_index_invalid"


def test_a_reference_the_manifest_disagrees_with_is_refused(
    catalog_root: Path,
) -> None:
    edit_index(
        catalog_root,
        lambda document: document["climbs"][0].update({"reference": "renamed@9"}),
    )

    with pytest.raises(ValidationError) as failure:
        repository(catalog_root).load_climb("renamed@9")

    assert failure.value.code == "catalog_reference_mismatch"


def test_an_object_nothing_ships_cannot_be_referenced(catalog_root: Path) -> None:
    with pytest.raises(NotFoundError) as failure:
        repository(catalog_root).load_campaign(sha256_digest_bytes(b"absent"))

    assert failure.value.code == "catalog_object_not_found"


# ---------------------------------------------------------------------------
# Contradictions
# ---------------------------------------------------------------------------


def test_a_climb_that_contradicts_its_data_policy_raises_a_policy_error(
    catalog_root: Path, service: CatalogService
) -> None:
    """The policy requires candidate skills to be released; this Climb hides them."""
    _replace_climb(
        catalog_root,
        slug="synthetic-open",
        status="open",
        proof_grade="P1",
        skill_visibility="private",
    )

    with pytest.raises(PolicyError) as failure:
        service.get_climb("synthetic-open@1")

    assert "release" in str(failure.value)


def test_a_proof_grade_that_disagrees_with_the_status_raises_a_policy_error(
    catalog_root: Path, service: CatalogService
) -> None:
    _replace_climb(
        catalog_root,
        slug="synthetic-open",
        status="open",
        proof_grade="development_only",
    )

    with pytest.raises(PolicyError) as failure:
        service.get_climb("synthetic-open@1")

    assert failure.value.code == "proof_grade_contradiction"


def test_evidence_produced_for_another_taskset_is_rejected(
    catalog_root: Path, service: CatalogService
) -> None:
    """The receipt and the evidence it points at must describe one validation."""
    fixture = builder()
    lock = fixture.build_taskset_lock()
    other_lock = lock.model_copy(
        update={"engine_digest": fixture.synthetic_digest("another-engine")}
    )
    _rebuild(catalog_root, evidence=fixture.build_validation_evidence(other_lock))

    with pytest.raises(PolicyError) as failure:
        service.get_climb("synthetic-open@1")

    assert failure.value.code == "validation_evidence_mismatch"


def test_evidence_for_tasks_the_campaign_did_not_commit_to_is_rejected(
    catalog_root: Path, service: CatalogService
) -> None:
    """What was validated and what will be run have to be the same tasks."""
    fixture = builder()
    evidence = fixture.build_validation_evidence(fixture.build_taskset_lock())
    renamed = [
        task.model_copy(
            update={
                "task_hash": fixture.synthetic_digest(f"other-task-{task.position}")
            }
        )
        for task in evidence.tasks
    ]
    _rebuild(catalog_root, evidence=evidence.model_copy(update={"tasks": renamed}))

    with pytest.raises(PolicyError) as failure:
        service.get_climb("synthetic-open@1")

    assert failure.value.code == "validated_membership_mismatch"


def test_a_receipt_pointing_at_evidence_nobody_ships_is_rejected(
    catalog_root: Path, service: CatalogService
) -> None:
    """Decisions 0003 A4: the public catalog carries no dangling references."""
    index = read_index(catalog_root)
    evidence_digest = _digest_of_kind(index, "validation_evidence")
    del index["objects"][evidence_digest]
    write_index(catalog_root, index)

    with pytest.raises(NotFoundError) as failure:
        service.get_climb("synthetic-open@1")

    assert failure.value.code == "catalog_object_not_found"


# ---------------------------------------------------------------------------
# Compatibility
# ---------------------------------------------------------------------------


def test_a_missing_engine_blocks_without_hiding_the_climb(
    service: CatalogService,
) -> None:
    """Before WP4 the engine is absent, and the Climb is still displayed."""
    summary = service.climb_summary(service.get_climb("synthetic-open@1"))

    assert summary.compatibility.engine_status is (
        EngineCompatibilityStatus.NOT_INSTALLED
    )
    assert summary.compatibility.compatible is False
    assert [issue.code for issue in summary.compatibility.issues] == [
        "engine_not_installed"
    ]
    assert summary.title


def test_an_installed_engine_is_a_warning_rather_than_a_block(
    catalog_root: Path, paths: TechtreePaths
) -> None:
    resolved = CatalogService(
        repository(catalog_root), SUPPORTED_HOST, InstalledEngineStatus(paths)
    ).get_climb("synthetic-open@1")
    paths.engine_dir(resolved.publisher_validation.engine_digest).mkdir(parents=True)

    compatibility = CatalogService(
        repository(catalog_root), SUPPORTED_HOST, InstalledEngineStatus(paths)
    ).compatibility(resolved)

    assert compatibility.compatible is True
    assert [issue.code for issue in compatibility.issues] == ["engine_not_verified"]


def test_an_unsupported_host_is_named_rather_than_guessed_at(
    catalog_root: Path, paths: TechtreePaths
) -> None:
    service = CatalogService(
        repository(catalog_root),
        HostInfo(operating_system="plan9", architecture="sparc", python_version="3.12"),
        InstalledEngineStatus(paths),
    )

    compatibility = service.compatibility(service.get_climb("synthetic-open@1"))

    assert compatibility.host_platform == "plan9/sparc"
    assert compatibility.host_supported is False
    assert "host_unsupported" in [issue.code for issue in compatibility.issues]


# ---------------------------------------------------------------------------
# The packaged catalog, which is empty
# ---------------------------------------------------------------------------


def test_the_packaged_catalog_is_valid_and_ships_nothing_yet() -> None:
    """Decisions 0003 A2: valid and empty until the generator exists."""
    packaged = EmbeddedCatalogRepository.packaged()

    assert packaged.list_climb_references() == []
    assert packaged.catalog_metadata()["object_count"] == 0


def test_list_says_so_usefully_when_the_build_ships_no_climbs(
    temp_techtree_home: Path,
) -> None:
    envelope = _invoke(temp_techtree_home, "climb", "list", "--json")

    assert envelope["ok"] is True
    assert envelope["data"] == []
    assert envelope["messages"][0]["code"] == "no_climbs_available"
    assert envelope["next_actions"][0]["cli"] == ["techtree", "doctor"]


def test_show_reports_a_name_this_build_does_not_have(
    temp_techtree_home: Path,
) -> None:
    result = CliRunner().invoke(
        create_app(),
        ["--home", str(temp_techtree_home), "--json", "climb", "show", "absent"],
    )

    assert result.exit_code == EXIT_NOT_FOUND
    envelope = json.loads(result.stdout.splitlines()[-1])
    assert envelope["error"]["code"] == "climb_not_found"
    assert envelope["next_actions"][0]["id"] == "check_environment"


# ---------------------------------------------------------------------------
# The commands, against the complete fixture
# ---------------------------------------------------------------------------


def test_list_shows_every_available_climb_and_offers_the_first(
    populated_cli: Callable[..., dict[str, Any]],
) -> None:
    envelope = populated_cli("climb", "list", "--json")

    assert envelope["ok"] is True
    assert [entry["reference"] for entry in envelope["data"]] == [
        "synthetic-open@1",
        "synthetic-development@1",
    ]
    assert envelope["warnings"][0]["code"] == "development_climb"
    assert envelope["next_actions"][0]["cli"] == [
        "techtree",
        "climb",
        "show",
        "synthetic-open@1",
    ]


def test_list_renders_one_readable_row_per_climb(populated_home: Path) -> None:
    result = CliRunner().invoke(
        create_app(), ["--home", str(populated_home), "climb", "list"]
    )

    assert result.exit_code == EXIT_OK
    assert "2 Climbs are available in this build." in result.stdout
    assert "synthetic-open@1" in result.stdout
    assert "synthetic-closed@1" not in result.stdout
    assert "Next steps:" in result.stdout
    assert "techtree climb show synthetic-open@1" in result.stdout


def test_show_returns_a_summary_a_host_agent_can_validate(
    populated_cli: Callable[..., dict[str, Any]],
) -> None:
    envelope = populated_cli("climb", "show", "synthetic-open", "--json")

    # Validated from JSON rather than from the parsed mapping: a protocol model
    # is strict, and a host agent reads the bytes, not a Python object.
    summary = ClimbSummary.model_validate_json(json.dumps(envelope["data"]))
    assert summary.reference == "synthetic-open@1"
    assert summary.task_count == 4
    assert summary.data_policy.candidate_skill_public_release == "required_for_climb"
    assert summary.compatibility.compatible is False


def test_show_displays_everything_a_person_needs_before_entering(
    populated_home: Path,
) -> None:
    """Spec section 26 WP1, the whole display list.

    Including the Campaign facts a summary has no field for, and with protocol
    values spelled as words rather than as identifiers.
    """
    result = CliRunner().invoke(
        create_app(),
        ["--home", str(populated_home), "climb", "show", "synthetic-development"],
    )

    assert result.exit_code == EXIT_OK
    for expected in (
        "Synthetic development Climb",
        "synthetic-development@1",
        "development",
        "component uplift",
        "4 tasks",
        "hermes-agent 0.19.0",
        "development/development-placeholder",
        "techtree-development-placeholder:not-executed",
        "synthetic_reward",
        "participant",
        "required for climb",
        "prohibited",
        "local_techtree",
        "skill insertion",
        "development only",
        "not installed",
    ):
        assert expected in result.stdout, f"{expected!r} is missing from climb show"
    assert "is a development Climb" in result.stdout


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def populated_home(
    catalog_root: Path, temp_techtree_home: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Point the CLI at the complete fixture instead of the packaged catalog."""

    def service_over_the_fixture(context: Any) -> CatalogService:
        return CatalogService(
            EmbeddedCatalogRepository(catalog_root),
            current_host_info(),
            InstalledEngineStatus(context.paths),
        )

    monkeypatch.setattr(
        "techtree.cli.commands.climb.build_catalog_service", service_over_the_fixture
    )
    return temp_techtree_home


@pytest.fixture
def populated_cli(populated_home: Path) -> Callable[..., dict[str, Any]]:
    """Return a callable that invokes the CLI over the complete fixture."""

    def invoke(*arguments: str) -> dict[str, Any]:
        return _invoke(populated_home, *arguments)

    return invoke


def _invoke(home: Path, *arguments: str) -> dict[str, Any]:
    result = CliRunner().invoke(create_app(), ["--home", str(home), *arguments])
    document: dict[str, Any] = json.loads(result.stdout.splitlines()[-1])
    return document


def _digest_of_kind(index: dict[str, Any], kind: str) -> str:
    for digest, location in index["objects"].items():
        if location["kind"] == kind:
            return str(digest)
    raise AssertionError(f"the fixture index has no {kind} object")


def _replace_climb(root: Path, *, slug: str, **overrides: Any) -> None:
    """Rewrite one Climb of a fixture copy, and re-file it in the index."""
    fixture = builder()
    index = read_index(root)
    entry = next(
        entry for entry in index["climbs"] if entry["reference"].startswith(slug)
    )
    campaign_digest = _digest_of_kind(index, "campaign")

    climb = fixture.build_climb(campaign_digest=campaign_digest, slug=slug, **overrides)
    (root / entry["path"]).write_bytes(canonical_json_bytes(climb))
    entry["digest"] = digest_object(climb)
    write_index(root, index)


def _rebuild(root: Path, *, evidence: Any) -> None:
    """Rebuild the whole fixture around one substituted evidence document.

    Everything downstream of the evidence — the receipt that points at it, the
    Campaign that commits to the receipt, the Climb that wraps the Campaign — is
    rebuilt so that every digest still verifies. Only the fact the test is about
    is wrong, which is what makes the resulting failure meaningful.
    """
    fixture = builder()
    lock = fixture.build_taskset_lock()
    data_policy = fixture.build_data_policy()
    receipt = fixture.build_validation_receipt(lock, evidence)
    campaign = fixture.build_campaign(
        lock=lock,
        validation_receipt_digest=digest_object(receipt),
        data_policy_digest=digest_object(data_policy),
    )
    climb = fixture.build_climb(
        campaign_digest=digest_object(campaign),
        slug="synthetic-open",
        status="open",
        proof_grade="P1",
    )

    shutil.rmtree(root)
    fixture.write_catalog(
        root,
        climbs={"climbs/synthetic-open.json": climb},
        objects=[
            fixture.CatalogFile(
                kind="campaign", path=fixture.CAMPAIGN_PATH, model=campaign
            ),
            fixture.CatalogFile(
                kind="data_policy", path=fixture.DATA_POLICY_PATH, model=data_policy
            ),
            fixture.CatalogFile(
                kind="taskset_validation", path=fixture.RECEIPT_PATH, model=receipt
            ),
            fixture.CatalogFile(
                kind="validation_evidence", path=fixture.EVIDENCE_PATH, model=evidence
            ),
        ],
    )
