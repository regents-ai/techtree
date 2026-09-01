"""WP0.4's NeMo Fabric adapter capability evidence and release blockers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from techtree.canonical import sha256_digest_bytes

CLI_ROOT = Path(__file__).parents[2]
MONOREPO_ROOT = CLI_ROOT.parent
DOCS_ROOT = MONOREPO_ROOT / "docs" / "v0.2"
FIXTURE_ROOT = CLI_ROOT / "tests" / "fixtures" / "fabric"
FIXTURE_PATH = FIXTURE_ROOT / "fabric_capabilities_0_2_0.json"
MANIFEST_PATH = FIXTURE_ROOT / "evidence_manifest.json"
MATRIX_PATH = DOCS_ROOT / "FABRIC_CAPABILITY_MATRIX.json"
LOCK_PATH = DOCS_ROOT / "UPSTREAM_CONTRACT_LOCK.json"
CANDIDATES_PATH = DOCS_ROOT / "UPSTREAM_CANDIDATES.json"
CONTRACT_PATH = DOCS_ROOT / "FABRIC_CONTRACT.md"

ADAPTERS = ("nvidia.fabric.hermes", "nvidia.fabric.codex")
DESCRIPTOR_KEYS = {"nvidia.fabric.hermes": "hermes", "nvidia.fabric.codex": "codex"}


def load_json(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def retained(record: dict[str, Any]) -> bytes:
    relative = record["path"]
    assert isinstance(relative, str)
    return (MONOREPO_ROOT / relative).read_bytes()


def descriptor(manifest: dict[str, Any], adapter_id: str) -> dict[str, Any]:
    record = manifest["descriptors"][DESCRIPTOR_KEYS[adapter_id]]
    document = json.loads(retained(record).decode("utf-8"))
    assert isinstance(document, dict)
    return document


def derive_controls(
    manifest: dict[str, Any], observed: dict[str, Any]
) -> dict[str, dict[str, dict[str, Any]]]:
    """Re-derive every capability claim from the retained evidence alone."""

    derived: dict[str, dict[str, dict[str, Any]]] = {}
    for adapter_id in ADAPTERS:
        accepts = set(descriptor(manifest, adapter_id)["config"]["accepts"])
        records = {}
        for control, record in observed["controls"][adapter_id].items():
            admitted = record["plan"] == "admitted" and not record["doctor_failures"]
            records[control] = {
                "descriptor_claimed": control in accepts,
                "techtree_conformance": (
                    "admitted" if admitted else "rejected_before_execution"
                ),
                "routed_to": sorted(
                    {route["target"] for route in record.get("routes", [])}
                )
                or None,
            }
        derived[adapter_id] = records
    return derived


def test_exact_candidate_evidence_and_digest_chain() -> None:
    fixture = load_json(FIXTURE_PATH)
    manifest = load_json(MANIFEST_PATH)
    matrix = load_json(MATRIX_PATH)
    lock = load_json(LOCK_PATH)["nemo_fabric"]
    candidate = next(
        entry
        for entry in load_json(CANDIDATES_PATH)["candidates"]
        if entry["id"] == "nemo-fabric-stable-0.2.0"
    )

    assert lock["source_commit"] == candidate["source_commit"]
    assert lock["source_tag"] == candidate["source_tag"] == "v0.2.0"
    assert fixture["fabric"]["source_commit"] == lock["source_commit"]
    assert fixture["fabric"]["runtime_version"] == lock["runtime_version"]
    assert fixture["fabric"]["fabric_schema_version"] == lock["fabric_schema_version"]
    assert matrix["runtime"]["fabric_schema_version"] == lock["fabric_schema_version"]
    assert (
        fixture["fabric"]["adapter_contract_version"]
        == lock["adapter_contract_version"]
    )

    packages = {entry["package"]: entry for entry in candidate["packages"]}
    for name, record in manifest["artifacts"].items():
        if name in {"hermes_agent_wheel", "openai_codex_wheel"}:
            continue
        assert record["version"] == "0.2.0"
        assert packages[record["package"]]["wheel_sha256"] == record["sha256"]
        # No wheel names a commit, so every record says where the commit
        # actually comes from rather than implying the wheel proves it.
        assert "release tag" in record["source_commit_note"]

    provenance = manifest["wheel_provenance"]
    assert provenance["commit_binding"] == (
        "asserted_from_release_tag_not_from_wheel_contents"
    )
    assert provenance["sbom"]["declares_commit"] is False
    assert provenance["sbom"]["member_sha256"].startswith("sha256:")
    assert "release tag" in lock["source_commit_note"]
    assert "release tag" in candidate["source_commit_note"]

    for adapter in lock["adapter_coordinates"]:
        key = DESCRIPTOR_KEYS[adapter["adapter_id"]]
        record = manifest["descriptors"][key]
        assert adapter["descriptor"] == record["path"]
        assert adapter["descriptor_sha256"] == record["sha256"]
        assert record["sha256"] == sha256_digest_bytes(retained(record))
        assert record["size_bytes"] == len(retained(record))
        assert adapter["admission"] == (
            "conformance_captured_release_admission_pending"
        )

    fixture_digest = sha256_digest_bytes(FIXTURE_PATH.read_bytes())
    manifest_digest = sha256_digest_bytes(MANIFEST_PATH.read_bytes())
    assert lock["fixture_sha256"] == fixture_digest
    assert lock["evidence_manifest_sha256"] == manifest_digest
    assert matrix["evidence"]["fixture_sha256"] == fixture_digest
    assert matrix["evidence"]["evidence_manifest_sha256"] == manifest_digest
    assert lock["capability_matrix_sha256"] == sha256_digest_bytes(
        MATRIX_PATH.read_bytes()
    )
    assert lock["contract_record_sha256"] == sha256_digest_bytes(
        CONTRACT_PATH.read_bytes()
    )
    assert candidate["conformance"]["evidence_manifest_sha256"] == manifest_digest
    assert FIXTURE_PATH.stat().st_size < 16 * 1024


def test_all_claims_use_retained_evidence() -> None:
    manifest = load_json(MANIFEST_PATH)

    for record in manifest["source_snapshots"].values():
        assert record["artifact"] in manifest["artifacts"]
        excerpt = retained(record)
        assert record["excerpt_sha256"] == sha256_digest_bytes(excerpt)
        assert record["excerpt_size_bytes"] == len(excerpt)
        assert record["member_size_bytes"] >= record["excerpt_size_bytes"]
        assert record["member_sha256"].startswith("sha256:")
        lines = excerpt.decode("utf-8").splitlines()
        assert len(lines) == record["line_end"] - record["line_start"] + 1

    for name, record in manifest["observations"].items():
        assert record["path"] == f"cli/tests/fixtures/fabric/observed/{name}.json"
        payload = retained(record)
        assert record["sha256"] == sha256_digest_bytes(payload)
        assert record["size_bytes"] == len(payload)

    fixture = load_json(FIXTURE_PATH)
    observed = load_json(FIXTURE_ROOT / "observed" / "admission_matrix.json")
    derived = derive_controls(manifest, observed)
    for adapter_id in ADAPTERS:
        assert fixture["adapters"][adapter_id]["controls"] == derived[adapter_id]
        recorded = fixture["adapters"][adapter_id]
        claimed = descriptor(manifest, adapter_id)["config"]["accepts"]
        assert recorded["descriptor_claimed_controls"] == claimed
        assert (
            recorded["adapter_kind"] == descriptor(manifest, adapter_id)["adapter_kind"]
        )
        assert (
            recorded["descriptor_sha256"]
            == manifest["descriptors"][DESCRIPTOR_KEYS[adapter_id]]["sha256"]
        )
        # The observation repeats the descriptor's accepts list; it must not
        # drift from the descriptor bytes the manifest binds.
        assert observed["resolved_descriptors"][adapter_id]["config_accepts"] == claimed
        assert observed["resolved_descriptors"][adapter_id][
            "resolved_descriptor_canonical_sha256"
        ].startswith("sha256:")
    assert (
        "runtime capability flags"
        in (observed["resolved_descriptor_canonical_sha256_meaning"])
    )

    # Every evidence reference names a retained snapshot or observation.
    available = set(manifest["source_snapshots"]) | set(manifest["observations"])
    for adapter in fixture["adapters"].values():
        for ref in adapter.get("harness_availability_evidence_refs", []):
            assert ref in available, ref
    for blocker in fixture["unresolved_for_release"].values():
        assert blocker["evidence_refs"]
        for ref in blocker["evidence_refs"]:
            assert ref in available, ref


def test_admission_is_exact_to_the_descriptor_and_precedes_execution() -> None:
    manifest = load_json(MANIFEST_PATH)
    observed = load_json(FIXTURE_ROOT / "observed" / "admission_matrix.json")
    matrix = load_json(MATRIX_PATH)
    derived = derive_controls(manifest, observed)
    candidates = {entry["adapter_id"]: entry for entry in matrix["candidate_adapters"]}

    for adapter_id in ADAPTERS:
        claimed = set(descriptor(manifest, adapter_id)["config"]["accepts"])
        admitted = {
            control
            for control, record in derived[adapter_id].items()
            if record["techtree_conformance"] == "admitted"
        }
        rejected = set(derived[adapter_id]) - admitted
        assert admitted == claimed & set(derived[adapter_id])
        assert not rejected & claimed

        # A rejected control fails while planning, before any runtime starts.
        for control in rejected:
            assert observed["controls"][adapter_id][control]["plan"] == "rejected"
            assert observed["controls"][adapter_id][control]["doctor_failures"]

        # Doctor reports a failing check for every refused control except
        # tools.definitions, where it raises instead of returning a report.
        raising = {
            control
            for control in rejected
            if observed["controls"][adapter_id][control]["doctor_status"] == "raised"
        }
        assert raising == {"tools.definitions"}

        entry = candidates[adapter_id]
        assert sorted(entry["techtree_admitted_controls"]) == sorted(admitted)
        assert sorted(entry["unsupported_controls"]) == sorted(rejected)
        assert entry["descriptor_claimed_controls"] == sorted(claimed)
        assert (
            entry["declared_runtime_capabilities"]
            == observed["resolved_descriptors"][adapter_id][
                "declared_runtime_capabilities"
            ]
        )
        assert observed["resolved_descriptors"][adapter_id]["provenance_sources"] == [
            "installed_package"
        ]

    codex = derived["nvidia.fabric.codex"]
    for control in ("tools.enabled", "tools.blocked", "tools.definitions"):
        assert codex[control]["techtree_conformance"] == "rejected_before_execution"
    assert (
        derived["nvidia.fabric.hermes"]["tools.enabled"]["techtree_conformance"]
        == "admitted"
    )


def test_recorded_gaps_are_the_ones_the_evidence_shows() -> None:
    lifecycle = load_json(FIXTURE_ROOT / "observed" / "lifecycle.json")
    isolation = load_json(FIXTURE_ROOT / "observed" / "isolation.json")
    fixture = load_json(FIXTURE_PATH)
    lock = load_json(LOCK_PATH)["nemo_fabric"]
    matrix = load_json(MATRIX_PATH)

    for adapter_id in ADAPTERS:
        absent = lifecycle["absent_harness"][adapter_id]
        assert absent["doctor_status"] == "pass"
        assert absent["harness_presence_checked_by_doctor"] is False
        assert absent["lifecycle"] == "failed_after_admission"
        assert absent["lifecycle_failure"]["lifecycle_stage"] == "start"
        assert absent["lifecycle_failure"]["missing_module"]
    assert lock["harness_presence_checked_by_fabric_doctor"] is False

    enforcement = lifecycle["declared_requirement_enforcement"]
    assert enforcement["doctor_status"] == "fail"
    assert [check["name"] for check in enforcement["requirement_checks"]] == [
        "requirement.binary"
    ]

    for run in lifecycle["runs"].values():
        assert run["event_kinds"] == [
            "runtime_start",
            "invocation_start",
            "invocation_end",
            "runtime_stop",
        ]
        assert run["runtime_stop_metadata"] == [
            {"already_stopped": False, "host_crashed": False}
        ]
        assert run["status"] == "failed"
        assert run["error"]["stage"] == "invoke"
        assert run["usage"] is None
        assert run["telemetry"] == []
        assert run["adapter_runner"] == "persistent_local_host"
        assert run["host_interpreter_inside_managed_environment"] is True
        assert run["harness_state_root_prefixes"] == [".fabric"]
        assert run["model_turn_completed"] is False
        # The measured directory is the disposable HOME the process was given,
        # not the operator's own home, and the record says which.
        assert run["process_home_entries_before"] == 0
        assert run["process_home_entries_after"] == 0
        assert "disposable directory supplied" in run["process_home_measurement"]

    hermes = lifecycle["runs"]["hermes_empty_enabled_tools"]
    assert hermes["tools_policy"] == "empty_enabled_list"
    assert hermes["enabled_toolsets"] == []
    assert lifecycle["runs"]["hermes_harness_default_tools"]["enabled_toolsets"]

    for adapter_id in ADAPTERS:
        capabilities = fixture["adapters"][adapter_id]["declared_runtime_capabilities"]
        assert capabilities == {
            "cancellation": False,
            "service": False,
            "streaming": False,
            "updates": False,
        }
        assert fixture["adapters"][adapter_id]["declared_requirements"] == {}
    # These are descriptor declarations, never observed attempts.
    for field in (
        "runtime_cancellation",
        "runtime_streaming",
        "runtime_updates",
        "runtime_service_handles",
    ):
        assert lock[field] == "declared_false_by_both_descriptors_untested"
    assert lock["native_streaming_entry_point"] == (
        "invoke_openai_stream_present_untested"
    )
    native = (
        MONOREPO_ROOT
        / load_json(MANIFEST_PATH)["source_snapshots"]["fabric_native_interface"][
            "path"
        ]
    ).read_text(encoding="utf-8")
    assert "def invoke_openai_stream(" in native
    # The excerpt carries every signature whole, and stops on a complete one.
    assert native.count("def ") == native.count("-> str: ...")
    assert native.rstrip().endswith("...")
    assert lock["usage_accounting"] == (
        "not_reported_on_runs_that_terminated_at_invoke"
    )
    assert lock["doctor_refusal_shapes"] == (
        "failing_check_except_tools_definitions_which_raises"
    )

    cache = load_json(FIXTURE_ROOT / "observed" / "codex_fresh_home_plugin_cache.json")
    assert cache["git_working_tree_present"] is True
    assert "FETCH_HEAD" in cache["git_markers_present"]
    assert cache["remote_inspected"] is False
    assert cache["remote_asserted"] is None
    assert lock["codex_fresh_home_hermeticity"] == (
        "not_hermetic_remote_plugin_fetch_observed"
    )

    supply = load_json(FIXTURE_ROOT / "observed" / "index_queries.json")
    hermes_index = supply["queries"]["hermes_agent_releases"]
    assert hermes_index["observed_latest_version"] == "0.19.0"
    assert "0.19.0" in hermes_index["observed_recent_releases"]
    assert "Neither observation proves" in hermes_index["supports"]
    vendor = (
        MONOREPO_ROOT
        / load_json(MANIFEST_PATH)["source_snapshots"][
            "nemo_fabric_hermes_harness_supply"
        ]["path"]
    ).read_text(encoding="utf-8")
    assert "0.20 and later is not installable from PyPI" in vendor

    inherited = isolation["unresolved"]["codex_openai_provider_home_inheritance"]
    excerpt = (
        MONOREPO_ROOT
        / load_json(MANIFEST_PATH)["source_snapshots"]["codex_adapter_inherited_env"][
            "path"
        ]
    ).read_text(encoding="utf-8")
    assert inherited["inherited_environment_names"] == sorted(
        re.findall(r'^\s+"(\w+)",$', excerpt, re.M)
    )
    for name in ("CODEX_HOME", "HOME", "OPENAI_API_KEY"):
        assert name in inherited["inherited_environment_names"]
    assert lock["codex_openai_provider_environment_isolation"] == (
        "caller_owned_home_and_codex_home_required"
    )
    assert matrix["techtree_owned_gates_required_before_any_subject_run"]


def test_no_adapter_is_release_admitted_and_no_protected_action_ran() -> None:
    fixture = load_json(FIXTURE_PATH)
    matrix = load_json(MATRIX_PATH)
    lock = load_json(LOCK_PATH)["nemo_fabric"]
    isolation = load_json(FIXTURE_ROOT / "observed" / "isolation.json")

    assert matrix["admitted_adapters"] == []
    assert matrix["support_rule"] == [
        "descriptor_claimed",
        "techtree_conformance_passed",
        "release_admitted",
    ]
    lifecycle = load_json(FIXTURE_ROOT / "observed" / "lifecycle.json")
    blockers = set(fixture["unresolved_for_release"])
    for entry in matrix["candidate_adapters"]:
        assert entry["descriptor_claims_captured"] is True
        assert entry["techtree_conformance_passed"] is True
        assert entry["release_admitted"] is False
        assert entry["release_admission_blockers"]
        # The conformance boolean must never read as a successful subject run.
        assert entry["lifecycle_terminal_status"] == "failed"
        assert entry["lifecycle_error_stage"] == "invoke"
        assert entry["model_turn_completed"] is False
        # Every blocker the matrix names resolves to a recorded finding whose
        # kind says whether it was observed, declared, or merely stated.
        for blocker in entry["release_admission_blockers"]:
            assert blocker["id"] in blockers, blocker["id"]
            assert (
                fixture["unresolved_for_release"][blocker["id"]]["kind"]
                == blocker["kind"]
            )
    scope = matrix["techtree_conformance_scope"]
    assert scope["model_turn_completed"] is False
    assert scope["lifecycle_terminal_status"] == "failed"
    assert (
        "does not mean a subject run succeeded"
        in (matrix["support_rule_meaning"]["techtree_conformance_passed"])
    )
    assert lock["lifecycle_conformance"]["model_turn_completed"] is False
    assert lock["lifecycle_conformance"]["terminal_status"] == "failed"

    for adapter_id, adapter in fixture["adapters"].items():
        assert adapter["release_admitted"] is False
        assert adapter["model_turn_completed"] is False
        assert adapter["lifecycle_terminal_status"] == "failed"
        assert "no model turn" in adapter["techtree_lifecycle_observed"]
        run_status = {run["status"] for run in lifecycle["runs"].values()}
        assert run_status == {"failed"}
        assert adapter_id in ADAPTERS
    assert lock["admission"] == (
        "blocked_pending_founder_release_admission_and_techtree_owned_gates"
    )

    assert fixture["paid_work_observed"] is False
    assert fixture["model_provider_contacted"] is False
    # Network activity is scoped honestly: the Codex harness did fetch.
    assert "No model provider was contacted" in fixture["network_activity_during_runs"]
    assert fixture["host_harness_installation_modified"] is False
    assert fixture["reusable_credential_copied_into_managed_runtime"] is False
    assert isolation["process_environment"]["credential_variable_names_present"] == []
    assert (
        isolation["process_environment"]["host_harness_executables_reachable_on_path"]
        == []
    )
    observed = isolation["observed"]
    assert observed["process_home_entries_created_by_lifecycle"] == 0
    assert "disposable directory supplied" in observed["process_home_measurement"]
    assert observed["operator_home_directory_named_in_process_environment"] is False


def test_retained_evidence_has_no_private_or_reusable_account_material() -> None:
    manifest = load_json(MANIFEST_PATH)
    evidence = "\n".join(
        path.read_text(encoding="utf-8")
        for path in FIXTURE_ROOT.rglob("*")
        if path.is_file()
    )
    serialized = evidence + CONTRACT_PATH.read_text(encoding="utf-8")

    assert re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", serialized) is None
    assert "/Users/" not in serialized
    assert "/home/" not in serialized
    assert re.search(r"Bearer [A-Za-z0-9_-]{20,}", serialized) is None
    assert "sk-ant-" not in serialized
    assert "sk-proj-" not in serialized
    assert "OPENAI_API_KEY=" not in serialized
    assert all(value is False for value in manifest["sanitization"].values())
