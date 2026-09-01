"""WP0.3's Prime Hosted contract evidence and release blockers."""

from __future__ import annotations

import json
import re
import shlex
import tomllib
from pathlib import Path
from typing import Any

from techtree.canonical import digest_object, sha256_digest_bytes

CLI_ROOT = Path(__file__).parents[2]
MONOREPO_ROOT = CLI_ROOT.parent
DOCS_ROOT = MONOREPO_ROOT / "docs" / "v0.2"
FIXTURE_ROOT = CLI_ROOT / "tests" / "fixtures" / "prime"
RESPONSE_ROOT = FIXTURE_ROOT / "responses"
FIXTURE_PATH = FIXTURE_ROOT / "official_cli_0_6_31.json"
MANIFEST_PATH = FIXTURE_ROOT / "evidence_manifest.json"
RAW_OPENAPI_PATH = FIXTURE_ROOT / "openapi.json"
PROJECTION_PATH = FIXTURE_ROOT / "openapi_projection.json"
CONTRACT_PATH = DOCS_ROOT / "PRIME_HOSTED_CONTRACT.json"
LOCK_PATH = DOCS_ROOT / "UPSTREAM_CONTRACT_LOCK.json"
CONFORMANCE_PYPROJECT = (
    CLI_ROOT / "tests" / "conformance" / "prime_environment" / "pyproject.toml"
)

EVIDENCE_GROUPS = ("source_snapshots", "help_snapshots", "response_snapshots")

#: Prime returns collision-resistant identifiers for its own environments,
#: versions, teams, and jobs. They are provider-internal and are persisted
#: nowhere, so this pattern rejects any bare token of their observed shape
#: rather than the specific values that were seen.
PROVIDER_ID_PATTERN = re.compile(r"(?<![0-9a-z])[0-9a-z]{24,25}(?![0-9a-z])")

#: The upstream OpenAPI document is retained verbatim and bound by the digest
#: the provider publishes. It predates every account action recorded here and
#: contains ordinary camel-case words that the pattern would flag.
PROVIDER_ID_SCAN_EXEMPT = {RAW_OPENAPI_PATH}

OPENAPI_REFS = {
    "openapi_hosted_create": ("path", "/api/v1/hosted-evaluations", "post"),
    "openapi_logs": (
        "path",
        "/api/v1/hosted-evaluations/{evaluation_id}/logs",
        "get",
    ),
    "openapi_stop": (
        "path",
        "/api/v1/hosted-evaluations/{evaluation_id}/cancel",
        "patch",
    ),
    "openapi_evaluation_get": (
        "path",
        "/api/v1/evaluations/{evaluation_id}",
        "get",
    ),
    "openapi_evaluation_list": ("path", "/api/v1/evaluations/", "get"),
    "openapi_samples": (
        "path",
        "/api/v1/evaluations/{evaluation_id}/samples",
        "get",
    ),
    "openapi_status": (
        "schema",
        {"EvaluationStatus"},
        None,
    ),
}


