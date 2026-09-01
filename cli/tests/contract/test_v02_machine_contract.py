"""The v0.2 machine contract, bound to the code it describes. WP0.6.

``docs/v0.2/MACHINE_CONTRACT.md`` freezes ``techtree.cli.v2``: eleven stable
operation identifiers that *describe existing CLI handlers* rather than create a
second command hierarchy, and a five-state public projection over the detailed
append-only run phases.

A document that names a handler is a document that can be wrong about it. These
tests make it impossible to be wrong for long: every handler the inventory
cites must exist and be registered as a command, every registered command must
be described by some operation, and the projection table must cover every
``RunPhase`` exactly once. WP0 changes no runtime behavior, so this is the only
thing holding the document to the code until WP1 replaces the envelope.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest
import typer

from techtree.cli.app import create_app
from techtree.models.run import RunPhase

CLI_ROOT = Path(__file__).parents[2]
MONOREPO_ROOT = CLI_ROOT.parent
CONTRACT_PATH = MONOREPO_ROOT / "docs" / "v0.2" / "MACHINE_CONTRACT.md"

#: The identifiers the binding plan names, in the order it names them.
PLANNED_OPERATIONS: frozenset[str] = frozenset(
    {
        "plan.prepare",
        "plan.inspect",
        "action.prepare",
        "action.execute",
        "run.status",
        "run.wait",
        "run.reconcile",
        "run.cancel",
        "result.inspect",
        "claim.inspect",
        "proof.verify",
    }
)

#: The five public states the plan projects the internal phases onto.
PUBLIC_STATES: frozenset[str] = frozenset(
    {"prepared", "running", "completed", "failed", "cancelled"}
)

#: The five retry classes a typed next action may carry.
RETRY_CLASSES: frozenset[str] = frozenset(
    {
        "safe",
        "safe_after_delay",
        "reconcile_first",
        "human_decision_required",
        "forbidden",
    }
)

#: ``module:function``, the way the document cites a handler.
HANDLER_REFERENCE = re.compile(
    r"`(techtree(?:\.[a-z_][a-z0-9_]*)+):([a-z_][a-z0-9_]*)`"
)

#: A backticked operation identifier: two dotted lowercase words.
OPERATION_REFERENCE = re.compile(r"`([a-z_]+\.[a-z_]+)`")


def contract_text() -> str:
    """Return the machine contract, insisting it is where it says it is."""
    assert CONTRACT_PATH.is_file(), f"{CONTRACT_PATH} is missing"
    return CONTRACT_PATH.read_text(encoding="utf-8")


def section(text: str, heading: str) -> str:
    """Return one ``##``-level section's body, heading excluded."""
    lines = text.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.strip() == heading), None
    )
    assert start is not None, f"the contract has no section {heading!r}"
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


def table_rows(text: str) -> list[list[str]]:
    """Return the cells of every Markdown table row in ``text``.

    Header and separator rows are dropped, so a row is a row of data.
    """
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(set(cell) <= {"-", ":"} and cell for cell in cells):
            continue
        rows.append(cells)
    return rows


def first_table(text: str) -> list[list[str]]:
    """Return the first table in ``text``, stopping where it ends.

    A section holds several tables — the shape, then the value sets its fields
    draw from — and the first one is the shape.
    """
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if rows:
                break
            continue
        rows.extend(table_rows(line))
    return rows


def inventory_rows() -> list[list[str]]:
    """Return the operation-inventory table's data rows."""
    rows = table_rows(section(contract_text(), "## Operation inventory"))
    # The header names the columns; every row after it describes one operation.
    assert rows[0][0] == "Operation", "the inventory table lost its header"
    return rows[1:]


def registered_handlers(app: typer.Typer) -> dict[str, tuple[str, ...]]:
    """Return every command callback the application registers.

    Keyed by ``module:function``, valued by the command paths that reach it, so
    a failure names the command a reader would recognize rather than a symbol.
    """
    found: dict[str, list[str]] = {}

    def walk(group: typer.Typer, path: tuple[str, ...]) -> None:
        for command in group.registered_commands:
            callback = command.callback
            assert callback is not None
            name = command.name or callback.__name__
            reference = f"{callback.__module__}:{callback.__name__}"
            found.setdefault(reference, []).append(" ".join((*path, name)))
        for subgroup in group.registered_groups:
            instance = subgroup.typer_instance
            assert instance is not None
            assert subgroup.name is not None
            walk(instance, (*path, subgroup.name))

    walk(app, ())
    return {reference: tuple(paths) for reference, paths in found.items()}


@pytest.fixture(scope="module")
def handlers() -> dict[str, tuple[str, ...]]:
    return registered_handlers(create_app())


# ---------------------------------------------------------------------------
# The operation inventory
# ---------------------------------------------------------------------------


def test_the_inventory_names_exactly_the_planned_operations() -> None:
    """Eleven identifiers, no more and no fewer."""
    documented = {row[0].strip("`") for row in inventory_rows()}
    assert documented == PLANNED_OPERATIONS


def test_every_cited_handler_exists_and_is_a_registered_command(
    handlers: dict[str, tuple[str, ...]],
) -> None:
    """An operation may only describe a handler the CLI actually has.

    This is the whole point of the inventory: the identifiers describe existing
    handlers rather than promising a second command hierarchy. A citation that
    names nothing, or names a function that is not wired to a command, is a
    promise the CLI does not keep.
    """
    for row in inventory_rows():
        operation = row[0].strip("`")
        cited = HANDLER_REFERENCE.findall(" | ".join(row))
        assert cited, f"{operation} cites no handler"
        for module, function in cited:
            reference = f"{module}:{function}"
            assert reference in handlers, (
                f"{operation} cites {reference}, which is not a registered "
                f"techtree command"
            )


