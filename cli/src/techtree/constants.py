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
EXPERIMENT_SCHEMA_VERSION: Final = "techtree.experiment.v1alpha1"
TASKSET_LOCK_SCHEMA_VERSION: Final = "techtree.taskset-lock.v1alpha1"
TASKSET_VALIDATION_SCHEMA_VERSION: Final = "techtree.taskset-validation.v1alpha1"
EPISODE_RECEIPT_SCHEMA_VERSION: Final = "techtree.episode-receipt.v1alpha1"
UPLIFT_SCHEMA_VERSION: Final = "techtree.uplift-report.v1alpha1"

DEFAULT_CONFIRMATION_TTL_SECONDS: Final = 900
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
PINNED_VERIFIERS_REVISION: Final = "7e1c47d24d055aae587ee8259f77a3e8e193513a"
