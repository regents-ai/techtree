"""The v0.2 machine contract, bound to the code it describes. WP0.6.

``docs/v0.2/MACHINE_CONTRACT.md`` freezes ``techtree.cli.v2``: stable
operation identifiers that *describe existing CLI handlers* rather than create a
second command hierarchy, and a five-state public projection over the detailed
append-only run phases.

A document that names a handler is a document that can be wrong about it. These
tests make it impossible to be wrong for long: every handler the inventory
cites must exist and be registered as a command, every registered command must
be described by some operation, and the projection table must cover every
``RunPhase`` exactly once.

Since WP1.6 they also bind the envelope itself. The document's eleven envelope
fields, its nine next-action fields, and its five retry classes are checked
against the models that produce them, so a field renamed in one place and not
the other fails the build rather than reaching a host agent.
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest
import typer

from techtree.cli.app import create_app
from techtree.constants import CLI_SCHEMA_VERSION
from techtree.models.cli import (
    CliEnvelope,
    DataEgress,
    NextAction,
    Operation,
    RetryClass,
    SideEffect,
)
from techtree.models.run import PublicRunState, RunPhase
from techtree.runs.machine import public_state

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
        "profile.get",
        "profile.sync",
        "profile.update",
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

#: ``module:symbol``, the way the document cites code. The symbol may be a
#: function or a class: the contract cites the review payloads a refusal
#: returns as well as the handlers that return them, and a citation nobody
#: checks is the kind that survives a rename.
HANDLER_REFERENCE = re.compile(
    r"`(techtree(?:\.[a-z_][a-z0-9_]*)+):([A-Za-z_][A-Za-z0-9_]*)`"
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
    """Only the deliberately published operation identifiers."""
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


def test_the_cli_projects_every_phase_the_way_the_document_says() -> None:
    """The documented table and the one the CLI uses are one table.

    The test above holds the document to ``RunPhase``. This holds the code to
    the document, so a projection that was changed in one place and not the
    other fails rather than leaving a host agent's five states disagreeing with
    the contract it programmed against.
    """
    rows = table_rows(section(contract_text(), "## The public state projection"))
    documented = {row[0].strip("`"): row[1].strip("`") for row in rows[1:]}
    implemented = {phase.value: public_state(phase).value for phase in RunPhase}

    assert implemented == documented


def test_the_five_public_states_are_the_ones_the_plan_names() -> None:
    """The enum a payload carries holds exactly the contract's vocabulary."""
    assert {state.value for state in PublicRunState} == PUBLIC_STATES


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


def documented_envelope_fields() -> list[str]:
    rows = first_table(section(contract_text(), "## The envelope"))
    assert rows[0][0] == "Field", "the envelope table lost its header"
    return [row[0].strip("`") for row in rows[1:]]


def documented_next_action_fields() -> list[str]:
    # The first table is the entry itself; the ones after it are its value sets.
    rows = first_table(section(contract_text(), "## Typed next actions"))
    assert rows[0][0] == "Field", "the next-action table lost its header"
    return [row[0].strip("`") for row in rows[1:]]


