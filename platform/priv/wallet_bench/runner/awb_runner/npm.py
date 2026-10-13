"""The npm side of a pinned agent: what the registry publishes for the pinned release, read before anything from the
package runs on the machine, and what npm then put there.

What this shows: the registry npm uses on this machine publishes, under that exact version, the fingerprint recorded
when the pin was chosen; npm itself refuses a download that does not match the registry's value; and the command the
tested account runs is the one inside npm's copy, not something an installer built another way. What it does not
show: nothing here hashes the files on disk again, and the package's own dependencies resolve on the day. That is why
everything npm resolved for the agent is recorded with the machine's baseline.
"""
import json
import shlex
from pathlib import Path

from .machine import Machine

# The installer's own npm: nvm's, once an agent's installer has set nvm up for the tested account, else the machine's.
NVM = 'export NVM_DIR="$HOME/.nvm"; [ ! -s "$NVM_DIR/nvm.sh" ] || . "$NVM_DIR/nvm.sh" > /dev/null'
NPM = f"{NVM}; npm"
# Where a global install can land: the tested account's home (its own prefix, or nvm's) and the system's folders.
ROOTS = (Path("/home/bench"), Path("/usr/local/lib"), Path("/usr/lib"))
RECORD = Path("/work/baseline/npm.json")


async def _npm(machine: Machine, arguments: str) -> str:
    result = await machine.exec(f"{NPM} {arguments}", timeout_sec=120)
    if result.return_code != 0:
        raise RuntimeError(f"npm {arguments} failed: {result.stdout}{result.stderr}")
    return result.stdout.strip()


async def published(machine: Machine, package: str, pin: dict) -> str:
    """Stops the build unless the registry publishes the pinned fingerprint for the pinned version. Returns the
    registry's address, as the tested account's npm reports it."""
    registry = await _npm(machine, "config get registry")
    integrity = await _npm(machine, f"view {shlex.quote(package + '@' + pin['version'])} dist.integrity")
    print(f"npm registry {registry}: {package}@{pin['version']} is published as {integrity}")
    if integrity != pin["integrity"]:
        raise RuntimeError(f"{package}@{pin['version']} is pinned as {pin['integrity']}; the registry differs")
    return registry


def _named(manifest: Path) -> str | None:
    try:
        package = json.loads(manifest.read_text())
        return f"{package['name']}@{package['version']}"
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _is_package(manifest: Path) -> bool:
    folder = manifest.parent.parent
    return folder.name == "node_modules" or (folder.name.startswith("@") and folder.parent.name == "node_modules")


def installed(package: str, version: str, roots: tuple[Path, ...] = ROOTS) -> dict:
    """Every copy of the package npm put on the machine and everything npm resolved beneath them. Stops the build when
    there is no copy, which is an install that took another road than npm, or a copy is not the pinned version."""
    copies = sorted(
        manifest.parent
        for root in roots
        for manifest in root.rglob(f"node_modules/{package}/package.json")
        if manifest.parts.count("node_modules") == 1
    )
    if not copies:
        raise RuntimeError(f"npm installed no copy of {package}")
    for copy in copies:
        if _named(copy / "package.json") != f"{package}@{version}":
            raise RuntimeError(f"{copy} is {_named(copy / 'package.json')}, not {package}@{version}")
    tree = {
        named
        for copy in copies
        for manifest in copy.rglob("package.json")
        if _is_package(manifest) and (named := _named(manifest))
    }
    return {"copies": [str(copy) for copy in copies], "tree": sorted(tree)}


def commands(copy: Path) -> list[str]:
    """The commands the package gives the account, from its own package.json."""
    package = json.loads((copy / "package.json").read_text())
    named = package["bin"]
    return [package["name"].rpartition("/")[2]] if isinstance(named, str) else sorted(named)


async def runs_from(machine: Machine, command: str, copies: list[str]) -> None:
    """Stops the build unless the command on the tested account's PATH is a file inside one of npm's copies."""
    result = await machine.exec(f'{NVM}; readlink -f "$(command -v {shlex.quote(command)})"', timeout_sec=30)
    found = result.stdout.strip()
    if not found or not any(Path(found).is_relative_to(Path(copy).resolve()) for copy in copies):
        raise RuntimeError(f"`{command}` on the tested account's PATH is {found or 'missing'}, not npm's copy")


async def check(machine: Machine, package: str, pin: dict, registry: str) -> None:
    """After the install: the same registry still publishes the pinned fingerprint, npm's copy is the pinned version,
    its commands run from that copy, and the record of it all is written for the baseline's manifest."""
    again = await published(machine, package, pin)
    if again != registry:
        raise RuntimeError(f"npm's registry was {registry} before the install and {again} after it")
    found = installed(package, pin["version"])
    for command in commands(Path(found["copies"][0])):
        await runs_from(machine, command, found["copies"])
    print(f"npm installed {package}@{pin['version']} at {', '.join(found['copies'])} with {len(found['tree'])} packages")
    RECORD.write_text(json.dumps({"registry": registry, "package": package, **pin, **found}))
