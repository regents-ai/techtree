"""WP0.2's proposed Verifiers and deterministic-environment commitments."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from techtree.canonical import sha256_digest_bytes
from techtree.engines.bundle import package_source_digest
from techtree.tasksets.membership import membership_digest

CLI_ROOT = Path(__file__).parents[2]
MONOREPO_ROOT = CLI_ROOT.parent
DOCS_ROOT = MONOREPO_ROOT / "docs" / "v0.2"
ENVIRONMENT_ROOT = CLI_ROOT / "tests" / "conformance" / "prime_environment"


def load_json(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def candidate_by_id(document: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    candidates = document["candidates"]
    assert isinstance(candidates, list)
    return next(
        candidate for candidate in candidates if candidate["id"] == candidate_id
    )


def test_stable_candidate_passed_and_the_development_fallback_did_not_run() -> None:
    candidates = load_json(DOCS_ROOT / "UPSTREAM_CANDIDATES.json")
    stable = candidate_by_id(candidates, "verifiers-stable-0.3.1")
    fallback = candidate_by_id(candidates, "verifiers-fallback-0.3.2.dev17")

    assert candidates["selected_candidate"]["verifiers"] == stable["id"]
    assert candidates["selection_status"] == "proposed_for_adoption"
    assert candidates["final_adoption"] == "pending_founder_approval"
    assert stable["status_history"] == [
        "discovered",
        "approved_for_spike",
        "conformance_passed",
        "proposed_for_adoption",
    ]
    assert stable["source_commit"] == "b2e4e8157783b2c0dffc7821044c87f29f1c3ccf"
    assert stable["wheel_sha256"] == (
        "sha256:105cd114184625895b3d1a07ddc418f08a0ddadcd9cb20dad5acb763ccb01725"
    )
    assert fallback["status_history"] == ["discovered"]
    assert fallback["spike"] == {
        "status": "not_run",
        "reason": "stable_candidate_passed",
    }
    assert fallback["source_commit"] == "c51c094a4018471b7fdc873eb5cb55bbd5e956e1"
    assert fallback["wheel_sha256"] == (
        "sha256:68c23a7c48b0544f5e98fd7fee433e1e96c96b7713a3ac2215b856770481b035"
    )


def test_proposed_lock_names_the_passing_stable_candidate_without_adopting_it() -> None:
    lock = load_json(DOCS_ROOT / "UPSTREAM_CONTRACT_LOCK.json")
    candidates = load_json(DOCS_ROOT / "UPSTREAM_CANDIDATES.json")
    candidate = candidate_by_id(candidates, "verifiers-stable-0.3.1")
    fallback = candidate_by_id(candidates, "verifiers-fallback-0.3.2.dev17")
    verifiers = lock["verifiers"]

    assert lock["status"] == "contract_spike_pending"
    assert lock["approved_at"] is None
    assert verifiers["package_version"] == candidate["version"]
    assert verifiers["source_commit"] == candidate["source_commit"]
    assert verifiers["wheel_filename"] == candidate["wheel_filename"]
    assert verifiers["wheel_sha256"] == candidate["wheel_sha256"]
    assert verifiers["admission"] == "proposed_for_adoption"
    assert verifiers["fallback_candidate_status"] == "discovered"
    assert verifiers["fallback_spike"] == fallback["spike"]
    assert verifiers["historical_v0_1_engine_lock_unchanged"] is True

    serialized = json.dumps(verifiers).lower()
    assert "latest" not in serialized
    assert '"main"' not in serialized


def test_environment_manifest_binds_the_exact_source_lock_scorer_and_membership() -> (
    None
):
    manifest_path = DOCS_ROOT / "PRIME_CONFORMANCE_ENVIRONMENT.json"
    manifest = load_json(manifest_path)
    candidates = load_json(DOCS_ROOT / "UPSTREAM_CANDIDATES.json")
    stable = candidate_by_id(candidates, "verifiers-stable-0.3.1")

    assert manifest["status"] == "local_conformance_passed"
    assert manifest["publication"] == {
        "status": "not_published",
        "protected_action_required": True,
        "owner": "@techtree",
        "visibility": "public",
        "prime_environment_id": None,
        "prime_environment_version_id": None,
    }
    assert "not a benchmark" in manifest["purpose"]
    assert manifest["evaluation_engine"]["version"] == stable["version"]
    assert manifest["evaluation_engine"]["source_commit"] == stable["source_commit"]
    assert manifest["evaluation_engine"]["wheel_sha256"] == stable["wheel_sha256"]
    assert stable["conformance"]["environment_manifest_sha256"] == (
        sha256_digest_bytes(manifest_path.read_bytes())
    )

    package = manifest["package"]
    assert package["project_tree_digest"] == package_source_digest(ENVIRONMENT_ROOT)
    assert package["python_package_digest"] == package_source_digest(
        ENVIRONMENT_ROOT / "techtree_v02_conformance"
    )
    assert package["pyproject_digest"] == sha256_digest_bytes(
        (ENVIRONMENT_ROOT / "pyproject.toml").read_bytes()
    )
    assert package["lockfile_digest"] == sha256_digest_bytes(
        (ENVIRONMENT_ROOT / "uv.lock").read_bytes()
    )
    assert package["license"] == "MIT"
    assert package["license_digest"] == sha256_digest_bytes(
        (ENVIRONMENT_ROOT / "LICENSE").read_bytes()
    )

    taskset = manifest["taskset"]
    assert taskset["source_digest"] == sha256_digest_bytes(
        (ENVIRONMENT_ROOT / "techtree_v02_conformance" / "taskset.py").read_bytes()
    )
    assert taskset["task_count"] == len(taskset["tasks"]) == 4
    assert [task["position"] for task in taskset["tasks"]] == list(range(4))
    assert taskset["membership_digest"] == membership_digest(
        [task["task_hash"] for task in taskset["tasks"]]
    )

    scorer = manifest["scorer"]
    assert manifest["environment"]["source_digest"] == sha256_digest_bytes(
        (ENVIRONMENT_ROOT / "techtree_v02_conformance" / "env.py").read_bytes()
    )
    assert scorer["source_digest"] == sha256_digest_bytes(
        (ENVIRONMENT_ROOT / "techtree_v02_conformance" / "scoring.py").read_bytes()
    )
    assert scorer["kind"] == "deterministic_exact_match"
    assert scorer["judge_model"] is None


def test_environment_project_uses_only_the_exact_stable_verifiers_dependency() -> None:
    project = tomllib.loads((ENVIRONMENT_ROOT / "pyproject.toml").read_text())
    lock = tomllib.loads((ENVIRONMENT_ROOT / "uv.lock").read_text())

    assert project["project"]["dependencies"] == ["verifiers==0.3.1"]
    assert project["project"]["license"] == "MIT"
    assert project["project"]["license-files"] == ["LICENSE"]
    assert not (ENVIRONMENT_ROOT / "techtree_v02_conformance" / "harness.py").exists()

    verifiers = next(
        package for package in lock["package"] if package["name"] == "verifiers"
    )
    assert verifiers["version"] == "0.3.1"
    assert {
        wheel["hash"]
        for wheel in verifiers["wheels"]
        if wheel["url"].endswith("verifiers-0.3.1-py3-none-any.whl")
    } == {"sha256:105cd114184625895b3d1a07ddc418f08a0ddadcd9cb20dad5acb763ccb01725"}


def test_environment_manifest_makes_no_unearned_execution_claim() -> None:
    manifest = load_json(DOCS_ROOT / "PRIME_CONFORMANCE_ENVIRONMENT.json")

    assert manifest["constraints"] == {
        "environment_network_client": False,
        "environment_secrets": False,
        "tools": False,
        "customer_data": False,
        "hidden_answers": False,
        "performance_claim": False,
    }
    assert manifest["local_conformance"]["model_calls_requested"] is False
    assert manifest["local_conformance"]["credentials_required"] is False
    assert manifest["future_paths"] == {
        "local_model_run": {"status": "not_run"},
        "prime_hosted_run": {
            "status": "not_run",
            "reason": "blocked_by_upstream_contract_and_protected_action",
        },
        "provider_hosted_rerun": {
            "status": "not_run",
            "reason": "protected_action_required",
        },
        "fabric_hermes_run": {"status": "not_run"},
        "relay_complete_run": {"status": "not_run"},
        "relay_incomplete_run": {"status": "not_run"},
    }
