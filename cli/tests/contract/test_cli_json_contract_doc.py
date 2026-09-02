"""The v1 CLI contract document, bound to the application it describes.

``cli/docs/cli-json-contract.md`` is what a host agent programs from. It lists
the stable command names and the namespaces that are reserved and not
registered. A list written by hand drifts: five commands were once registered
and never listed, and ``uplift`` stayed reserved on paper after its group was
wired (techtree-31k.15). These tests hold the document to
:func:`techtree.cli.app.create_app` so that cannot happen quietly again.
"""

from __future__ import annotations

import re
from pathlib import Path

import typer

from techtree.cli.app import RESERVED_NAMESPACES, create_app

CONTRACT_PATH = Path(__file__).parents[2] / "docs" / "cli-json-contract.md"

#: The sentence that names the reserved namespaces, and the backticked names
#: inside it.
RESERVED_SENTENCE = re.compile(
    r"The namespaces (?P<names>.*?)\s+are reserved and are not registered\.",
    re.DOTALL,
)
BACKTICKED_NAME = re.compile(r"`([a-z]+)`")


def contract_text() -> str:
    assert CONTRACT_PATH.is_file(), f"{CONTRACT_PATH} is missing"
    return CONTRACT_PATH.read_text(encoding="utf-8")


def documented_command_names() -> list[str]:
    """Return the command list from the ``Stable command names`` section."""
    text = contract_text()
    heading = "## Stable command names"
    assert heading in text, f"the contract has no section {heading!r}"
    body = text.split(heading, 1)[1]
    match = re.search(r"```text\n(?P<listing>.*?)\n```", body, re.DOTALL)
    assert match, "the stable command names are not in a text listing"
    return match.group("listing").splitlines()


def registered_command_paths(app: typer.Typer) -> set[str]:
    """Return every command path the application registers, program name excluded."""
    found: set[str] = set()

    def walk(group: typer.Typer, path: tuple[str, ...]) -> None:
        for command in group.registered_commands:
            assert command.callback is not None
            name = command.name or command.callback.__name__
            found.add(" ".join((*path, name)))
        for subgroup in group.registered_groups:
            assert subgroup.typer_instance is not None
            assert subgroup.name is not None
            walk(subgroup.typer_instance, (*path, subgroup.name))

    walk(app, ())
    return found


def test_the_document_lists_every_registered_command_and_nothing_else() -> None:
    documented = documented_command_names()

    assert len(documented) == len(set(documented)), "a command is listed twice"
    assert set(documented) == registered_command_paths(create_app())


def test_the_document_names_the_reserved_namespaces_the_code_reserves() -> None:
    match = RESERVED_SENTENCE.search(contract_text())

    assert match, "the contract no longer says which namespaces are reserved"
    assert tuple(BACKTICKED_NAME.findall(match.group("names"))) == RESERVED_NAMESPACES


def test_no_reserved_namespace_is_registered() -> None:
    top_level = {path.split(" ")[0] for path in registered_command_paths(create_app())}

    assert not top_level & set(RESERVED_NAMESPACES)
