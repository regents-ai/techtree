"""The plugin's own doctor. Specification sections 7.4, 7.15, 9.18.

Techtree's Doctor answers "can this machine run a Climb?". This one answers a
narrower question first: "is this plugin build sound, and is the Techtree CLI
it needs present?". It is the gate the repository runs in CI and the check an
operator runs when the plugin behaves oddly.

Doctor is read-only. It parses files that shipped with the plugin, reads the
declared tool schemas, and looks two executables up on PATH. It starts no
process, opens no socket, and writes nothing, so running it can never repair
one problem by causing another.

Checks are blocking or not. A blocking failure means this plugin build is
broken and should not be trusted. A non-blocking warning means something is
missing that the operator can still supply, such as the CLI itself: the plugin
is required to load and answer questions on a host where Techtree was never
installed.
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from .bridge import resolve_techtree_binary
from .constants import (
    CLI_COMMAND,
    MANIFEST_FILENAME,
    PLUGIN_ID,
    PLUGIN_ROOT,
    PLUGIN_VERSION,
    RELEASE_CORE_FILENAME,
    SKILL_ENTRY_FILENAME,
    SKILLS_DIRNAME,
    SUPPORTED_HOOKS,
)
from .errors import PluginError
from .hooks import SESSION_HOOKS
from .models import INSTALLER_EXECUTABLE
from .release import load_embedded_release_core, release_core_digest
from .schemas import all_tool_schemas
from .tools import TOOL_HANDLERS

Status = Literal["pass", "warn", "fail"]

# Manifest ---------------------------------------------------------------------

MANIFEST_SCALAR_FIELDS: Final = ("name", "version", "description", "author", "kind")
MANIFEST_LIST_FIELDS: Final = ("provides_tools", "provides_hooks")
MANIFEST_FIELDS: Final = MANIFEST_SCALAR_FIELDS + MANIFEST_LIST_FIELDS

# Property names a model-visible schema must never accept. Specification
# section 7.4: no credential, no executable, no command line.
FORBIDDEN_SCHEMA_PROPERTIES: Final = frozenset(
    {
        "api_key",
        "apikey",
        "argv",
        "auth",
        "authorization",
        "binary",
        "command",
        "credential",
        "env",
        "executable",
        "index_url",
        "install_command",
        "password",
        "secret",
        "shell",
        "token",
    }
)


@dataclass(frozen=True)
class PluginManifest:
    """The plugin.yaml fields the plugin makes promises about."""

    name: str
    version: str
    description: str
    author: str
    kind: str
    provides_tools: tuple[str, ...]
    provides_hooks: tuple[str, ...]


def read_manifest(path: Path) -> PluginManifest:
    """Parse ``plugin.yaml``.

    The manifest grammar is deliberately tiny: comments, blank lines,
    ``key: value`` scalars, and ``- item`` string lists. Anything else is
    rejected rather than guessed at, because this file is what the host reads
    to decide which tools an agent may call.

    Raises:
        PluginError: when the file is missing or uses anything outside that
            grammar.
    """

    def invalid(detail: str, line_number: int | None = None) -> PluginError:
        where = f" (line {line_number})" if line_number else ""
        return PluginError(
            f"{path.name} is not usable{where}: {detail}",
            code="plugin_manifest_invalid",
            repair="Reinstall the plugin at its published commit.",
        )

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise invalid(str(error)) from error

    scalars: dict[str, str] = {}
    lists: dict[str, list[str]] = {}
    current_list: list[str] | None = None

    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        if line.startswith(" "):
            item = line.strip()
            if current_list is None or not item.startswith("- "):
                raise invalid("indented line is not a list item", number)
            current_list.append(_unquote(item[2:].strip()))
            continue

        key, separator, value = line.partition(":")
        if not separator or not key or key != key.strip():
            raise invalid("line is not a 'key: value' pair", number)
        if key in scalars or key in lists:
            raise invalid(f"duplicate key {key!r}", number)
        if key not in MANIFEST_FIELDS:
            raise invalid(f"unsupported key {key!r}", number)

        value = value.strip()
        if value:
            if key not in MANIFEST_SCALAR_FIELDS:
                raise invalid(f"key {key!r} must be a list", number)
            scalars[key] = _unquote(value)
            current_list = None
        else:
            if key not in MANIFEST_LIST_FIELDS:
                raise invalid(f"key {key!r} has no value", number)
            current_list = lists.setdefault(key, [])

    missing = sorted(set(MANIFEST_FIELDS) - set(scalars) - set(lists))
    if missing:
        raise invalid(f"missing keys {missing}")
    for name, items in lists.items():
        if not items:
            raise invalid(f"key {name!r} is empty")

    return PluginManifest(
        name=scalars["name"],
        version=scalars["version"],
        description=scalars["description"],
        author=scalars["author"],
        kind=scalars["kind"],
        provides_tools=tuple(lists["provides_tools"]),
        provides_hooks=tuple(lists["provides_hooks"]),
    )


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


# Report -----------------------------------------------------------------------


@dataclass(frozen=True)
class DoctorCheck:
    """One thing the doctor looked at, and what it found."""

    id: str
    label: str
    status: Status
    detail: str
    blocking: bool
    repair: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the check in the shape the JSON report carries it."""
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
            "blocking": self.blocking,
            "repair": self.repair,
        }