def test_every_registered_command_is_described_by_an_operation(
    handlers: dict[str, tuple[str, ...]],
) -> None:
    """No command may exist outside the machine surface.

    A command the inventory does not describe is a command a host agent can
    only reach by parsing human output, which is the thing the contract exists
    to prevent.
    """
    described = {
        f"{module}:{function}"
        for row in inventory_rows()
        for module, function in HANDLER_REFERENCE.findall(" | ".join(row))
    }
    undescribed = {
        reference: paths
        for reference, paths in handlers.items()
        if reference not in described
    }
    assert not undescribed, (
        "these commands are not described by any v2 operation: "
        f"{sorted(path for paths in undescribed.values() for path in paths)}"
    )


def test_every_symbol_the_document_cites_exists() -> None:
    """The prose cites code too, and prose drifts more quietly than a table.

    The inventory's citations are checked against the registered commands
    above. This checks the rest: the helpers, the digest function, and the two
    different routes by which publication eligibility is reached. A citation
    that has been renamed out from under the document is the kind of error that
    survives a careful read, because the sentence around it still sounds true.
    """
    cited = sorted(set(HANDLER_REFERENCE.findall(contract_text())))
    assert cited, "the contract cites no code at all"
    for module_name, symbol in cited:
        module = importlib.import_module(module_name)
        assert hasattr(module, symbol), (
            f"the contract cites {module_name}:{symbol}, which does not exist"
        )


def test_no_operation_outside_the_inventory_is_used_as_an_identifier() -> None:
    """Every dotted identifier the document treats as an operation is one."""
    text = contract_text()
    prefixes = {operation.split(".", 1)[0] for operation in PLANNED_OPERATIONS}
    used = {
        candidate
        for candidate in OPERATION_REFERENCE.findall(text)
        if candidate.split(".", 1)[0] in prefixes
    }
    assert used <= PLANNED_OPERATIONS, f"undeclared operations: {sorted(used)}"


# ---------------------------------------------------------------------------
# The public state projection
# ---------------------------------------------------------------------------


def test_the_projection_covers_every_run_phase_exactly_once() -> None:
    """Twelve internal phases in, five public states out, nothing implicit.

    A phase added to ``RunPhase`` without a row here would otherwise project to
    whatever the reader assumed, which for a run's public state is the
    difference between "still going" and "stopped".
    """
    rows = table_rows(section(contract_text(), "## The public state projection"))
    assert rows[0][0] == "Internal phase", "the projection table lost its header"
    projection = {row[0].strip("`"): row[1].strip("`") for row in rows[1:]}

    assert len(projection) == len(rows) - 1, "the projection lists a phase twice"
    assert set(projection) == {phase.value for phase in RunPhase}
    assert set(projection.values()) == PUBLIC_STATES


def test_a_run_asked_to_stop_is_not_reported_as_stopped() -> None:
    """``cancel_requested`` projects to ``running``.

    Cancellation is cooperative: a run that has been asked to stop has not
    stopped and may still end in ``failed``.
    """
    rows = table_rows(section(contract_text(), "## The public state projection"))
    projection = {row[0].strip("`"): row[1].strip("`") for row in rows[1:]}
    assert projection[RunPhase.CANCEL_REQUESTED.value] == "running"


# ---------------------------------------------------------------------------
# The envelope and its typed next actions
# ---------------------------------------------------------------------------


def test_the_envelope_documents_exactly_the_eleven_planned_fields() -> None:
    rows = first_table(section(contract_text(), "## The envelope"))
    assert rows[0][0] == "Field", "the envelope table lost its header"
    documented = [row[0].strip("`") for row in rows[1:]]
    assert documented == [
        "schema_version",
        "operation",
        "ok",
        "state_digest",
        "facts",
        "unknowns",
        "blockers",
        "warnings",
        "content_refs",
        "next_actions",
        "error",
    ]


def test_a_next_action_documents_exactly_the_nine_planned_fields() -> None:
    body = section(contract_text(), "## Typed next actions")
    # The first table is the entry itself; the ones after it are its value sets.
    rows = first_table(body)
    assert rows[0][0] == "Field", "the next-action table lost its header"
    documented = [row[0].strip("`") for row in rows[1:]]
    assert documented == [
        "operation",
        "prepared_arguments",
        "expected_state_digest",
        "side_effect",
        "approval_required",
        "retry_class",
        "estimated_cost",
        "data_egress",
        "reason",
    ]


def test_the_five_retry_classes_are_the_ones_the_plan_names() -> None:
    body = section(contract_text(), "## Typed next actions")
    documented = {
        row[0].strip("`")
        for row in table_rows(body)
        if row[0].strip("`") in RETRY_CLASSES
    }
    assert documented == RETRY_CLASSES


# ---------------------------------------------------------------------------
# The boundaries the decision ledger set
# ---------------------------------------------------------------------------


def test_this_build_still_emits_the_v1_envelope() -> None:
    """WP0 is a decision, not a migration.

    The contract is frozen here and the producers move in WP1. If this starts
    failing, the cutover happened and this test is what should be deleted with
    it — not the document's claim that WP0 changed no runtime behavior.
    """
    from techtree.constants import CLI_SCHEMA_VERSION

    assert CLI_SCHEMA_VERSION == "techtree.cli.v1"
    assert "`techtree.constants:CLI_SCHEMA_VERSION` is still" in contract_text()


def test_the_contract_forbids_the_rejected_alternatives() -> None:
    """The named rejections stay named, so a later reader inherits them."""
    body = section(contract_text(), "## What v2 does not add").lower()
    for rejected in ("adapter", "second command hierarchy", "daemon", "busy-poll"):
        assert rejected in body, f"the contract stopped rejecting {rejected}"
