"""Model-visible tool schemas. Specification section 7.4.

One schema per declared tool. The descriptions are written for the host agent
that has to choose between them, so each says when the tool applies and what
it costs: which tools are read-only, which change the host, and which spend
model budget on an evaluated run.

Four things never appear in a schema here: an API key, an executable path, an
installation command, and an unbounded identifier. Anything the plugin runs is
built from release data and the fixed CLI contract, never from these arguments.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any, Final

# Bounded value patterns ------------------------------------------------------

_RUN_ID_PATTERN: Final = r"^run_[0-9a-f]{32}$"
_DRAFT_ID_PATTERN: Final = r"^draft_[0-9a-f]{32}$"
_PLAN_ID_PATTERN: Final = r"^install_[0-9a-f]{32}$"
_DIGEST_PATTERN: Final = r"^sha256:[0-9a-f]{64}$"
_CLIMB_REFERENCE_PATTERN: Final = r"^[a-z0-9][a-z0-9-]{0,63}(@[0-9A-Za-z.-]{1,16})?$"
_TOKEN_PATTERN: Final = r"^[A-Za-z0-9_-]{16,128}$"
_LABEL_PATTERN: Final = r"^[0-9A-Za-z][0-9A-Za-z ._-]{0,63}$"

_CHANNEL: Final = {
    "type": "string",
    "enum": ["terminal", "gateway", "unknown"],
    "description": (
        "Where the answer will be read. Use 'terminal' only for an attached "
        "terminal session and 'gateway' for phone or chat. When omitted the "
        "plugin assumes 'unknown' and returns compact text with no escape codes."
    ),
}

_PATH_NOTE: Final = (
    "Must be a filesystem path the user identified explicitly in this "
    "conversation. Never guess a path, complete one, or reuse one the plugin "
    "returned for a different purpose."
)


def _run_id(purpose: str) -> dict[str, Any]:
    return {
        "type": "string",
        "pattern": _RUN_ID_PATTERN,
        "description": purpose,
    }


def _schema(
    description: str,
    properties: Mapping[str, Any],
    required: Sequence[str] = (),
    one_of: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "description": description,
        "properties": {**properties, "channel": dict(_CHANNEL)},
        "required": list(required),
        "additionalProperties": False,
    }
    if one_of is not None:
        schema["oneOf"] = [dict(branch) for branch in one_of]
    return schema


_TOOL_SCHEMAS: Final[dict[str, dict[str, Any]]] = {
    "techtree_bootstrap_check": _schema(
        description=(
            "Report whether this host can run Techtree: whether the Techtree "
            "CLI is installed, whether it matches the release this plugin was "
            "built against, and what the next step is. Read-only and free: it "
            "installs nothing and starts no evaluation. Run this first in any "
            "Techtree conversation."
        ),
        properties={
            "include_doctor": {
                "type": "boolean",
                "description": (
                    "Also run Techtree's own Doctor when the CLI is present. "
                    "Doctor inspects Docker, the evaluation engine, the "
                    "catalog, and evaluation-provider authentication. Free, "
                    "but slower than the plain check."
                ),
            }
        },
    ),
    "techtree_bootstrap_install": _schema(
        description=(
            "Install the pinned Techtree CLI release using the plan that "
            "techtree_bootstrap_check produced. This changes software on the "
            "user's machine and always requires the user to approve the exact "
            "command through the host's normal terminal approval. The package, "
            "the version, and every flag come from the plan; nothing about the "
            "command can be supplied here."
        ),
        properties={
            "plan_id": {
                "type": "string",
                "pattern": _PLAN_ID_PATTERN,
                "description": (
                    "The identifier of the unexpired plan returned by "
                    "techtree_bootstrap_check."
                ),
            }
        },
        required=["plan_id"],
    ),
    "techtree_system_check": _schema(
        description=(
            "Run Techtree's Doctor and report each readiness check separately: "
            "CLI release, managed engine, Docker, public catalog, host "
            "platform, and evaluation-provider authentication. Read-only and "
            "free. Use it when something failed and you need to know which "
            "part of the host is not ready."
        ),
        properties={},
    ),
    "techtree_climbs_list": _schema(
        description=(
            "List the Climbs this Techtree build offers. Read-only and free. "
            "Use it before inspecting or preparing anything."
        ),
        properties={},
    ),
    "techtree_climb_inspect": _schema(
        description=(
            "Show what one Climb measures: its Campaign summary, its data "
            "rights, the model and provider it requires, how many tasks it "
            "runs, its cost bound, its proof grade, and whether this host can "
            "run it. Read-only and free. Always inspect and show these facts "
            "before asking the user to approve a run."
        ),
        properties={
            "reference": {
                "type": "string",
                "pattern": _CLIMB_REFERENCE_PATTERN,
                "description": "A Climb reference such as 'example-climb@1'.",
            }
        },
        required=["reference"],
    ),
    "techtree_climb_prepare": _schema(
        description=(
            "Prepare a candidate Skill for one Climb. Preparation is free and "
            "starts nothing: it scans the Skill, freezes a draft, and returns "
            "the draft identifier, the data-policy digest, and a one-time "
            "confirmation token that techtree_climb_start will need. For the "
            "guided introduction use techtree_demo_prepare instead."
        ),
        properties={
            "reference": {
                "type": "string",
                "pattern": _CLIMB_REFERENCE_PATTERN,
                "description": "The Climb to prepare the Skill for.",
            },
            "skill_path": {
                "type": "string",
                "minLength": 1,
                "maxLength": 4096,
                "description": (
                    "The candidate Skill directory or its SKILL.md. " + _PATH_NOTE
                ),
            },
            "label": {
                "type": "string",
                "pattern": _LABEL_PATTERN,
                "description": "What to call this candidate in the result.",
            },
        },
        required=["reference", "skill_path"],
    ),
    "techtree_demo_prepare": _schema(
        description=(
            "Prepare Techtree Hello World, the toy Skill-uplift Climb, with "
            "the founder-supplied hello-world-starter-v1 Skill: check the "
            "CLI, run Doctor, materialize the starter Skill by its pinned "
            "digest, and prepare a draft. Free and starts nothing. It returns "
            "the exact field that changes between the two runs, the "
            "data-policy summary, the episode and budget estimate, and the "
            "confirmation token the user must approve before any model "
            "spending happens. Hello World demonstrates how the mechanism "
            "works; it is not a measure of broad capability."
        ),
        properties={},
    ),
    "techtree_climb_start": _schema(
        description=(
            "Start a prepared draft running. This spends model budget and "
            "provisions Docker, so call it only after the user has seen the "
            "cost, the data policy, and the Skill, and has said yes. Model "
            "inference goes to the model provider the user configured, under "
            "that provider's policies; Techtree uploads nothing of its own. "
            "The run is detached: this returns a run identifier immediately "
            "and never waits for the result."
        ),
        properties={
            "draft_id": {
                "type": "string",
                "pattern": _DRAFT_ID_PATTERN,
                "description": "The prepared draft to start.",
            },
            "confirmation_token": {
                "type": "string",
                "pattern": _TOKEN_PATTERN,
                "description": (
                    "The one-time token the preparation step returned. It is "
                    "not a credential and is never reused."
                ),
            },
            "data_policy_digest": {
                "type": "string",
                "pattern": _DIGEST_PATTERN,
                "description": (
                    "The exact data-policy digest the user accepted. Never "
                    "infer acceptance; the digest must come from the "
                    "preparation result the user was shown."
                ),
            },
        },
        required=["draft_id", "confirmation_token", "data_policy_digest"],
    ),
    "techtree_run_status": _schema(
        description=(
            "Report how a detached run is progressing. Read-only, free, and "
            "returns immediately. Poll it occasionally rather than waiting; "
            "a Climb takes minutes, not seconds."
        ),
        properties={"run_id": _run_id("The run to report on.")},
        required=["run_id"],
    ),
    "techtree_run_cancel": _schema(
        description=(
            "Stop a run that is still in progress. Destroys the run's "
            "in-flight work and cannot be undone, so call it only when the "
            "user explicitly asked to cancel."
        ),
        properties={"run_id": _run_id("The run to stop.")},
        required=["run_id"],
    ),
    "techtree_run_result": _schema(
        description=(
            "Return the finished report for a completed run: the comparison "
            "outcome, the uplift report, and the local proof path. Read-only "
            "and free. Everything it returns is Techtree's own output, "
            "relayed unchanged and with no model asked to describe it; the "
            "result was not independently reproduced by anyone else, and must "
            "never be described as if it were."
        ),
        properties={"run_id": _run_id("The completed run to read.")},
        required=["run_id"],
    ),
    "techtree_proof_verify": _schema(
        description=(
            "Check a local proof bundle offline and report its integrity, "
            "scientific, and attestation checks separately. Read-only and "
            "free: the check itself reads stored bytes and reaches no "
            "network. Give either a run identifier or a proof path, not both."
        ),
        properties={
            "run_id": _run_id("The run whose stored proof should be checked."),
            "proof_path": {
                "type": "string",
                "minLength": 1,
                "maxLength": 4096,
                "description": "A local proof bundle path. " + _PATH_NOTE,
            },
        },
        one_of=[
            {"required": ["run_id"], "not": {"required": ["proof_path"]}},
            {"required": ["proof_path"], "not": {"required": ["run_id"]}},
        ],
    ),
    "techtree_uplift_context": _schema(
        description=(
            "Export the sanitized improvement context for a finished run: what "
            "Techtree is willing to reveal about how the Skill performed. Read-"
            "only and free. It never contains hidden task answers or the "
            "subject's final replies, and nothing outside it may be used to "
            "revise a Skill."
        ),
        properties={"run_id": _run_id("The finished run to build context from.")},
        required=["run_id"],
    ),
    "techtree_uplift_propose": _schema(
        description=(
            "Propose one revision of the Skill a finished run measured, and "
            "show what changed. Reads the sanitized improvement context, asks "
            "the host model exactly once, hands the proposal to Techtree to "
            "scan and prepare, and stops. It spends no model budget on an "
            "evaluation and starts nothing. The guided introduction allows one "
            "proposal; a failed attempt still uses it up. Tell the user before "
            "calling it: this one request sends the Skill being revised and "
            "the sanitized improvement context to the model provider behind "
            "the agent they are talking to, which is a different provider "
            "from the one the evaluated run uses. Show the user the diff, the "
            "data policy, and the estimate before starting anything."
        ),
        properties={
            "source_run_id": _run_id("The finished run whose Skill should be revised."),
            "confirmation_token": {
                "type": "string",
                "pattern": _TOKEN_PATTERN,
                "description": (
                    "Omit it the first time. The tool then sends nothing and "
                    "returns the disclosure of exactly what would leave this "
                    "machine, with a one-time token. Read that disclosure out "
                    "in full, and pass the token back only if the user agrees "
                    "to it. The token works once."
                ),
            },
        },
        required=["source_run_id"],
    ),
    "techtree_uplift_prepare": _schema(
        description=(
            "Prepare a comparison between a finished run's Skill and a revised "
            "version of it. Free and starts nothing. Show the user the diff "
            "between the two Skills and the data policy before starting the "
            "comparison this prepares."
        ),
        properties={
            "run_id": _run_id("The finished run whose Skill becomes the baseline."),
            "revised_skill_path": {
                "type": "string",
                "minLength": 1,
                "maxLength": 4096,
                "description": (
                    "The revised Skill directory or its SKILL.md. " + _PATH_NOTE
                ),
            },
            "label": {
                "type": "string",
                "pattern": _LABEL_PATTERN,
                "description": "What to call the revision in the result.",
            },
        },
        required=["run_id", "revised_skill_path"],
    ),
    "techtree_uplift_start": _schema(
        description=(
            "Start a prepared Skill-against-Skill comparison. This spends "
            "model budget, so call it only after the user has seen the Skill "
            "diff, the data policy, and the budget, and has approved this "
            "second run specifically. Returns a run identifier immediately."
        ),
        properties={
            "draft_id": {
                "type": "string",
                "pattern": _DRAFT_ID_PATTERN,
                "description": "The prepared replacement to start.",
            },
            "confirmation_token": {
                "type": "string",
                "pattern": _TOKEN_PATTERN,
                "description": "The one-time token the preparation step returned.",
            },
            "data_policy_digest": {
                "type": "string",
                "pattern": _DIGEST_PATTERN,
                "description": (
                    "The exact data-policy digest the user accepted for this "
                    "second run."
                ),
            },
        },
        required=["draft_id", "confirmation_token", "data_policy_digest"],
    ),
}


def all_tool_schemas() -> Mapping[str, dict[str, Any]]:
    """Return the name-to-schema mapping used for registration and tests.

    The returned mapping is read-only and its schemas are copies, so a caller
    that hands one to a registry cannot reach back and change what the plugin
    declares.
    """
    return MappingProxyType(copy.deepcopy(_TOOL_SCHEMAS))


__all__ = ["all_tool_schemas"]
