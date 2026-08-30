"""One package exporting a Taskset, an Env and a Harness through one ``__all__``.

Spec section 6.5 relies on Verifiers filtering a package's exported classes by
the requested base type, so that a single reference package can carry both the
taskset and the named-subject environment. This fixture proves that filtering
with three plugin kinds at once, which is one more than the reference package
will ever need.
"""

from techtree_preflight_subject.env import SubjectEnv, SubjectEnvConfig
from techtree_preflight_subject.harness import StubHarness, StubHarnessConfig
from techtree_preflight_subject.taskset import (
    SubjectData,
    SubjectTask,
    SubjectTaskset,
)

__all__ = [
    "StubHarness",
    "StubHarnessConfig",
    "SubjectData",
    "SubjectEnv",
    "SubjectEnvConfig",
    "SubjectTask",
    "SubjectTaskset",
]