@dataclass(frozen=True)
class DoctorReport:
    """Everything the doctor looked at in one run."""

    plugin_id: str
    plugin_version: str
    release_core_digest: str | None
    checks: tuple[DoctorCheck, ...]

    @property
    def ok(self) -> bool:
        """Whether nothing blocking failed."""
        return not any(
            check.blocking and check.status == "fail" for check in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the whole report as JSON-ready data."""
        return {
            "ok": self.ok,
            "plugin_id": self.plugin_id,
            "plugin_version": self.plugin_version,
            "release_core_digest": self.release_core_digest,
            "checks": [check.to_dict() for check in self.checks],
        }


# Checks -----------------------------------------------------------------------


def run_plugin_doctor(
    root: Path = PLUGIN_ROOT,
    *,
    path_lookup: Callable[[str], str | None] = shutil.which,
) -> DoctorReport:
    """Inspect this plugin build and the host readiness it depends on.

    Args:
        root: The plugin directory to inspect. Tests point this at a copy.
        path_lookup: How executables are found. Tests substitute a lookup so
            they can describe a host with and without the Techtree CLI.
    """
    checks: list[DoctorCheck] = []
    manifest = _check_manifest(root, checks)
    _check_tool_schemas(manifest, checks)
    digest = _check_release_core(root, checks)
    _check_runtime_imports(root, checks)
    _check_bundled_skills(root, checks)
    _check_coverage(
        checks,
        check_id="tool_handlers",
        label="Tool handlers",
        noun="tools",
        declared=set(manifest.provides_tools) if manifest else set(all_tool_schemas()),
        implemented=set(TOOL_HANDLERS),
    )
    _check_coverage(
        checks,
        check_id="hook_callbacks",
        label="Session hooks",
        noun="hooks",
        declared=set(manifest.provides_hooks) if manifest else set(SUPPORTED_HOOKS),
        implemented=set(SESSION_HOOKS),
    )
    _check_executable(
        checks,
        located=resolve_techtree_binary(path_lookup=path_lookup),
        name=CLI_COMMAND,
        check_id="techtree_cli",
        label="Techtree CLI",
        absent_detail=(
            "the Techtree CLI is not on PATH, so no Climb can run yet; the "
            "plugin itself is fine"
        ),
        repair="Run techtree_bootstrap_check for the pinned install plan.",
    )
    _check_executable(
        checks,
        located=path_lookup(INSTALLER_EXECUTABLE),
        name=INSTALLER_EXECUTABLE,
        check_id="uv",
        label="uv",
        absent_detail=(
            "uv is not on PATH, so the plugin cannot offer to install the Techtree CLI"
        ),
        repair="Install uv with your usual package manager, then check again.",
    )
    return DoctorReport(
        plugin_id=PLUGIN_ID,
        plugin_version=PLUGIN_VERSION,
        release_core_digest=digest,
        checks=tuple(checks),
    )


def _check_manifest(root: Path, checks: list[DoctorCheck]) -> PluginManifest | None:
    try:
        manifest = read_manifest(root / MANIFEST_FILENAME)
    except PluginError as error:
        checks.append(
            DoctorCheck(
                id="plugin_manifest",
                label="Plugin manifest",
                status="fail",
                detail=str(error),
                blocking=True,
                repair="Reinstall the plugin at its published commit.",
            )
        )
        return None

    problems: list[str] = []
    if manifest.name != PLUGIN_ID:
        problems.append(f"name is {manifest.name!r}, not {PLUGIN_ID!r}")
    if manifest.version != PLUGIN_VERSION:
        problems.append(f"version is {manifest.version!r}, not {PLUGIN_VERSION!r}")
    if not manifest.description:
        problems.append("description is empty")
    if manifest.kind != "standalone":
        problems.append(f"kind is {manifest.kind!r}, not 'standalone'")
    if tuple(manifest.provides_hooks) != SUPPORTED_HOOKS:
        problems.append(
            f"declared hooks {list(manifest.provides_hooks)} are not "
            f"{list(SUPPORTED_HOOKS)}"
        )
    duplicates = sorted(
        {
            name
            for name in manifest.provides_tools
            if manifest.provides_tools.count(name) > 1
        }
    )
    if duplicates:
        problems.append(f"tools declared more than once: {duplicates}")

    checks.append(
        DoctorCheck(
            id="plugin_manifest",
            label="Plugin manifest",
            status="fail" if problems else "pass",
            detail=(
                "; ".join(problems)
                if problems
                else (
                    f"{manifest.name} {manifest.version} declares "
                    f"{len(manifest.provides_tools)} tools and "
                    f"{len(manifest.provides_hooks)} hooks, and no credentials"
                )
            ),
            blocking=True,
            repair="Reinstall the plugin at its published commit."
            if problems
            else None,
        )
    )
    return manifest


def _check_tool_schemas(
    manifest: PluginManifest | None, checks: list[DoctorCheck]
) -> None:
    schemas = all_tool_schemas()
    problems: list[str] = []

    if manifest is not None:
        declared = set(manifest.provides_tools)
        defined = set(schemas)
        undeclared = sorted(defined - declared)
        undefined = sorted(declared - defined)
        if undeclared:
            problems.append(f"schemas exist for undeclared tools {undeclared}")
        if undefined:
            problems.append(f"declared tools have no schema {undefined}")

    for name, schema in sorted(schemas.items()):
        problems.extend(f"{name}: {problem}" for problem in _schema_problems(schema))

    checks.append(
        DoctorCheck(
            id="tool_schemas",
            label="Tool schemas",
            status="fail" if problems else "pass",
            detail=(
                "; ".join(problems)
                if problems
                else (
                    f"{len(schemas)} schemas match the manifest, accept no "
                    "credential, executable, or command, and bound every "
                    "identifier they take"
                )
            ),
            blocking=True,
            repair="Fix schemas.py; a released plugin must not ship this."
            if problems
            else None,
        )
    )


def _schema_problems(schema: Mapping[str, Any]) -> Iterator[str]:
    if schema.get("type") != "object":
        yield "is not an object schema"
    if not schema.get("description"):
        yield "has no description"
    if schema.get("additionalProperties") is not False:
        yield "allows additional properties"

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        yield "declares no properties object"
        return

    for required in schema.get("required", []):
        if required not in properties:
            yield f"requires undeclared property {required!r}"

    for name, definition in properties.items():
        if name.lower() in FORBIDDEN_SCHEMA_PROPERTIES:
            yield f"accepts forbidden property {name!r}"
        if not isinstance(definition, dict):
            yield f"property {name!r} is not a schema"
            continue
        if not definition.get("description"):
            yield f"property {name!r} has no description"
        if definition.get("type") == "string" and not (
            definition.get("pattern")
            or definition.get("enum")
            or definition.get("maxLength")
        ):
            yield f"property {name!r} is an unbounded string"


def _check_release_core(root: Path, checks: list[DoctorCheck]) -> str | None:
    try:
        core = load_embedded_release_core(root)
    except (PluginError, OSError) as error:
        checks.append(
            DoctorCheck(
                id="release_core",
                label="Release core",
                status="fail",
                detail=str(error),
                blocking=True,
                repair=f"Regenerate {RELEASE_CORE_FILENAME} with the release tooling.",
            )
        )
        return None

    digest = release_core_digest(core)
    # The release document says for itself whether a person has chosen every
    # coordinate yet. A build carrying an unfinished release is usable, and
    # must never be mistaken for a published one.
    development = core.placeholder_release
    checks.append(
        DoctorCheck(
            id="release_core",
            label="Release core",
            status="warn" if development else "pass",
            detail=(
                f"release {core.release_id} pins CLI {core.cli_version} "
                f"and carries digest {digest}"
                + (
                    "; it is not a published release yet: "
                    + ", ".join(core.placeholder_fields)
                    + " have not been chosen"
                    if development
                    else ""
                )
            ),
            blocking=True,
            repair=(
                f"Regenerate {RELEASE_CORE_FILENAME} from a real release before "
                "publishing this plugin."
                if development
                else None
            ),
        )
    )
    return digest


def _check_runtime_imports(root: Path, checks: list[DoctorCheck]) -> None:
    problems: list[str] = []
    module_count = 0

    for path in sorted(iter_runtime_modules(root)):
        module_count += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as error:
            problems.append(f"{path.name} could not be read: {error}")
            continue
        for module in _imported_top_level_modules(tree):
            if module in sys.stdlib_module_names:
                continue
            relative = path.relative_to(root)
            if module == "techtree":
                problems.append(
                    f"{relative} imports Techtree Python; the CLI JSON "
                    "envelope is the only boundary"
                )
            else:
                problems.append(f"{relative} imports third-party module {module!r}")

    checks.append(
        DoctorCheck(
            id="runtime_imports",
            label="Runtime imports",
            status="fail" if problems else "pass",
            detail=(
                "; ".join(problems)
                if problems
                else (
                    f"{module_count} runtime modules import only the standard "
                    "library and each other"
                )
            ),
            blocking=True,
            repair="Remove the dependency; plugin runtime code is stdlib only."
            if problems
            else None,
        )
    )


def iter_runtime_modules(root: Path) -> Iterator[Path]:
    """Yield the Python files Hermes loads as part of this plugin.

    Repository tooling and tests are excluded: they are allowed dependencies
    the host never imports.
    """
    excluded = {"tests", "scripts", "skills"}
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if relative.parts[0] in excluded or any(
            part.startswith(".") for part in relative.parts
        ):
            continue
        yield path


def _imported_top_level_modules(tree: ast.AST) -> Iterator[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0]


def _check_bundled_skills(root: Path, checks: list[DoctorCheck]) -> None:
    skills_root = root / SKILLS_DIRNAME
    found = (
        sorted(
            entry.name
            for entry in skills_root.iterdir()
            if entry.is_dir() and (entry / SKILL_ENTRY_FILENAME).is_file()
        )
        if skills_root.is_dir()
        else []
    )

    checks.append(
        DoctorCheck(
            id="bundled_skills",
            label="Bundled operator Skills",
            status="pass" if found else "warn",
            detail=(
                "registers as " + ", ".join(f"{PLUGIN_ID}:{name}" for name in found)
                if found
                else "this build bundles no operator Skills"
            ),
            blocking=False,
        )
    )


def _check_coverage(
    checks: list[DoctorCheck],
    *,
    check_id: str,
    label: str,
    noun: str,
    declared: set[str],
    implemented: set[str],
) -> None:
    """Compare what the manifest promises against what this build implements.

    An implementation the manifest never declared is a defect and blocks. A
    declaration whose implementation has not landed yet is reported plainly,
    so an incomplete build is visible without pretending to be broken.
    """
    undeclared = sorted(implemented - declared)
    missing = sorted(declared - implemented)

    if undeclared:
        status: Status = "fail"
        detail = f"undeclared {noun} are implemented: {undeclared}"
    elif missing:
        status = "warn"
        detail = (
            f"{len(implemented)} of {len(declared)} declared {noun} are "
            f"implemented in this build; still missing {missing}"
        )
    else:
        status = "pass"
        detail = f"all {len(declared)} declared {noun} are implemented"

    checks.append(
        DoctorCheck(
            id=check_id,
            label=label,
            status=status,
            detail=detail,
            blocking=bool(undeclared),
            repair=f"Declare the {noun} in the manifest, or remove them."
            if undeclared
            else None,
        )
    )


def _check_executable(
    checks: list[DoctorCheck],
    *,
    located: str | None,
    name: str,
    check_id: str,
    label: str,
    absent_detail: str,
    repair: str,
) -> None:
    checks.append(
        DoctorCheck(
            id=check_id,
            label=label,
            status="pass" if located else "warn",
            detail=f"{name} is at {located}" if located else absent_detail,
            blocking=False,
            repair=None if located else repair,
        )
    )


# Command line -----------------------------------------------------------------

_STATUS_MARK: Final = {"pass": "ok  ", "warn": "warn", "fail": "FAIL"}


def format_report(report: DoctorReport) -> str:
    """Render the report for a person reading a terminal."""
    lines = [
        f"{report.plugin_id} {report.plugin_version} "
        f"({report.release_core_digest or 'no release digest'})",
        "",
    ]
    for check in report.checks:
        lines.append(f"  {_STATUS_MARK[check.status]}  {check.label}: {check.detail}")
        if check.repair:
            lines.append(f"          → {check.repair}")
    lines.append("")
    lines.append(
        "Plugin doctor passed."
        if report.ok
        else "Plugin doctor found a blocking problem."
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the doctor from the command line. Returns a process exit code."""
    parser = argparse.ArgumentParser(
        prog="plugin-doctor",
        description="Check that this Techtree plugin build is sound.",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit the report as one JSON object"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=PLUGIN_ROOT,
        help="the plugin directory to inspect",
    )
    arguments = parser.parse_args(argv)

    report = run_plugin_doctor(arguments.root)
    if arguments.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_report(report))
    return 0 if report.ok else 1