def test_the_envelope_documents_exactly_the_eleven_planned_fields() -> None:
    assert documented_envelope_fields() == [
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


def test_the_envelope_the_cli_emits_has_exactly_those_fields() -> None:
    """The document and the model are one envelope.

    Holding the document to the plan is only half of it. This holds the code to
    the document, so a field added, renamed, or dropped in the model without
    the contract moving with it fails here rather than reaching a host agent
    that programmed against the document.
    """
    assert list(CliEnvelope.model_fields) == documented_envelope_fields()


def test_the_next_action_the_cli_emits_has_exactly_those_fields() -> None:
    assert list(NextAction.model_fields) == documented_next_action_fields()


def test_a_next_action_documents_exactly_the_nine_planned_fields() -> None:
    assert documented_next_action_fields() == [
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
    assert {retry.value for retry in RetryClass} == RETRY_CLASSES


def test_the_operations_the_cli_can_answer_under_are_the_planned_ones() -> None:
    """The enum the envelope carries holds exactly the inventory."""
    assert {operation.value for operation in Operation} == PLANNED_OPERATIONS


def test_the_side_effect_and_egress_classes_are_the_documented_ones() -> None:
    """Both value sets are derived in the contract, so both are checked to it.

    They are the two fields that say what invoking an action would do to a
    machine and what would leave it, which makes an undocumented member a
    promise nobody wrote down.
    """
    body = section(contract_text(), "## Typed next actions")
    documented = {row[0].strip("`") for row in table_rows(body)}
    assert {effect.value for effect in SideEffect} <= documented
    assert {egress.value for egress in DataEgress} <= documented
    for section_name, members in (
        ("### Side-effect classes", {effect.value for effect in SideEffect}),
        ("### Data-egress classes", {egress.value for egress in DataEgress}),
    ):
        rows = table_rows(_subsection(contract_text(), section_name))
        assert {row[0].strip("`") for row in rows[1:]} == members


def _subsection(text: str, heading: str) -> str:
    """Return one ``###``-level subsection's body, heading excluded."""
    lines = text.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.strip() == heading), None
    )
    assert start is not None, f"the contract has no section {heading!r}"
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## ") or line.startswith("### "):
            break
        body.append(line)
    return "\n".join(body)


# ---------------------------------------------------------------------------
# The boundaries the decision ledger set
# ---------------------------------------------------------------------------


def test_this_build_emits_the_v2_envelope() -> None:
    """WP1.6 was the cutover, and the document says so where it happened."""
    assert CLI_SCHEMA_VERSION == "techtree.cli.v2"
    assert (
        "`techtree.constants:CLI_SCHEMA_VERSION` is\n`techtree.cli.v2` in this build"
        in contract_text()
    )


#: Files that may still name the v1 envelope version, and why. This test names
#: it in order to forbid it. ``test_models.py`` hands the plugin's parser a v1
#: envelope to prove it is rejected. Everything else that builds or reads an
#: envelope speaks one version, and the frozen trees — the v1 contract
#: document and ``schemas/v1alpha1`` — are history rather than code.
V1_VERSION_IS_ALLOWED: frozenset[str] = frozenset(
    {
        "test_models.py",
        "test_v02_machine_contract.py",
    }
)


