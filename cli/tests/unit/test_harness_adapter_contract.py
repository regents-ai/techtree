"""Adapter invariants over synthetic in-memory version metadata.

These are not recordings or evidence that a newer upstream agent was executed.
"""

from dataclasses import replace

import pytest

from fixtures.receipts.pair import recorded_pair
from techtree.receipts.compare import _tool_surface_check
from techtree.verifiers.models import VariantName


@pytest.mark.parametrize("version", ["0.19.0", "0.21.1", "1.0.0-rc.1"])
def test_paired_tool_contract_does_not_use_a_runtime_version_allowlist(
    version: str,
) -> None:
    pair = recorded_pair()
    variants = []
    for variant in (VariantName.BASELINE, VariantName.CANDIDATE):
        observed = pair.observed(variant)
        variants.append(
            replace(
                observed,
                configuration=observed.configuration.model_copy(
                    update={"harness_version": version}
                ),
            )
        )
    assert _tool_surface_check(*variants).status == "passed"


@pytest.mark.parametrize("inventory", ["empty", "duplicate"])
def test_invalid_inventory_cannot_be_hidden_by_dictionary_deduplication(
    inventory: str,
) -> None:
    pair = recorded_pair()
    baseline = pair.observed(VariantName.BASELINE)
    candidate = pair.observed(VariantName.CANDIDATE)
    tools = [] if inventory == "empty" else [*candidate.tools, candidate.tools[0]]
    assert (
        _tool_surface_check(baseline, replace(candidate, tools=tools)).status
        == "failed"
    )


def test_another_adapter_does_not_inherit_the_hermes_description_exception() -> None:
    pair = recorded_pair()
    variants = []
    for variant in (VariantName.BASELINE, VariantName.CANDIDATE):
        observed = pair.observed(variant)
        variants.append(
            replace(
                observed,
                configuration=observed.configuration.model_copy(
                    update={"harness_id": "codex"}
                ),
            )
        )
    assert _tool_surface_check(*variants).status == "failed"
