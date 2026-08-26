"""Central protocol constants. Spec section 10.4.

This module holds values only. It imports nothing from the rest of the package
and defines no behavior, so every other module may import it freely without
creating a cycle.
"""

from __future__ import annotations

from typing import Final

#: Prefix that turns a bare SHA-256 hexadecimal string into a Techtree digest.
DIGEST_PREFIX: Final = "sha256:"

CLI_SCHEMA_VERSION: Final = "techtree.cli.v1"
CATALOG_SCHEMA_VERSION: Final = "techtree.catalog.v1alpha1"
CAMPAIGN_SCHEMA_VERSION: Final = "techtree.campaign.v1alpha1"
CLIMB_SCHEMA_VERSION: Final = "techtree.climb.v1alpha1"
DATA_POLICY_SCHEMA_VERSION: Final = "techtree.data-policy.v1alpha1"
EVALUATION_BACKEND_SCHEMA_VERSION: Final = "techtree.evaluation-backend.v1alpha1"
SKILL_SCHEMA_VERSION: Final = "techtree.skill.v1alpha1"
SUBMISSION_DRAFT_SCHEMA_VERSION: Final = "techtree.submission-draft.v1alpha1"
EXPERIMENT_SCHEMA_VERSION: Final = "techtree.experiment.v1alpha1"
TASKSET_LOCK_SCHEMA_VERSION: Final = "techtree.taskset-lock.v1alpha1"
TASKSET_VALIDATION_SCHEMA_VERSION: Final = "techtree.taskset-validation.v1alpha1"
#: Decisions document 0003 A1. The deterministic, normalized form of the raw
#: upstream validation output that a receipt points at.
VALIDATION_EVIDENCE_SCHEMA_VERSION: Final = "techtree.validation-evidence.v1alpha1"
#: Decisions document 0003 A1. Local operational provenance for one validation
#: execution. Never part of the Campaign graph.
VALIDATION_EXECUTION_SCHEMA_VERSION: Final = "techtree.validation-execution.v1alpha1"
EPISODE_RECEIPT_SCHEMA_VERSION: Final = "techtree.episode-receipt.v1alpha1"
UPLIFT_SCHEMA_VERSION: Final = "techtree.uplift-report.v1alpha1"
ENGINE_SCHEMA_VERSION: Final = "techtree.engine.v1alpha1"

#: Decisions document 0003 A9. Go/OCI-style ``<os>/<arch>`` strings are the
#: only host-platform spelling in the protocol. The tuple is ordered so that
#: generated descriptors and schemas list the vocabulary the same way every
#: time.
SUPPORTED_HOST_PLATFORMS: Final[tuple[str, ...]] = (
    "darwin/amd64",
    "darwin/arm64",
    "linux/amd64",
    "linux/arm64",
)

#: The subject container every generated Campaign pins, and the per-platform
#: manifests that index resolves to. Decisions document 0007 R5 makes this
#: release-blocking: a tag moves, so a Campaign naming one could not claim its
#: two variants ran the same subject, and a multi-platform index digest alone
#: does not say which bytes a given host ran.
#:
#: Hermes Agent is installed into the container at setup time from a PEP 723
#: script, so the image needs a shell, ``pip`` and nothing else; the agent's own
#: interpreter is provisioned by ``uv`` inside the container. That is why the
#: pin is a stock ``python:3.11-slim`` and not something Techtree publishes.
#:
#: Every digest below was read from the registry rather than written from
#: memory, on 2026-08-13::
#:
#:     docker image inspect python:3.11-slim --format '{{index .RepoDigests 0}}'
#:     docker manifest inspect python@sha256:90744cff...
#:
#: ``tests/preflight/test_subject_image_pin.py`` re-reads both and fails if the
#: registry ever stops agreeing with what is written here.
SUBJECT_IMAGE_REPOSITORY: Final = "python"
SUBJECT_IMAGE_TAG: Final = "3.11-slim"
SUBJECT_IMAGE_INDEX_DIGEST: Final = (
    "sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff"
)
SUBJECT_IMAGE: Final = f"{SUBJECT_IMAGE_REPOSITORY}@{SUBJECT_IMAGE_INDEX_DIGEST}"
SUBJECT_IMAGE_PLATFORM_DIGESTS: Final[dict[str, str]] = {
    "linux/amd64": (
        "sha256:78b39ef14d8e2b4d71f8dc304f1328c37df95fe0ef99477c2ae6bd3d03784553"
    ),
    "linux/arm64": (
        "sha256:20eadabc42589e6543b24a64ab305b9895e9fcf6dbb2cadb14812f394ecdbadf"
    ),
}

#: What the starter Skill is called in front of a person, and what the guided
#: first run files it under. Decisions document 0009 fixes the name and 0010
#: item 5 fixes the label; the two are deliberately different values, and
#: neither is ever derived from a path. A materialized Skill lives in a
#: directory named by the digest it was verified against, and a digest is
#: neither a name anybody would choose nor a label a candidate may carry.
STARTER_SKILL_NAME: Final = "hello-world-starter-v1"
STARTER_SKILL_CANDIDATE_LABEL: Final = "hello-world-v1"

#: Why the starter Skill is the shape it is. Decisions document 0010 item 2
#: amends 0007 R4: the Skill's own text stays silent about its gap, because a
#: Skill that announced one would be measuring something other than what it
#: says, and the release metadata discloses instead. This is that disclosure
#: on the command line, printed beside the Skill's name wherever it is handed
#: over — the same sentence the public Climb page and the calibration record
#: carry. It is release metadata about the artifact, never Skill content.
STARTER_SKILL_PURPOSE: Final = "intentionally incomplete introductory Skill"

DEFAULT_WORKER_HEARTBEAT_SECONDS: Final = 2
DEFAULT_STALE_HEARTBEAT_SECONDS: Final = 15

MAX_SKILL_FILE_BYTES: Final = 256 * 1024
MAX_SKILL_TOTAL_BYTES: Final = 2 * 1024 * 1024
MAX_SKILL_FILES: Final = 64

ALLOWED_SKILL_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
    }
)

#: Decisions document 0001. Never a branch, a tag, or an unpinned PyPI range.
#: Changing this value requires a dedicated dependency-bump change that reruns
#: the pinned-Verifiers preflight suite.
PINNED_VERIFIERS_REVISION: Final = "b2e4e8157783b2c0dffc7821044c87f29f1c3ccf"