def test_no_v1_envelope_or_next_action_shape_survives() -> None:
    """The cutover is hard: the v1 names are gone from producer and consumer.

    ``messages`` was v1's free-text channel, ``retryable`` its error-level
    boolean, and ``requires_user_confirmation``, ``hermes_tool`` and
    ``hermes_args`` its next-action fields. A search is a blunt instrument, and
    it is the right one over the code that builds an envelope and the code that
    reads one: none of these words may be a field name in either.

    ``techtree.cli.v1`` is scanned the same way, and for a sharper reason. A
    second definition of the envelope version is not a field name a reader
    would notice — it is a string that looks right everywhere it appears — and
    one of them survived the cutover in ``version.py``, where Doctor reported
    it from inside a v2 envelope.
    """
    forbidden = (
        "requires_user_confirmation",
        "hermes_tool",
        "hermes_args",
        "retryable",
    )
    for path in sorted((CLI_ROOT / "src").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for name in forbidden:
            if name == "retryable" and path.name in {"cli.py", "errors.py"}:
                # Both explain, in prose, why the boolean is gone.
                continue
            assert name not in text, f"{path} still names the v1 field {name!r}"


def test_nothing_that_speaks_the_envelope_still_names_v1() -> None:
    """One envelope version, defined once, named nowhere it could be read as live."""
    roots = (CLI_ROOT / "src", CLI_ROOT / "tests", MONOREPO_ROOT / "plugin")
    for root in roots:
        for suffix in ("*.py", "*.json"):
            for path in sorted(root.rglob(suffix)):
                if path.name in V1_VERSION_IS_ALLOWED:
                    continue
                text = path.read_text(encoding="utf-8")
                assert "techtree.cli.v1" not in text, (
                    f"{path} still names techtree.cli.v1"
                )


#: The four side-effecting handlers, and how each one names the thing it acts
#: on. All four refuse in machine mode without ``--yes``; what each refusal
#: offers is the subject of the tests below.
APPROVED_CALLS: tuple[tuple[str, list[str], list[str]], ...] = (
    ("climb start", ["climb", "start"], ["draft_00000000000000000000000000000000"]),
    ("uplift start", ["uplift", "start"], ["draft_00000000000000000000000000000000"]),
    ("publish", ["publish"], ["run_00000000000000000000000000000000"]),
    ("withdraw", ["withdraw"], ["sha256:" + "0" * 64]),
)

#: What each approved call would do, in the contract's three classes. A start
#: runs locally and sends prompts to the model provider; a publication or a
#: withdrawal changes the public log and reaches the publication service. The
#: retry class is where they differ most: a start is a person's decision every
#: time, and a request that may already have reached the log is read back
#: before anything is decided.
APPROVED_CALL_CLASSES: dict[str, tuple[SideEffect, DataEgress, RetryClass]] = {
    "climb start": (
        SideEffect.LOCAL_EXECUTION,
        DataEgress.MODEL_PROVIDER,
        RetryClass.HUMAN_DECISION_REQUIRED,
    ),
    "uplift start": (
        SideEffect.LOCAL_EXECUTION,
        DataEgress.MODEL_PROVIDER,
        RetryClass.HUMAN_DECISION_REQUIRED,
    ),
    "publish": (
        SideEffect.PUBLIC_PUBLICATION,
        DataEgress.PUBLICATION_SERVICE,
        RetryClass.RECONCILE_FIRST,
    ),
    "withdraw": (
        SideEffect.PUBLIC_PUBLICATION,
        DataEgress.PUBLICATION_SERVICE,
        RetryClass.RECONCILE_FIRST,
    ),
}


def offered_approved_calls() -> dict[str, NextAction]:
    """Return the step each of the four refusals offers, built as it is built."""
    from techtree.cli.commands.climb import start_when_approved
    from techtree.cli.commands.publish import _publish_when_agreed
    from techtree.cli.commands.withdraw import _withdraw_when_agreed

    draft = APPROVED_CALLS[0][2][0]
    digest = "sha256:" + "a" * 64
    return {
        "climb start": start_when_approved(
            "climb",
            draft_id=draft,
            draft_digest=digest,
            estimated_cost=None,
            reason="It starts the run described above.",
        ),
        "uplift start": start_when_approved(
            "uplift",
            draft_id=draft,
            draft_digest=digest,
            estimated_cost=None,
            reason="It starts the run described above.",
        ),
        "publish": _publish_when_agreed(APPROVED_CALLS[2][2][0]),
        "withdraw": _withdraw_when_agreed(APPROVED_CALLS[3][2][0]),
    }


def test_every_refusal_offers_the_approved_call_not_the_refused_one() -> None:
    """``action.prepare`` refuses; what it offers is the call that would work.

    Handing back the invocation that had just been refused is not a next step
    — a caller that took it would be refused again, forever. Each of the four
    offers the same call carrying the flag that says a person has answered,
    which is ``action.execute``, and what stops a machine from taking it on
    its own is ``approval_required``.
    """
    offered = offered_approved_calls()

    for name, command, arguments in APPROVED_CALLS:
        action = offered[name]
        prepared = action.prepared_arguments
        assert action.operation is Operation.ACTION_EXECUTE, name
        assert action.approval_required is True, name
        assert prepared["command"] == command, name
        assert prepared["arguments"] == arguments, name
        options = prepared["options"]
        assert isinstance(options, dict)
        assert options.get("--yes") is True, f"{name} offers the refused call"


def test_every_approved_call_records_where_the_review_was_answered() -> None:
    """The refusal carried the review, so the approved call says who read it.

    ``--reviewed-on host-agent`` is how the run, the publication receipt, or
    the withdrawal records that the person answered on the host agent's own
    surface rather than at this terminal. An approved call without it would
    record an answer given nowhere.
    """
    offered = offered_approved_calls()

    for name, _command, _arguments in APPROVED_CALLS:
        options = offered[name].prepared_arguments["options"]
        assert isinstance(options, dict)
        assert options == {"--yes": True, "--reviewed-on": "host-agent"}, name


def test_every_approved_call_says_what_invoking_it_would_do() -> None:
    """The three classes are the truth about the step, not about the refusal.

    A host agent branches on them before it shows a person anything, so an
    approved call that understated its effect — a publication marked as local
    state, a start marked as reaching nothing — would have the person agree to
    less than what happens.
    """
    offered = offered_approved_calls()

    for name, (side_effect, data_egress, retry_class) in APPROVED_CALL_CLASSES.items():
        action = offered[name]
        assert action.side_effect is side_effect, name
        assert action.data_egress is data_egress, name
        assert action.retry_class is retry_class, name


def test_a_start_offered_after_a_review_is_bound_to_the_draft_reviewed() -> None:
    """An answer is about one draft, and the call it allows says which.

    ``expected_state_digest`` is what stops a start from running on a draft
    that moved after the review a person read. The money statement travels
    with the same call: a review that showed a declared maximum offers a start
    carrying it, and one that showed none offers a start that carries none
    rather than a zero.
    """
    from techtree.cli.commands.climb import _declared_maximum_of, start_when_approved

    offered = offered_approved_calls()

    for name in ("climb start", "uplift start"):
        assert offered[name].expected_state_digest == "sha256:" + "a" * 64, name
        assert offered[name].estimated_cost is None, name

    priced = start_when_approved(
        "climb",
        draft_id=APPROVED_CALLS[0][2][0],
        draft_digest="sha256:" + "a" * 64,
        estimated_cost=_declared_maximum_of(12.5),
        reason="It starts the run described above.",
    )
    assert priced.estimated_cost is not None
    assert priced.estimated_cost.maximum_authorized_cost == "12.5"
    assert priced.estimated_cost.estimate_source == "campaign_declared_maximum"
    assert priced.estimated_cost.execution_plan_digest is None


def literal_tuple(module: Path, name: str) -> tuple[str, ...]:
    """Return one module-level tuple of string literals, without importing it.

    The Hermes plugin is a separate package with its own import machinery, and
    reading its source is enough here: what is being checked is the vocabulary
    it hard-codes, which is a literal in the file either way.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign | ast.Assign):
            continue
        targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
        if not any(
            isinstance(target, ast.Name) and target.id == name for target in targets
        ):
            continue
        assert isinstance(node.value, ast.Tuple), f"{name} is not a tuple literal"
        return tuple(ast.literal_eval(element) for element in node.value.elts)
    raise AssertionError(f"{module} defines no {name}")


def test_the_hermes_consumer_reads_exactly_the_contract_envelope() -> None:
    """The producer and the only consumer describe one envelope.

    The plugin parses an envelope by name and rejects a field it has never
    heard of, so its field lists *are* its half of the contract. They are
    checked against the document rather than against the CLI's model, because
    the document is what a second consumer would be written from.
    """
    models = MONOREPO_ROOT / "plugin" / "services" / "models.py"
    assert (
        list(literal_tuple(models, "_CLI_ENVELOPE_FIELDS"))
        == documented_envelope_fields()
    )
    assert (
        list(literal_tuple(models, "_CLI_NEXT_ACTION_FIELDS"))
        == documented_next_action_fields()
    )
    assert set(literal_tuple(models, "_CLI_OPERATIONS")) == PLANNED_OPERATIONS
    assert set(literal_tuple(models, "_CLI_RETRY_CLASSES")) == RETRY_CLASSES


def test_the_hermes_consumer_speaks_the_same_envelope_version() -> None:
    """One version, moved in one change. There is no negotiation."""
    constants = MONOREPO_ROOT / "plugin" / "cli" / "constants.py"
    text = constants.read_text(encoding="utf-8")
    assert f'SUPPORTED_CLI_SCHEMA: Final = "{CLI_SCHEMA_VERSION}"' in text
