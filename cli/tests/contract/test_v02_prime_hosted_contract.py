"""WP0.3's Prime Hosted contract evidence and release blockers."""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any

from techtree.canonical import digest_object, sha256_digest_bytes

CLI_ROOT = Path(__file__).parents[2]
MONOREPO_ROOT = CLI_ROOT.parent
DOCS_ROOT = MONOREPO_ROOT / "docs" / "v0.2"
FIXTURE_ROOT = CLI_ROOT / "tests" / "fixtures" / "prime"
FIXTURE_PATH = FIXTURE_ROOT / "official_cli_0_6_31.json"
MANIFEST_PATH = FIXTURE_ROOT / "evidence_manifest.json"
RAW_OPENAPI_PATH = FIXTURE_ROOT / "openapi.json"
PROJECTION_PATH = FIXTURE_ROOT / "openapi_projection.json"
CONTRACT_PATH = DOCS_ROOT / "PRIME_HOSTED_CONTRACT.json"
LOCK_PATH = DOCS_ROOT / "UPSTREAM_CONTRACT_LOCK.json"

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
    for group in ("source_snapshots", "help_snapshots"):
        if record := manifest[group].get(ref):
            relative_path = record.get("path")
            assert isinstance(relative_path, str)
            return (MONOREPO_ROOT / relative_path).read_text(encoding="utf-8")
    raise AssertionError(f"missing retained capture: {ref}")


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
        for group in ("help_snapshots", "source_snapshots")
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
            and has_keys(listing, "evaluations", "total"),
            "shape_supported_response_unobserved",
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
            "skip: int" in methods and "hasMore" in models and "total_pages" in fields,
            "shape_supported_boundaries_unproven",
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

    for group, records in (
        ("source_snapshots", manifest["source_snapshots"]),
        ("help_snapshots", manifest["help_snapshots"]),
    ):
        for record in records.values():
            path = MONOREPO_ROOT / record["path"]
            assert path.is_file()
            if group == "source_snapshots":
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
    assert load_json(CONTRACT_PATH)["supported_machine_reads"] == []

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
    assert "@latest" in capture("prime_cli_hosted_resolver", manifest)
    assert "@latest" not in contract["environment"]["coordinate"]
    assert "@latest" not in lock["environment_coordinate"]
    assert fixture["live_hosted_mutation_observed"] is False
    assert fixture["paid_work_observed"] is False

    packets = contract["protected_action_packets"]
    publication = packets["publish_environment"]
    hosted_run = packets["paid_hosted_conformance_run"]
    assert publication["status"] == "prepared_but_not_requested"
    assert publication["intent_digest"] == digest_object(publication["intent"])
    assert publication["intent"]["maximum_authorized_cost_usd"] == "0"
    assert (
        publication["intent"]["environment_source_tree_digest"]
        == environment["package"]["project_tree_digest"]
    )
    assert (
        publication["intent"]["environment_wheel_sha256"]
        == environment["package"]["wheel"]["sha256"]
    )
    assert publication["action_taken"] is False
    assert hosted_run["status"] == "blocked_not_ready_for_approval"
    assert hosted_run["intent_digest"] is None
    assert hosted_run["action_taken"] is False
    assert {
        "published immutable Prime environment version identifier",
        "supported structured create, logs, and cancel surface",
        "provider estimate and maximum-cost semantics",
    }.issubset(hosted_run["missing_before_exact_packet"])
    assert all(value is False for value in contract["external_effects"].values())


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
