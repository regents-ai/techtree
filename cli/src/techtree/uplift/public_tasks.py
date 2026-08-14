"""What may be shown about a task, taskset by taskset. Decisions R1, 0014.

Ratified decision R1 lets an improvement context carry a task's *public input*
and forbids it carrying the subject's reply, the expected answer, grader
source, or any hidden field. It also says the disclosure policy is
taskset-specific and must never be inferred: "not secret" is not something to
work out from a taskset nobody wrote a policy for.

So this module is a lookup, not a rule. A taskset this build knows the policy
for gets a projection that names its public input; every other taskset gets
:func:`~techtree.uplift.context.hash_only_projection`, which names a task by
its position and the head of its committed hash and shows nothing else. Adding
a taskset here is a deliberate act, and the absence of one is a safe answer
rather than a missing feature.

Why it matters that the input is shown at all: the introductory Climb's whole
subject is a Skill with one wrong rule in it, and which tasks it fails is the
evidence for finding that rule. A reader given only "task 11 failed" and a hash
cannot see a pattern in the inputs, because it has not been shown any. That is
not privacy, it is an absence of evidence, and decision 0014 records what it
cost: two rehearsal attempts in which the model diagnosed a defect the
membership does not contain.

The answer never travels. What is read here is the frozen input list the
reference taskset ships; the oracle that turns an input into an answer sits in
the same package and is not imported, called, or reproduced.
"""

from __future__ import annotations

import importlib.util
import sys
from typing import Final

from techtree.engines.bundle import embedded_engine_root
from techtree.errors import ValidationError
from techtree.models.base import Digest
from techtree.models.campaign import CampaignSpec
from techtree.uplift.context import (
    TaskPublicProjection,
    TaskPublicProjectionProvider,
    hash_only_projection,
)

__all__ = [
    "public_projection_for",
]

#: The one taskset this build has a disclosure policy for. Spec section 22:
#: its inputs are single lowercase common tree names, its prompt template is
#: published verbatim, and its answers are the only part that is withheld.
_REFERENCE_TASKSET: Final = "procedure-transfer-v1"

#: Where the frozen input list lives inside the packaged engine bundle. The
#: module beside it computes answers and is deliberately not touched.
_DATASET_MODULE: Final = "dataset.py"


def public_projection_for(campaign: CampaignSpec) -> TaskPublicProjectionProvider:
    """Return how much of each task this Campaign's taskset may show.

    Args:
        campaign: The Campaign whose committed membership is being projected.

    Returns:
        A provider naming each task's public input when the taskset has a
        disclosure policy here, and the hash-only provider when it has none.
    """
    reference = campaign.taskset.ref
    if reference.id != _REFERENCE_TASKSET or reference.package.name != (
        _REFERENCE_TASKSET
    ):
        return hash_only_projection
    return _branch_code_projection(campaign)


def _branch_code_projection(campaign: CampaignSpec) -> TaskPublicProjectionProvider:
    """Name each committed task by the public input the subject was given."""
    committed = list(campaign.taskset.membership.ordered_task_hashes)
    inputs = _proving_inputs()

    def project(*, task_hash: Digest, position: int) -> TaskPublicProjection:
        # The position and the hash have to agree before either is trusted to
        # pick an input. They come from the same receipt, so a disagreement
        # means the receipt and the Campaign are describing different runs, and
        # labelling a task with another task's input would be worse than
        # showing nothing.
        if (
            position >= len(committed)
            or position >= len(inputs)
            or committed[position] != task_hash
        ):
            return hash_only_projection(task_hash=task_hash, position=position)
        named = hash_only_projection(task_hash=task_hash, position=position)
        return TaskPublicProjection(
            task_label=named.task_label,
            public_prompt=inputs[position],
        )

    return project


def _proving_inputs() -> tuple[str, ...]:
    """Read the reference taskset's frozen public inputs, and nothing else.

    The module is loaded from the packaged bundle by path rather than
    imported by name: the package's ``__init__`` pulls in Verifiers, which
    belongs to the managed engine environment and is not resolvable here. Only
    the pure input list is wanted, and it has no dependency of its own beyond
    the normalizer in the same package.
    """
    package = (
        embedded_engine_root()
        / "packages"
        / _REFERENCE_TASKSET
        / _REFERENCE_TASKSET.replace("-", "_")
    )
    module_name = f"{_REFERENCE_TASKSET.replace('-', '_')}.dataset"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return tuple(cached.PROVING_INPUTS)

    algorithm_name = f"{_REFERENCE_TASKSET.replace('-', '_')}.algorithm"
    for name, filename in (
        (algorithm_name, "algorithm.py"),
        (module_name, _DATASET_MODULE),
    ):
        if name in sys.modules:
            continue
        location = package / filename
        specification = importlib.util.spec_from_file_location(name, str(location))
        if specification is None or specification.loader is None:
            raise ValidationError(
                "this build cannot read the reference taskset's public inputs",
                details={"module": name},
            )
        module = importlib.util.module_from_spec(specification)
        sys.modules[name] = module
        specification.loader.exec_module(module)

    return tuple(sys.modules[module_name].PROVING_INPUTS)