def load_json(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def capture(ref: str, manifest: dict[str, Any]) -> str:
    for group in EVIDENCE_GROUPS:
        if record := manifest[group].get(ref):
            relative_path = record.get("path")
            assert isinstance(relative_path, str)
            return (MONOREPO_ROOT / relative_path).read_text(encoding="utf-8")
    raise AssertionError(f"missing retained capture: {ref}")


def response(ref: str, manifest: dict[str, Any]) -> dict[str, Any]:
    document = json.loads(capture(ref, manifest))
    assert isinstance(document, dict)
    return document


def has_option(text: str, option: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(option)}(?=[\s,]|$)", text) is not None


def has_keys(text: str, *keys: str) -> bool:
    return all(re.search(rf"\b{re.escape(key)}\b", text) for key in keys)


def contains(text: str, *fragments: str) -> bool:
    return all(fragment in text for fragment in fragments)


def has_output(text: str) -> bool:
    return has_option(text, "--output")


def claim(condition: bool, supported: str, unsupported: str = "unsupported") -> str:
    return supported if condition else unsupported


def schema(projection: dict[str, Any], name: str) -> dict[str, Any]:
    result = projection["schemas"].get(name)
    assert isinstance(result, dict), f"missing OpenAPI schema: {name}"
    return result


def derive_statuses(
    manifest: dict[str, Any], projection: dict[str, Any]
) -> dict[str, str]:
    t = {
        ref: capture(ref, manifest)
        for group in EVIDENCE_GROUPS
        for ref in manifest[group]
    }
    run = t["prime_eval_run"]
    methods = t["prime_evals_methods"]
    models = t["prime_evals_models"]
    teams = t["prime_teams_list"]
    env = t["prime_env_inspect"]
    get = t["prime_eval_get"]
    listing = t["prime_eval_list"]
    samples = t["prime_eval_samples"]
    logs = t["prime_eval_logs"]
    stop = t["prime_eval_stop"]
    resolver = t["prime_cli_hosted_resolver"]
    create = t["prime_cli_hosted_create"]
    client = t["prime_cli_api_client"]
    status = t["prime_cli_hosted_status"]
    env_listing = response("prime_env_list_owned", manifest)
    empty_env_listing = response("prime_env_list_owned_empty", manifest)
    empty_eval_listing = response("prime_eval_list_empty", manifest)
    env_status = response("prime_env_status_owned", manifest)
    action_listing = response("prime_env_action_list_owned", manifest)
    action_logs = t["prime_env_action_logs_owned"]
    exact_version_listing = t["prime_env_inspect_owned"]
    action = action_listing["actions"][0]
    fields = set(schema(projection, "GetSamplesResponse")["properties"])
    cli_statuses = set(re.findall(r'^\s+[A-Z]+ = "([A-Z]+)"$', status, re.M))
    api_statuses = set(schema(projection, "EvaluationStatus").get("enum", []))
    request = json.dumps(schema(projection, "CreateHostedEvaluationRequest"))
    return {
        "account_team_discovery": claim(
            has_output(teams) and has_keys(teams, "teamId", "slug"),
            "shape_supported_response_unobserved",
        ),
        "environment_exact_read": claim(
            has_option(env, "--version") and has_output(env) and "version_id" in env,
            "shape_supported_response_unobserved",
        ),
        "evaluation_get": claim(
            has_output(get)
            and "async def get_evaluation" in methods
            and "evaluation_id" in get,
            "shape_supported_response_unobserved",
        ),
        "evaluation_list": claim(
            has_output(listing)
            and "async def list_evaluations" in methods
            and has_keys(listing, "evaluations", "total")
            and set(empty_eval_listing) == {"evaluations", "total", "skip", "limit"}
            and empty_eval_listing["evaluations"] == []
            and empty_eval_listing["total"] == 0,
            "supported_machine_read_observed_empty_collection",
        ),
        "environment_list": claim(
            set(env_listing) == {"environments", "total", "page", "per_page"}
            and set(empty_env_listing) == set(env_listing)
            and empty_env_listing["environments"] == []
            and empty_env_listing["total"] == 0
            and env_listing["total"] == len(env_listing["environments"]) == 1
            and set(env_listing["environments"][0])
            == {
                "environment",
                "description",
                "visibility",
                "version",
                "stars",
                "updated_at",
            },
            "supported_machine_read_observed",
        ),
        "environment_status_read": claim(
            set(env_status)
            == {
                "id",
                "name",
                "description",
                "visibility",
                "owner",
                "latest_version",
                "action",
            }
            and set(env_status["latest_version"])
            == {"version_id", "semantic_version", "content_hash", "created_at"}
            and env_status["visibility"] == "PUBLIC"
            and env_status["latest_version"]["semantic_version"] == "0.1.0"
            and env_status["id"].startswith("<redacted-")
            and env_status["latest_version"]["version_id"].startswith("<redacted-"),
            "supported_machine_read_observed_with_provider_ids_redacted",
        ),
        "environment_publication_action": claim(
            env_status["action"]["status"] == action["status"] == "FAILED"
            and action["name"] == "Integration Test"
            and action["trigger"] == "PUSH"
            and action["exit_code"] == 1
            and action["version"]["semantic_version"] == "0.1.0"
            and "AssertionError: pyproject.toml does not have tags" in action_logs
            and contains(
                action_logs,
                "test_pyproject_has_metadata FAILED",
                "test_install_and_import PASSED",
                "test_readme_exists PASSED",
                "1 failed, 3 passed",
            ),
            "hub_integration_test_failed_on_missing_tags_metadata",
        ),
        "environment_action_list": claim(
            set(action_listing) == {"actions", "total", "limit", "offset"}
            and action_listing["total"] == len(action_listing["actions"]) == 1
            and action["id"].startswith("<redacted-")
            and action["version"]["id"].startswith("<redacted-"),
            "supported_machine_read_observed_with_provider_ids_redacted",
        ),
        "environment_action_logs": claim(
            "test session starts" in action_logs
            and not action_logs.lstrip().startswith("{"),
            "provider_log_text_observed",
        ),
        "environment_exact_version_listing": claim(
            "techtree/techtree-v02-conformance@0.1.0" in exact_version_listing
            and contains(exact_version_listing, "pyproject.toml", "README.md")
            and not exact_version_listing.lstrip().startswith("{"),
            "human_output_only_observed",
        ),
        "samples_results": claim(
            has_output(samples)
            and "async def get_samples" in methods
            and "hasMore" in models
            and "total_pages" in fields,
            "shape_supported_response_unobserved_with_openapi_drift",
        ),
        "hosted_environment_selection": claim(
            has_option(run, "--hosted")
            and contains(resolver, "/environmentshub/", "@latest"),
            "unsupported_for_immutable_selection",
        ),
        "hosted_create": claim(
            has_option(run, "--hosted")
            and 'client.post("/hosted-evaluations"' in create
            and not has_option(run, "--output"),
            "unsupported_machine_contract",
        ),
        "logs": claim(
            "hosted evaluation" in logs.lower() and not has_output(logs),
            "unsupported_machine_contract",
        ),
        "stop": claim(
            "stop a running hosted evaluation" in stop.lower() and not has_output(stop),
            "unsupported_machine_contract",
        ),
        "terminal_failure": claim(
            "terminal_statuses" in status
            and "PROCESSING" not in cli_statuses
            and "PROCESSING" in api_statuses,
            "source_proven_shape_live_behavior_unobserved",
            "unproven",
        ),
        "pagination": claim(
            "skip: int" in methods
            and "hasMore" in models
            and "total_pages" in fields
            #: Three observed listings, three different pagination envelopes.
            and {"page", "per_page"} <= set(env_listing)
            and {"skip", "limit"} <= set(empty_eval_listing)
            and {"limit", "offset"} <= set(action_listing)
            and not {"page", "per_page"} & set(empty_eval_listing)
            and not {"page", "per_page", "skip"} & set(action_listing),
            "shape_supported_boundaries_unproven_with_observed_envelope_divergence",
            "unproven",
        ),
        "ambiguous_transport": claim(
            "idempotency" not in create.lower(),
            "unsupported_provider_idempotency",
            "supported_shape",
        ),
        "billing_principal": claim(
            "team_id" in create and "billing" not in (create + request).lower(),
            "not_exposed_as_safe_provider_record",
            "supported_shape",
        ),
        "artifact_access": claim(
            not any(
                term in (get + samples).lower()
                for term in ("artifact", "bundle", "download")
            ),
            "unsupported",
            "supported_shape",
        ),
        "fabric_custom_harness": claim(
            "fabric" not in run.lower(), "unproven", "supported_shape"
        ),
        "transport_safety": claim(
            contains(client, "follow_redirects=True", "response.json()"),
            "unsupported_by_official_clients",
            "supported_shape",
        ),
    }


def openapi_ref_exists(ref: str, projection: dict[str, Any]) -> bool:
    kind, target, method = OPENAPI_REFS[ref]
    if kind == "schema":
        return all(name in projection["schemas"] for name in target)
    return method in projection["paths"].get(target, {})


def test_exact_candidate_evidence_and_digest_chain() -> None:
    fixture = load_json(FIXTURE_PATH)
    manifest = load_json(MANIFEST_PATH)
    contract = load_json(CONTRACT_PATH)
    lock = load_json(LOCK_PATH)["prime_hosted_evaluations"]
    cli = manifest["artifacts"]["prime_cli_wheel"]
    sdk = manifest["artifacts"]["prime_evals_wheel"]
    api = manifest["artifacts"]["public_openapi"]

    assert manifest["isolated_resolution"] == fixture["isolated_resolution"]
    assert (cli["package"], cli["version"]) == ("prime", "0.6.31")
    assert (sdk["package"], sdk["version"]) == ("prime-evals", "0.2.3")
    assert api["availability"] == "provider_retrievable"
    assert api["raw_bytes_retained"] is True
    assert api["raw_path"] == "cli/tests/fixtures/prime/openapi.json"
    assert api["sha256"] == sha256_digest_bytes(RAW_OPENAPI_PATH.read_bytes())
    assert api["size_bytes"] == RAW_OPENAPI_PATH.stat().st_size
    assert api["projection_sha256"] == sha256_digest_bytes(PROJECTION_PATH.read_bytes())

    candidate = contract["candidate_selection"]
    assert candidate["candidate"] == f"prime=={cli['version']}"
    assert candidate["source_commit"] == cli["source_commit"]
    assert candidate["wheel_sha256"] == cli["sha256"]
    assert candidate["public_sdk"] == f"prime-evals=={sdk['version']}"
    assert candidate["public_sdk_wheel_sha256"] == sdk["sha256"]
    assert candidate["api_generation"] == fixture["api_generation"]
    assert lock["cli_version"] == cli["version"]
    assert lock["source_commit"] == cli["source_commit"]
    assert lock["wheel_sha256"] == cli["sha256"]
    assert lock["client_package"] == sdk["package"]
    assert lock["client_version"] == sdk["version"]
    assert lock["client_wheel_sha256"] == sdk["sha256"]

    fixture_digest = sha256_digest_bytes(FIXTURE_PATH.read_bytes())
    manifest_digest = sha256_digest_bytes(MANIFEST_PATH.read_bytes())
    projection_digest = sha256_digest_bytes(PROJECTION_PATH.read_bytes())
    assert contract["fixture"]["sha256"] == fixture_digest
    assert contract["fixture"]["evidence_manifest_sha256"] == manifest_digest
    assert contract["fixture"]["openapi_projection_sha256"] == projection_digest
    assert lock["fixture_sha256"] == fixture_digest
    assert lock["evidence_manifest_sha256"] == manifest_digest
    assert lock["openapi_projection_sha256"] == projection_digest
    assert lock["contract_record_sha256"] == sha256_digest_bytes(
        CONTRACT_PATH.read_bytes()
    )
    assert FIXTURE_PATH.stat().st_size < 16 * 1024


def test_all_claims_use_retained_evidence_and_recorded_eval_paths_are_guarded() -> None:
    fixture = load_json(FIXTURE_PATH)
    manifest = load_json(MANIFEST_PATH)
    projection = load_json(PROJECTION_PATH)
    refs = {
        ref
        for operation in fixture["operations"].values()
        for ref in operation.get("evidence_refs", [])
    } | set(fixture["status_evidence"].values())
    for ref in refs:
        assert (
            openapi_ref_exists(ref, projection)
            if ref.startswith("openapi_")
            else capture(ref, manifest).strip()
        ), ref

    for group in EVIDENCE_GROUPS:
        for record in manifest[group].values():
            path = MONOREPO_ROOT / record["path"]
            assert path.is_file()
            if group == "response_snapshots":
                assert record["command"].startswith("prime --plain ")
                assert record["size_bytes"] == path.stat().st_size
                assert sha256_digest_bytes(path.read_bytes()) == record["sha256"]
                assert record["content"] in {
                    "verbatim_provider_response",
                    "redacted_provider_response",
                }
                if record["content"] == "redacted_provider_response":
                    assert record["redacted_fields"]
                assert record["capture_order"] in {
                    "before_the_environment_publication",
                    "after_the_environment_publication",
                    "not_recorded_relative_to_the_environment_publication",
                }
            elif group == "source_snapshots":
                assert record["artifact"] in manifest["artifacts"]
                assert record["member_sha256"].startswith("sha256:")
                assert record["member_size_bytes"] >= record["excerpt_size_bytes"]
                lines = path.read_text(encoding="utf-8").splitlines()
                assert len(lines) == record["line_end"] - record["line_start"] + 1
                assert path.stat().st_size == record["excerpt_size_bytes"]
                assert (
                    sha256_digest_bytes(path.read_bytes()) == record["excerpt_sha256"]
                )
            else:
                assert record["size_bytes"] > 0
                assert sha256_digest_bytes(path.read_bytes()) == record["sha256"]

    raw = load_json(RAW_OPENAPI_PATH)
    assert projection["source"]["raw_bytes_retained"] is True
    assert projection["source"]["raw_path"] == "cli/tests/fixtures/prime/openapi.json"
    assert projection["source"]["sha256"] == sha256_digest_bytes(
        RAW_OPENAPI_PATH.read_bytes()
    )
    assert projection["source"]["size_bytes"] == RAW_OPENAPI_PATH.stat().st_size
    for path, value in projection["paths"].items():
        assert raw["paths"][path] == value
    for name, value in projection["schemas"].items():
        assert raw["components"]["schemas"][name] == value

    derived = derive_statuses(manifest, projection)
    assert {name: op["status"] for name, op in fixture["operations"].items()} == derived
    assert set(fixture["operations"]) == set(derived)

    contract = load_json(CONTRACT_PATH)
    reads = contract["supported_machine_reads"]
    assert reads
    assert {read["operation"] for read in reads} == {
        name
        for name, status in derived.items()
        if status.startswith("supported_machine_read_observed")
    }
    retained = {
        record["path"]: record for record in manifest["response_snapshots"].values()
    }
    for read in reads:
        record = retained[read["fixture"]]
        observed = json.loads((MONOREPO_ROOT / read["fixture"]).read_text("utf-8"))
        assert read["command"] == record["command"]
        assert read["observed_envelope_keys"] == sorted(observed)
        assert read["limits"]

    #: The owned environment listing is a before-and-after pair around the one
    #: publication, and it is the only read captured before it.
    ordering = {
        name: record["capture_order"]
        for name, record in manifest["response_snapshots"].items()
    }
    assert ordering["prime_env_list_owned_empty"] == (
        "before_the_environment_publication"
    )
    assert ordering["prime_env_list_owned"] == "after_the_environment_publication"
    assert [
        name
        for name, order in ordering.items()
        if order == "before_the_environment_publication"
    ] == ["prime_env_list_owned_empty"]
    assert response("prime_env_list_owned_empty", manifest)["total"] == 0
    assert response("prime_env_list_owned", manifest)["total"] == 1

    commands = [
        record["command"]
        for record in fixture["runnable_commands"].values()
        if record["command"].startswith("prime eval run ")
    ] + [
        operation["machine_surface"]
        for operation in fixture["operations"].values()
        if operation.get("machine_surface", "").startswith("prime eval run ")
    ]
    assert commands
    assert all("--skip-upload" in shlex.split(command) for command in commands)
    assert has_option(capture("prime_eval_run", manifest), "--skip-upload")


def test_prime_blockers_and_protected_actions_remain_bound() -> None:
    fixture = load_json(FIXTURE_PATH)
    contract = load_json(CONTRACT_PATH)
    lock = load_json(LOCK_PATH)["prime_hosted_evaluations"]
    environment = load_json(DOCS_ROOT / "PRIME_CONFORMANCE_ENVIRONMENT.json")
    manifest = load_json(MANIFEST_PATH)
    projection = load_json(PROJECTION_PATH)
    derived = derive_statuses(manifest, projection)

    assert lock["admission"] == "blocked_by_upstream_contract"
    assert (
        derived["hosted_environment_selection"] == "unsupported_for_immutable_selection"
    )
    assert derived["hosted_create"] == "unsupported_machine_contract"
    assert derived["logs"] == "unsupported_machine_contract"
    assert derived["stop"] == "unsupported_machine_contract"
    assert derived["ambiguous_transport"] == "unsupported_provider_idempotency"
    assert derived["transport_safety"] == "unsupported_by_official_clients"
    assert derived["pagination"] == (
        "shape_supported_boundaries_unproven_with_observed_envelope_divergence"
    )

    #: The drift finding has to name every envelope that was actually seen, or
    #: the machine-readable record understates what the capture found.
    drift = next(
        blocker["finding"]
        for blocker in contract["confirmed_release_blockers"]
        if blocker["id"] == "prime_hosted_status_and_pagination_schema_drift"
    )
    limits = fixture["operations"]["pagination"]["observed_limits"]
    for envelope in ("page and per_page", "skip and limit", "limit and offset"):
        assert envelope in drift
        assert envelope in limits
    assert "three observed list envelopes" in drift
    assert "three observed list envelopes" in limits

    assert "@latest" in capture("prime_cli_hosted_resolver", manifest)
    assert "@latest" not in contract["environment"]["coordinate"]
    assert "@latest" not in lock["environment_coordinate"]
    assert fixture["live_hosted_mutation_observed"] is False
    assert fixture["paid_work_observed"] is False

    packets = contract["protected_action_packets"]
    publication = packets["publish_environment"]
    hosted_run = packets["paid_hosted_conformance_run"]
    execution = publication["execution"]
    published = environment["publication"]
    assert publication["status"] == "approved_and_executed"
    assert publication["intent_digest"] == digest_object(publication["intent"])
    assert publication["intent"]["maximum_authorized_cost_usd"] == "0"
    assert (
        publication["intent"]["environment_source_tree_digest"]
        == environment["package"]["project_tree_digest"]
    )
    assert (
        publication["intent"]["environment_wheel_sha256"]
        == environment["package"]["wheel"]["sha256"]
        == execution["observed_wheel_sha256"]
        == published["observed_wheel_sha256"]
    )
    assert publication["action_taken"] is True
    assert publication["executed_at"] == published["executed_at"] == "2026-09-01"
    assert execution["command"] == published["command"]
    assert execution["cost_usd_incurred"] == published["cost_usd"] == "0"
    assert execution["evaluation_created"] is False
    assert execution["model_call_made"] is False
    assert execution["wheel_matches_approved_packet"] is True

    #: The evidence manifest states the same provider action in its own words.
    #: Bind the two so neither can be softened without the other.
    observed = manifest["provider_actions_observed"]["environment_publication"]
    assert observed["action_kind"] == publication["intent"]["action_kind"]
    assert observed["executed_at"] == publication["executed_at"]
    assert observed["cost_usd"] == execution["cost_usd_incurred"] == "0"
    assert observed["evaluation_created"] == execution["evaluation_created"] is False
    assert observed["model_call_made"] == execution["model_call_made"] is False
    assert observed["founder_approved"] is True
    assert execution["approved_by"] == "founder"
    assert manifest["provider_actions_observed"]["hosted_evaluation_mutation"] is None
    assert hosted_run["status"] == "blocked_not_ready_for_approval"
    assert hosted_run["intent_digest"] is None
    assert hosted_run["action_taken"] is False
    assert {
        "published immutable Prime environment version identifier",
        "supported structured create, logs, and cancel surface",
        "provider estimate and maximum-cost semantics",
    }.issubset(hosted_run["missing_before_exact_packet"])
    assert contract["external_effects"] == {
        "environment_published": True,
        "paid_run_started": False,
        "provider_resource_mutated": True,
        "upstream_issue_or_pull_request_sent": False,
        "final_lock_adopted": False,
    }


def test_publication_did_not_relax_any_prime_admission_ruling() -> None:
    contract = load_json(CONTRACT_PATH)
    lock = load_json(LOCK_PATH)["prime_hosted_evaluations"]
    environment = load_json(DOCS_ROOT / "PRIME_CONFORMANCE_ENVIRONMENT.json")
    fixture = load_json(FIXTURE_PATH)

    assert contract["release_scope"] == {
        "prime_hosted": "v0.2.x",
        "v0_2_0_admission": "inadmissible",
        "decided_at": "2026-09-01",
        "decision": (
            "Founder decision: Prime Hosted moves to v0.2.x, and the hosted gap "
            "recorded in this document is inadmissible for v0.2.0."
        ),
        "plan_and_ticket_rescope": "tracked separately from this document",
    }
    assert contract["candidate_selection"]["admission"] == lock["admission"]
    assert contract["candidate_selection"]["v0_2_0_admission"] == "inadmissible"
    assert lock["v0_2_0_admission"] == "inadmissible"
    assert contract["candidate_selection"]["release_scope"] == lock["release_scope"]

    published = environment["publication"]
    recorded = contract["environment"]
    assert published["status"] == recorded["publication_status"] == "published"
    assert lock["environment_publication_status"] == "published"
    assert published["evaluation_or_model_call_performed"] is False
    assert environment["future_paths"]["prime_hosted_run"]["status"] == "not_run"
    assert fixture["environment_publication_observed"] is True
    assert fixture["live_hosted_mutation_observed"] is False

    #: The provider hands back its own identifiers on publication. None of them
    #: is written down, here or anywhere else in the retained evidence.
    assert recorded["prime_environment_id"] is None
    assert recorded["prime_environment_version_id"] is None
    assert published["prime_environment_id"] is None
    assert published["prime_environment_version_id"] is None
    assert lock["environment_id"] is None
    assert lock["environment_version_id"] is None

    #: The provider returns a content hash of its own. It is a digest rather
    #: than an identifier, so it is retained, but it binds to nothing Techtree
    #: computed and cannot stand in for an integrity check.
    content_hash = recorded["provider_content_hash"]
    assert content_hash == published["provider_content_hash"]
    assert content_hash == lock["environment_provider_content_hash"]
    assert recorded["provider_content_hash_algorithm_declared"] is False
    assert recorded["provider_content_hash_matches_a_techtree_digest"] is False
    assert f"sha256:{content_hash}" not in json.dumps(environment)

    #: Publication proved the environment exists at 0.1.0. It proved nothing
    #: about the hosted path, and it surfaced a failed provider action.
    assert recorded["immutable_version_reference_available_to_hosted_run"] is False
    assert recorded["observed_provider_action_status"] == "FAILED"
    assert lock["environment_provider_action_status"] == "FAILED"
    assert {blocker["id"] for blocker in contract["confirmed_release_blockers"]} == {
        "prime_hosted_immutable_environment_selection",
        "prime_hosted_structured_mutations",
        "prime_hosted_provider_idempotency",
        "prime_hosted_transport_integrity",
        "prime_hosted_status_and_pagination_schema_drift",
        "prime_hosted_estimate_and_billing_binding",
        "prime_hosted_environment_hub_requires_non_standard_tags",
    }


def test_the_failed_hub_action_states_its_cause_and_stays_unfixed() -> None:
    contract = load_json(CONTRACT_PATH)
    environment = load_json(DOCS_ROOT / "PRIME_CONFORMANCE_ENVIRONMENT.json")
    lock = load_json(LOCK_PATH)["prime_hosted_evaluations"]
    published = environment["publication"]
    recorded = contract["environment"]
    blocker = next(
        entry
        for entry in contract["confirmed_release_blockers"]
        if entry["id"] == "prime_hosted_environment_hub_requires_non_standard_tags"
    )

    #: The action failed for a known reason, and the reason is named rather
    #: than described as unknown.
    assert "tags" in blocker["finding"]
    assert "PEP 621" in blocker["finding"]
    assert recorded["observed_provider_action_note"] == blocker["finding"]
    assert published["provider_action_note"] == blocker["finding"]
    assert recorded["observed_provider_action_name"] == "Integration Test"
    assert recorded["observed_provider_action_trigger"] == "PUSH"

    #: Three of the hub's four checks passed, so the honest claim is narrow:
    #: installable and importable, not hub-validated.
    assert recorded["installable_and_importable_per_hub_test"] is True
    assert published["installable_and_importable_per_hub_test"] is True
    assert recorded["hub_validated"] is False
    assert published["hub_validated"] is False
    assert lock["environment_hub_validated"] is False
    assert lock["environment_hub_validation_gap"] == (
        "hub_integration_test_requires_non_standard_tags_metadata"
    )

    #: Fixing it means a new published version, which is a new protected
    #: action. Nothing here may quietly change the tree that produced 0.1.0.
    republish = contract["protected_action_packets"][
        "republish_environment_with_hub_tags"
    ]
    assert republish["status"] == "required_not_prepared_not_requested"
    assert republish["intent_digest"] is None
    assert republish["action_taken"] is False
    assert "founder approval" in republish["approval"]
    assert "tags" in republish["required_change"]

    pyproject = tomllib.loads(
        (CONFORMANCE_PYPROJECT).read_text(encoding="utf-8"),
    )
    assert "tags" not in pyproject["project"]
    assert pyproject["project"]["version"] == published["observed_semantic_version"]


def test_retained_evidence_has_no_private_or_reusable_account_material() -> None:
    manifest = load_json(MANIFEST_PATH)
    contract = load_json(CONTRACT_PATH)
    evidence = "\n".join(
        path.read_text(encoding="utf-8")
        for path in FIXTURE_ROOT.rglob("*")
        if path.is_file()
    )
    public = evidence + (DOCS_ROOT / "PRIME_CONTRACT.md").read_text(encoding="utf-8")
    serialized = public + json.dumps(contract, ensure_ascii=True)

    assert re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", serialized) is None
    assert "/Users/" not in serialized
    assert re.search(r"Bearer [A-Za-z0-9_-]{20,}", serialized) is None
    assert "sk-ant-" not in serialized
    assert "sk-proj-" not in serialized
    assert "PRIME_API_KEY=" not in serialized
    assert "Regents Labs" not in public
    assert json.dumps(contract).count("Regents Labs") == 1
    assert all(value is False for value in manifest["sanitization"].values())
    assert manifest["sanitization"]["provider_internal_ids_persisted"] is False
    assert (
        manifest["sanitization"]["protected_hosted_evaluation_mutation_observed"]
        is False
    )


def test_no_retained_file_carries_a_provider_internal_identifier() -> None:
    scanned = [
        path
        for path in sorted(FIXTURE_ROOT.rglob("*"))
        if path.is_file() and path not in PROVIDER_ID_SCAN_EXEMPT
    ] + [
        DOCS_ROOT / name
        for name in (
            "PRIME_CONTRACT.md",
            "PRIME_HOSTED_CONTRACT.json",
            "PRIME_CONFORMANCE_ENVIRONMENT.json",
            "UPSTREAM_CONTRACT_LOCK.json",
            "UPSTREAM_CANDIDATES.json",
        )
    ]
    assert RAW_OPENAPI_PATH in PROVIDER_ID_SCAN_EXEMPT
    assert set(RESPONSE_ROOT.iterdir()) <= set(scanned)
    for path in scanned:
        found = PROVIDER_ID_PATTERN.findall(path.read_text(encoding="utf-8"))
        assert not found, f"{path}: {sorted(set(found))}"

    #: The scan has to be able to fail, so prove it catches the shape it is for.
    #: These are synthetic tokens of the observed length, not observed values.
    assert PROVIDER_ID_PATTERN.search('"id": "a1b2c3d4e5f6g7h8j9k0m1n2"')
    assert PROVIDER_ID_PATTERN.search("a1b2c3d4e5f6g7h8j9k0m1n2p")
    assert not PROVIDER_ID_PATTERN.search(sha256_digest_bytes(b"prime"))
    assert not PROVIDER_ID_PATTERN.search("<redacted-provider-environment-id>")
