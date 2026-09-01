"""WP0.5's NeMo Relay, ATOF and ATIF evidence, and the two coverage profiles."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from techtree.canonical import sha256_digest_bytes

CLI_ROOT = Path(__file__).parents[2]
MONOREPO_ROOT = CLI_ROOT.parent
DOCS_ROOT = MONOREPO_ROOT / "docs" / "v0.2"
PROFILE_ROOT = DOCS_ROOT / "RELAY_COVERAGE_PROFILES"
FIXTURE_ROOT = CLI_ROOT / "tests" / "fixtures" / "relay"

MANIFEST_PATH = FIXTURE_ROOT / "evidence_manifest.json"
RECORD_PATH = FIXTURE_ROOT / "relay_contract_0_8_2.json"
ATOF_PATH = FIXTURE_ROOT / "atof" / "complete.atof.jsonl"
NATIVE_ATIF_PATH = FIXTURE_ROOT / "atif" / "complete.native.atif.json"
DERIVED_ATIF_PATH = FIXTURE_ROOT / "atif" / "complete.derived.atif.json"
CONTRACT_PATH = DOCS_ROOT / "RELAY_CONTRACT.md"
LOCK_PATH = DOCS_ROOT / "UPSTREAM_CONTRACT_LOCK.json"
CANDIDATES_PATH = DOCS_ROOT / "UPSTREAM_CANDIDATES.json"

PROFILE_PATHS = {
    "nvidia.fabric.hermes": PROFILE_ROOT / "hermes.relay-coverage-profile.json",
    "nvidia.fabric.codex": PROFILE_ROOT / "codex.relay-coverage-profile.json",
}

COVERAGE_STATUSES = (
    "not_requested",
    "unavailable",
    "incomplete",
    "complete_for_profile",
)

#: The ATOF envelope Relay 0.8.2 emits. Every retained event carries exactly
#: this key set for its kind, which is what makes correlation possible from the
#: stream alone.
SCOPE_EVENT_KEYS = frozenset(
    {
        "atof_version",
        "attributes",
        "category",
        "category_profile",
        "data",
        "data_schema",
        "kind",
        "metadata",
        "name",
        "parent_uuid",
        "scope_category",
        "timestamp",
        "uuid",
    }
)
MARK_EVENT_KEYS = SCOPE_EVENT_KEYS - {"attributes", "scope_category"}

#: Prime's provider identifiers and any similarly shaped opaque account token.
#: Reused from the Prime and Fabric spikes so one shape of leak is rejected
#: everywhere, not just where it was first seen.
PROVIDER_ID_PATTERN = re.compile(r"(?<![0-9a-z])[0-9a-z]{24,25}(?![0-9a-z])")


def load_json(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def retained(record: dict[str, Any]) -> bytes:
    relative = record["path"]
    assert isinstance(relative, str)
    return (MONOREPO_ROOT / relative).read_bytes()


def atof_events() -> list[dict[str, Any]]:
    lines = ATOF_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


# ---------------------------------------------------------------------------
# relay-coverage-v1, implemented here so the four statuses are demonstrably
# distinguishable from the retained evidence rather than only described.
# ---------------------------------------------------------------------------


def expected_identities(events: list[dict[str, Any]]) -> list[str]:
    """Derive the required expected identities a profile would declare.

    The declared sources supply the root agent scope (from the Fabric execution
    receipt) and the ordered LLM and tool calls (from the Verifiers trace). The
    retained capture stands in for both sources here: it is the only run this
    spike has, and deriving from it keeps the denominator honest about what the
    sources would say for this run.
    """

    identities = ["fabric_execution_receipt/agent/scope_start/0"]
    identities.append("fabric_execution_receipt/agent/scope_end/0")
    ordinals: dict[str, int] = {}
    for event in events:
        if event["kind"] != "scope" or event["category"] == "agent":
            continue
        category = event["category"]
        if event["scope_category"] == "start":
            ordinal = ordinals.get(category, 0)
            ordinals[category] = ordinal + 1
        else:
            ordinal = ordinals[category] - 1
        identities.append(
            f"verifiers_trace/{category}/scope_{event['scope_category']}/{ordinal}"
        )
    return sorted(set(identities))


def observed_identities(events: list[dict[str, Any]]) -> list[str]:
    identities: list[str] = []
    ordinals: dict[str, int] = {}
    for event in events:
        if event["kind"] != "scope":
            continue
        category = event["category"]
        role = f"scope_{event['scope_category']}"
        if category == "agent":
            identities.append(f"fabric_execution_receipt/agent/{role}/0")
            continue
        if event["scope_category"] == "start":
            ordinal = ordinals.get(category, 0)
            ordinals[category] = ordinal + 1
        else:
            ordinal = ordinals[category] - 1
        identities.append(f"verifiers_trace/{category}/{role}/{ordinal}")
    return sorted(set(identities))


def calculate_coverage(
    *,
    requested: bool,
    events: list[dict[str, Any]] | None,
    expected: list[str],
    teardown_completed: bool = True,
    diagnostics: list[str] | None = None,
) -> dict[str, Any]:
    """relay-coverage-v1 over one invocation's ATOF stream."""

    if not requested:
        return {"status": "not_requested", "reasons": []}
    if events is None or not events:
        return {"status": "unavailable", "reasons": ["no_atof_artifact"]}
    if not teardown_completed:
        return {"status": "unavailable", "reasons": ["teardown_did_not_run"]}

    observed = observed_identities(events)
    missing = sorted(set(expected) - set(observed))
    unexpected = sorted(set(observed) - set(expected))
    reasons = list(diagnostics or [])
    if not expected:
        return {"status": "incomplete", "reasons": [*reasons, "empty_denominator"]}
    if missing:
        reasons.append("missing_required_event")
    # An unexpected identity is recorded below and is never a reason. The plan
    # treats unexpected_event_ids as a recorded field, and neither profile
    # lists an unexpected identity among its incomplete reasons.
    status = "complete_for_profile" if not reasons else "incomplete"
    return {
        "status": status,
        "reasons": reasons,
        "expected_event_ids": expected,
        "observed_event_ids": observed,
        "missing_event_ids": missing,
        "unexpected_event_ids": unexpected,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_exact_candidate_coordinates_and_digest_chain() -> None:
    lock = load_json(LOCK_PATH)["nemo_relay"]
    manifest = load_json(MANIFEST_PATH)
    record = load_json(RECORD_PATH)
    candidate = next(
        entry
        for entry in load_json(CANDIDATES_PATH)["candidates"]
        if entry["id"] == "nemo-relay-stable-0.8.2"
    )

    assert load_json(CANDIDATES_PATH)["selected_candidate"]["nemo_relay"] == (
        "nemo-relay-stable-0.8.2"
    )
    assert lock["package_version"] == "0.8.2"
    assert lock["source_tag"] == candidate["source_tag"] == "0.8.2"
    assert lock["source_commit"] == candidate["source_commit"]
    assert record["relay"]["version"] == lock["package_version"]
    assert record["relay"]["source_commit"] == lock["source_commit"]
    assert record["relay"]["atof_version"] == lock["atof_version"] == "0.1"
    assert record["relay"]["atif_schema_version"] == lock["atif_version"] == "ATIF-v1.7"
    assert lock["schema_package"] == "nvidia-nat-atif"
    assert lock["schema_package_version"] == "1.8.0"
    assert (
        record["atif_schema_source"]["source_commit"]
        == (lock["schema_package_source_commit"])
    )
    assert lock["observability_config_version"] == 3
    assert record["relay"]["observability_config_version_pinned"] == 3
    assert candidate["formats"]["observability_config_version"] == 3

    packages = {entry["package"]: entry for entry in candidate["packages"]}
    assert packages["nemo-relay"]["wheel_sha256"] == lock["wheel_sha256"]
    assert (
        packages["nvidia-nat-atif"]["wheel_sha256"]
        == (lock["schema_package_wheel_sha256"])
    )
    artifacts = manifest["artifacts"]
    assert artifacts["nemo_relay_wheel"]["sha256"] == lock["wheel_sha256"]
    assert (
        artifacts["nvidia_nat_atif_wheel"]["sha256"]
        == (lock["schema_package_wheel_sha256"])
    )

    # No Relay wheel names a commit, and the 0.8.2 SBOM names the wrong
    # version, so every record says where the commit actually comes from.
    provenance = manifest["wheel_provenance"]
    assert provenance["commit_binding"] == (
        "asserted_from_release_tag_not_from_wheel_contents"
    )
    assert provenance["sbom"]["declares_commit"] is False
    assert provenance["sbom"]["declares_version"] == "0.8.0"
    assert provenance["sbom"]["version_matches_distribution"] is False
    assert "release tag" in lock["source_commit_note"]
    assert "release tag" in candidate["source_commit_note"]
    assert "release tag" in artifacts["nemo_relay_wheel"]["source_commit_note"]

    assert lock["evidence_manifest_sha256"] == sha256_digest_bytes(
        MANIFEST_PATH.read_bytes()
    )
    assert lock["fixture_sha256"] == sha256_digest_bytes(RECORD_PATH.read_bytes())
    assert lock["contract_record_sha256"] == sha256_digest_bytes(
        CONTRACT_PATH.read_bytes()
    )
    assert (
        candidate["conformance"]["evidence_manifest_sha256"]
        == (lock["evidence_manifest_sha256"])
    )
    assert lock["atof_capture_sha256"] == sha256_digest_bytes(ATOF_PATH.read_bytes())
    assert lock["native_atif_capture_sha256"] == sha256_digest_bytes(
        NATIVE_ATIF_PATH.read_bytes()
    )
    assert lock["derived_atif_capture_sha256"] == sha256_digest_bytes(
        DERIVED_ATIF_PATH.read_bytes()
    )
    assert RECORD_PATH.stat().st_size < 16 * 1024


def test_every_claim_rests_on_retained_evidence() -> None:
    manifest = load_json(MANIFEST_PATH)

    for name, snapshot in manifest["source_snapshots"].items():
        assert snapshot["artifact"] in manifest["artifacts"], name
        excerpt = retained(snapshot)
        assert snapshot["excerpt_sha256"] == sha256_digest_bytes(excerpt)
        assert snapshot["excerpt_size_bytes"] == len(excerpt)
        assert snapshot["member_size_bytes"] >= snapshot["excerpt_size_bytes"]
        assert snapshot["member_sha256"].startswith("sha256:")
        lines = excerpt.decode("utf-8").splitlines()
        assert len(lines) == snapshot["line_end"] - snapshot["line_start"] + 1
        # An excerpt that ends mid-statement cannot be read on its own.
        assert lines[-1].strip()

    for name, observation in manifest["observations"].items():
        assert observation["path"] == f"cli/tests/fixtures/relay/observed/{name}.json"
        payload = retained(observation)
        assert observation["sha256"] == sha256_digest_bytes(payload)
        assert observation["size_bytes"] == len(payload)

    for capture in manifest["captures"].values():
        payload = retained(capture)
        assert capture["sha256"] == sha256_digest_bytes(payload)
        assert capture["size_bytes"] == len(payload)

    derived = manifest["derived_record"]
    assert derived["sha256"] == sha256_digest_bytes(retained(derived))

    # Every finding that cites evidence cites something retained here.
    available = set(manifest["source_snapshots"]) | set(manifest["observations"])
    record = load_json(RECORD_PATH)
    blockers = set(record["unsupported_or_unobserved"])
    for name, finding in record["unsupported_or_unobserved"].items():
        for ref in finding["evidence_refs"]:
            assert ref in available, f"{name} -> {ref}"
    for blocker in record["release_admission_blockers"]:
        assert blocker["id"] in blockers
        assert (
            record["unsupported_or_unobserved"][blocker["id"]]["kind"]
            == (blocker["kind"])
        )
    for profile_path in PROFILE_PATHS.values():
        profile = load_json(profile_path)
        for blind_spot in profile["blind_spots"]:
            for ref in blind_spot["evidence_refs"]:
                assert ref in available, f"{profile_path.name} -> {ref}"
            # An observed claim must cite retained bytes. An unproven one may
            # cite nothing, and then it may not be written as an observation.
            if blind_spot["kind"] == "observed":
                assert blind_spot["evidence_refs"], (
                    f"{profile_path.name} -> {blind_spot['id']}"
                )
        for ref in profile["integration"]["evidence_refs"]:
            assert ref in available, f"{profile_path.name} -> {ref}"


def test_the_retained_atof_stream_has_the_shape_the_record_claims() -> None:
    record = load_json(RECORD_PATH)
    lifecycle = load_json(FIXTURE_ROOT / "observed" / "lifecycle.json")
    events = atof_events()

    assert len(events) == record["size_observations"]["atof_events_in_the_retained_run"]
    assert len(events) == lifecycle["complete"]["atof_event_count"]
    assert ATOF_PATH.stat().st_size == lifecycle["complete"]["atof_bytes"]
    assert [event["name"] for event in events] == (
        lifecycle["subject"]["expected_event_names_in_order"]
    )
    # The largest single event is measured on the retained bytes: the longest
    # JSON line in the file, excluding its trailing newline. Re-serializing the
    # parsed event would measure Python's separators, not Relay's output.
    lines = ATOF_PATH.read_text(encoding="utf-8").splitlines()
    largest_line_bytes = max(
        len(line.encode("utf-8")) for line in lines if line.strip()
    )
    assert largest_line_bytes == lifecycle["complete"]["largest_single_event_bytes"]
    assert (
        largest_line_bytes == record["size_observations"]["largest_single_event_bytes"]
    )
    for profile_path in PROFILE_PATHS.values():
        assert (
            load_json(profile_path)["size_bounds"][
                "observed_largest_single_event_bytes"
            ]
            == largest_line_bytes
        )
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert f"largest single event is {largest_line_bytes} bytes" in contract_text
    assert "excluding its trailing newline" in contract_text

    for event in events:
        assert event["atof_version"] == record["relay"]["atof_version"]
        expected_keys = (
            SCOPE_EVENT_KEYS if event["kind"] == "scope" else MARK_EVENT_KEYS
        )
        assert set(event) == expected_keys, event["name"]
    assert sorted(record["relay"]["atof_envelope_keys"]) == sorted(SCOPE_EVENT_KEYS)

    # Scope starts and ends pair on one uuid, and the root opened and closed.
    scopes = [event for event in events if event["kind"] == "scope"]
    starts = {e["uuid"] for e in scopes if e["scope_category"] == "start"}
    ends = {e["uuid"] for e in scopes if e["scope_category"] == "end"}
    assert starts == ends
    root = next(event for event in scopes if event["category"] == "agent")
    assert root["uuid"] in starts and root["uuid"] in ends
    assert all(
        event["parent_uuid"] == root["uuid"]
        for event in events
        if event["uuid"] != root["uuid"]
    )

    # The refused model call is recorded in ATOF and nowhere else.
    llm_end = next(
        event
        for event in scopes
        if event["category"] == "llm" and event["scope_category"] == "end"
    )
    assert llm_end["metadata"]["otel.status_code"] == "ERROR"
    assert lifecycle["subject"]["model_turn_completed"] is False
    assert record["conformance_scope"]["model_provider_contacted"] is False
    assert record["conformance_scope"]["paid_work_observed"] is False


def test_atif_is_a_lossy_projection_of_the_same_stream() -> None:
    divergence = load_json(
        FIXTURE_ROOT / "observed" / "atif_projection_divergence.json"
    )
    record = load_json(RECORD_PATH)
    native = load_json(NATIVE_ATIF_PATH)
    derived = load_json(DERIVED_ATIF_PATH)
    events = atof_events()

    projections = divergence["projections"]
    assert native["schema_version"] == derived["schema_version"] == "ATIF-v1.7"
    assert len(native["steps"]) == projections["native"]["step_count"]
    assert len(derived["steps"]) == projections["derived"]["step_count"]
    assert len(native["steps"]) != len(derived["steps"])

    # The native projection embeds the whole raw stream, so it is no less
    # private than the ATOF file and is not a redacted summary.
    assert native["extra"]["observed_events"] == events
    assert projections["native"]["embeds_raw_atof_events"] is True
    assert projections["native"]["embedded_event_count"] == len(events)
    assert "observed_events" not in derived.get("extra", {})

    # The native projection anchors on the root scope uuid; the derived one
    # falls back to the converter's own defaults.
    root = next(
        event
        for event in events
        if event["kind"] == "scope" and event["category"] == "agent"
    )
    assert native["session_id"] == native["trajectory_id"] == root["uuid"]
    assert derived["session_id"] == projections["derived"]["session_id_observed"]
    assert derived["agent"]["name"] == projections["derived"]["agent_name_observed"]
    assert "trajectory_id" not in derived

    # Neither projection carries the refused call; the derived one calls it
    # completed. No terminal status may ever be read from ATIF.
    serialized_native = json.dumps(native["steps"])
    assert "ERROR" not in serialized_native
    statuses = [
        step["extra"]["invocation"]["status"]
        for step in derived["steps"]
        if "invocation" in step.get("extra", {})
    ]
    assert statuses == ["completed"]
    assert projections["native"]["carries_llm_failure"] is False
    assert projections["derived"]["carries_llm_failure"] is False
    assert record["unsupported_or_unobserved"]["atif_fidelity"]["kind"] == (
        "observed_defect"
    )
    assert record["relay"]["atif_producers_observed"] == [
        "relay_native_plugin_export",
        "nat_atof_to_atif_converter",
    ]


def test_relay_reports_no_dropped_event_and_no_durable_delivery() -> None:
    diagnostics = load_json(FIXTURE_ROOT / "observed" / "delivery_diagnostics.json")
    lifecycle = load_json(FIXTURE_ROOT / "observed" / "lifecycle.json")
    lock = load_json(LOCK_PATH)["nemo_relay"]
    record = load_json(RECORD_PATH)

    cases = diagnostics["cases"]
    closed = cases["atof_stream_sink_closed_endpoint"]
    live = cases["atof_stream_sink_live_local_listener"]
    assert closed["runtime_report_diagnostics"] == []
    assert closed["teardown"] == "returned"
    # The live listener is what turns silence into a proven swallowed failure.
    assert live["connections_observed"] == live["events_emitted"] == 7
    assert live["runtime_report_diagnostics"] == []
    assert diagnostics["dropped_event_diagnostics"]["available_for_atof"] is False
    assert (
        diagnostics["dropped_event_diagnostics"]["available_for_opentelemetry"] is True
    )
    assert (
        diagnostics["config_report_shape"]["runtime_diagnostics_key_present"] is False
    )

    # The OpenTelemetry path proves a diagnostic channel exists and that the
    # ATOF path simply does not use it.
    otel = cases["opentelemetry_subscriber_direct"]
    assert otel["runtime_diagnostics"][0]["code"] == "otel.traces_export_failed"
    assert cases["opentelemetry_endpoint_closed_via_plugin"]["teardown_raises"] is True

    assert lock["atof_dropped_event_diagnostic"].startswith("unsupported")
    assert lock["atof_delivery_durability"] == (
        "unproven_flush_success_never_establishes_delivery"
    )
    assert record["unsupported_or_unobserved"]["flush_durability"]["kind"] == "unproven"

    # Flush is not evidence of delivery, and a hard death leaves a file that
    # cannot be told apart from a complete one.
    no_flush = lifecycle["no_flush"]
    assert no_flush["atof_event_count_before_shutdown"] == 7
    assert "not a durability or losslessness guarantee" in no_flush["conclusion"]
    hard_death = lifecycle["hard_death"]
    assert hard_death["native_atif_written"] is False
    assert hard_death["teardown_record_written"] is False

    # Teardown ordering constraints observed on the runtime itself.
    inside = lifecycle["flush_inside_event_loop"]
    assert inside["subscribers_flush"].startswith("RuntimeError")
    assert inside["exporter_force_flush"] == "returned"
    assert lock["teardown_flush_constraint"].startswith(
        "synchronous_subscriber_flush_refuses"
    )


def test_the_pinned_observability_config_version_is_the_only_shared_one() -> None:
    matrix = load_json(FIXTURE_ROOT / "observed" / "config_version_matrix.json")
    lock = load_json(LOCK_PATH)["nemo_relay"]

    accepted = [set(row["accepted"]) for row in matrix["producers"].values()]
    intersection = set.intersection(*accepted)
    assert sorted(intersection) == matrix["intersection"] == [3]
    assert matrix["pinned_observability_config_version"] == 3
    assert lock["observability_config_version"] == 3

    current = matrix["producers"]["nemo_relay_0_8_2"]
    prior = matrix["producers"]["nemo_relay_0_7_3"]
    fabric = matrix["producers"]["nemo_fabric_adapters_common_0_2_0"]
    assert current["default_observability_config_version"] == 4
    assert 4 in current["accepted"] and 4 in prior["rejected"]
    assert 4 in fabric["rejected"]
    assert current["version_3_restriction"]["affects_atof"] is False
    assert current["version_3_restriction"]["affects_atif"] is False

    for profile in PROFILE_PATHS.values():
        assert (
            load_json(profile)["pinned_upstream"]["observability_config_version"] == 3
        )


def test_both_profiles_pin_their_versions_and_keep_relay_observe_only() -> None:
    lock = load_json(LOCK_PATH)["nemo_relay"]
    locked_profiles = {
        entry["adapter_id"]: entry for entry in lock["coverage_profiles"]
    }
    assert set(locked_profiles) == set(PROFILE_PATHS)
    assert tuple(lock["coverage_statuses"]) == COVERAGE_STATUSES
    assert lock["coverage_calculation_version"] == "relay-coverage-v1"
    assert lock["coverage_authoritative_artifact"] == "atof"

    for adapter_id, path in PROFILE_PATHS.items():
        profile = load_json(path)
        entry = locked_profiles[adapter_id]
        assert entry["path"] == str(path.relative_to(MONOREPO_ROOT))
        assert entry["sha256"] == sha256_digest_bytes(path.read_bytes())
        assert entry["profile_id"] == profile["profile_id"]
        assert entry["status"] == profile["status"]
        assert entry["release_admitted"] is profile["release_admitted"] is False

        assert profile["schema_version"] == "techtree.relay-coverage-profile.v1"
        assert profile["calculation_version"] == "relay-coverage-v1"
        assert profile["calculation"]["version"] == "relay-coverage-v1"
        assert profile["calculation"]["authoritative_artifact"] == "atof"
        assert profile["adapter_id"] == adapter_id

        authority = profile["authority"]
        assert authority["observe_only"] is True
        assert authority["may_affect_score"] is False
        assert authority["may_affect_spend"] is False
        assert authority["may_affect_execution"] is False

        # The four statuses are all defined, and only one of them is complete.
        rules = profile["status_rules"]
        assert set(rules) == set(COVERAGE_STATUSES)
        assert isinstance(rules["not_requested"], str)
        assert rules["unavailable"] and rules["incomplete"]
        complete = rules["complete_for_profile"]
        assert complete["all_of"]
        assert "never" in complete
        assert "never asserted" in complete["never"]

        # Coverage cannot be completed by shrinking the denominator.
        assert (
            "before the ATOF stream is read"
            in profile["calculation"]["denominator_rule"]
        )
        assert (
            "empty denominator is never complete"
            in profile["calculation"]["denominator_rule"]
        )

        sources = {entry["source"] for entry in profile["expectation_sources"]}
        assert sources == {
            "verifiers_trace",
            "fabric_execution_receipt",
            "native_harness_events",
        }
        for source in profile["expectation_sources"]:
            for derivation in source["derives"]:
                assert derivation["identity"]
                assert derivation["atof_match"]
                if derivation["required"] is False:
                    assert derivation["required_rationale"]

        assert profile["teardown_order"][0] == "await the subject result"
        assert profile["teardown_order"][-1] == "write the evidence statement"
        assert "force-flush ATOF subscribers" in profile["teardown_order"]
        assert profile["size_bounds"]["bounds_are_techtree_owned"]
        assert profile["privacy"]["raw_trace_publication"] == "forbidden"
        assert profile["privacy"]["atof_retention"] == "private_local_archive"


def test_the_four_coverage_statuses_are_distinguishable_from_the_fixture() -> None:
    events = atof_events()
    expected = expected_identities(events)
    assert expected  # a real denominator, not an empty one

    complete = calculate_coverage(requested=True, events=events, expected=expected)
    assert complete["status"] == "complete_for_profile"
    assert complete["missing_event_ids"] == []
    assert complete["unexpected_event_ids"] == []
    assert complete["reasons"] == []

    not_requested = calculate_coverage(requested=False, events=None, expected=expected)
    assert not_requested["status"] == "not_requested"
    assert not_requested["reasons"] == []

    unavailable = calculate_coverage(requested=True, events=[], expected=expected)
    assert unavailable["status"] == "unavailable"

    torn = calculate_coverage(
        requested=True, events=events, expected=expected, teardown_completed=False
    )
    assert torn["status"] == "unavailable"

    # Late registration drops the root scope start.
    late = calculate_coverage(requested=True, events=events[1:], expected=expected)
    assert late["status"] == "incomplete"
    assert late["missing_event_ids"] == ["fabric_execution_receipt/agent/scope_start/0"]

    # A root scope that never closed drops the root scope end.
    unclosed = calculate_coverage(requested=True, events=events[:-1], expected=expected)
    assert unclosed["status"] == "incomplete"
    assert unclosed["missing_event_ids"] == [
        "fabric_execution_receipt/agent/scope_end/0"
    ]

    # A recorded delivery diagnostic makes a structurally complete run
    # incomplete rather than complete.
    diagnosed = calculate_coverage(
        requested=True,
        events=events,
        expected=expected,
        diagnostics=["atof_sink_delivery_failed"],
    )
    assert diagnosed["status"] == "incomplete"

    # An empty denominator is never complete.
    assert (
        calculate_coverage(requested=True, events=events[1:], expected=[])["status"]
        == "incomplete"
    )

    # An identity the profile did not declare is recorded, not punished. The
    # denominator rule that forbids narrowing is a rule about how a profile is
    # written, not something the calculation infers from a surplus event.
    shrunk = [identity for identity in expected if "agent" not in identity]
    surplus = calculate_coverage(requested=True, events=events[1:], expected=shrunk)
    assert surplus["unexpected_event_ids"] == [
        "fabric_execution_receipt/agent/scope_end/0"
    ]
    assert surplus["reasons"] == []
    assert surplus["status"] == "complete_for_profile"
    for profile_path in PROFILE_PATHS.values():
        rule = load_json(profile_path)["calculation"]["unexpected_rule"]
        assert "never a reason for incomplete" in rule
        assert "unexpected_event_ids" in rule
        assert not any(
            "unexpected" in entry
            for entry in load_json(profile_path)["status_rules"]["incomplete"]
        )

    assert (
        len(
            {
                result["status"]
                for result in (complete, not_requested, unavailable, late)
            }
        )
        == 4
    )


def test_relay_holds_no_score_spend_or_execution_authority() -> None:
    lock = load_json(LOCK_PATH)["nemo_relay"]
    record = load_json(RECORD_PATH)

    for source in (lock, record["authority"]):
        assert source["may_affect_score"] is False
        assert source["may_affect_spend"] is False
        assert source["may_affect_execution"] is False
    assert lock["observe_only"] is True
    assert lock["streaming_service_introduced"] is False
    assert lock["public_raw_trace_path_introduced"] is False
    assert record["authority"]["streaming_service_introduced"] is False
    assert record["authority"]["public_raw_trace_path_introduced"] is False

    # Nothing was admitted, and no protected action ran.
    assert record["release_admitted"] is False
    assert lock["admission"] == (
        "blocked_pending_founder_release_admission_and_codex_relay_cli_band_decision"
    )
    assert lock["relay_cli_executed"] is False
    assert lock["gateway_launched"] is False
    assert lock["hermes_relay_run_observed"] is False
    assert lock["codex_relay_run_observed"] is False
    assert record["conformance_scope"]["host_relay_installation_modified"] is False
    assert record["conformance_scope"]["host_harness_installation_modified"] is False
    assert (
        record["conformance_scope"]["reusable_credential_copied_into_managed_runtime"]
        is False
    )

    # The Codex version conflict is recorded as a founder decision, not routed
    # around with a compatibility branch.
    codex = load_json(PROFILE_PATHS["nvidia.fabric.codex"])
    conflict = codex["version_conflict"]
    assert conflict["kind"] == "observed"
    assert codex["pinned_upstream"]["relay_cli_accepted_range"] == ">=0.7.2,<0.8.0"
    assert codex["pinned_upstream"]["newest_stable_relay_rejected_by_this_adapter"] == (
        "0.8.2"
    )
    assert "founder decision" in conflict["consequence"]
    assert "no compatibility shim" in conflict["consequence"].lower()
    gateway_source = (
        FIXTURE_ROOT / "source" / "fabric_relay_cli_version_contract.txt"
    ).read_text(encoding="utf-8")
    assert "RELAY_MINIMUM_VERSION = (0, 7, 2)" in gateway_source
    assert "RELAY_MAXIMUM_VERSION = (0, 8, 0)" in gateway_source
    assert "NeMo Fabric requires >=0.7.2,<0.8.0" in gateway_source


def test_retained_evidence_has_no_private_or_reusable_account_material() -> None:
    manifest = load_json(MANIFEST_PATH)
    scanned = sorted(path for path in FIXTURE_ROOT.rglob("*") if path.is_file())
    scanned += [CONTRACT_PATH, *PROFILE_PATHS.values(), PROFILE_ROOT / "README.md"]
    serialized = "\n".join(path.read_text(encoding="utf-8") for path in scanned)

    assert re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", serialized) is None
    assert "/Users/" not in serialized
    assert "/home/" not in serialized
    assert "/private/tmp/" not in serialized
    assert re.search(r"Bearer [A-Za-z0-9_-]{20,}", serialized) is None
    assert "sk-ant-" not in serialized
    assert "sk-proj-" not in serialized
    assert "OPENAI_API_KEY=" not in serialized
    assert "NVIDIA_API_KEY=" not in serialized
    assert all(value is False for value in manifest["sanitization"].values())

    for path in scanned:
        found = PROVIDER_ID_PATTERN.findall(path.read_text(encoding="utf-8"))
        assert found == [], f"{path.name}: {found[:3]}"
    assert PROVIDER_ID_PATTERN.search('"id": "a1b2c3d4e5f6g7h8j9k0m1n2"')

    # The only model coordinate anywhere in the retained evidence is a
    # placeholder, and the only endpoint is a loopback address.
    assert "placeholder-model" in ATOF_PATH.read_text(encoding="utf-8")
    for event in atof_events():
        payload = json.dumps(event)
        assert "api.openai.com" not in payload
        assert "integrate.api.nvidia.com" not in payload
        if "base_url" in payload:
            assert "http://127.0.0.1:" in payload
