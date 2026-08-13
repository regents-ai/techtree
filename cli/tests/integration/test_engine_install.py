"""Installing the pinned engine for real. Spec sections 20 and 27.4.

Everything here runs against the actual bundle this build ships: the real
descriptor, the real lock, the real Verifiers commit. The install fixture calls
``uv sync``, which downloads several hundred megabytes on a cold cache and
reaches PyPI and GitHub, so the whole module is marked ``integration`` and
excluded from the default test run::

    uv run pytest tests/integration/test_engine_install.py -m integration

The install happens once per session and every test that needs a working engine
shares it. Nothing here writes outside its own temporary Techtree home.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from techtree.engines import installer as installer_module
from techtree.engines.bundle import (
    ENGINE_TOOLS,
    INSTALLATION_FILENAME,
    copy_engine_bundle,
    default_engine_descriptor,
    default_engine_digest,
    embedded_engine_root,
    engine_bundle_digest,
    enumerate_bundle_files,
    package_source_digest,
    read_engine_descriptor,
)
from techtree.engines.installer import (
    INSTALLING_MARKER_PREFIX,
    EngineInstaller,
    find_uv,
)
from techtree.engines.registry import EngineRegistry
from techtree.engines.runner import EngineRunner
from techtree.errors import EngineError, VerificationError
from techtree.models.engine import (
    EngineDescriptor,
    EngineInstallation,
    EnginePackage,
    EngineStatus,
)
from techtree.paths import TechtreePaths, ensure_path_layout, paths_from_root
from techtree.settings import Settings

pytestmark = pytest.mark.integration

REFERENCE_PACKAGE = "procedure-transfer-v1"
REFERENCE_MODULE = "procedure_transfer_v1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def descriptor() -> EngineDescriptor:
    """The descriptor of the engine this build ships."""
    return default_engine_descriptor()


@pytest.fixture(scope="session")
def installed_paths(tmp_path_factory: pytest.TempPathFactory) -> TechtreePaths:
    """A Techtree home used by every test that needs a real engine."""
    paths = paths_from_root(tmp_path_factory.mktemp("techtree-home"))
    ensure_path_layout(paths)
    return paths


@pytest.fixture(scope="session")
def installed_engine(installed_paths: TechtreePaths) -> EngineStatus:
    """Install the shipped engine once, for real."""
    registry = EngineRegistry(installed_paths, Settings())
    installer = EngineInstaller(installed_paths, registry, find_uv())
    return installer.install()


@pytest.fixture
def registry(installed_paths: TechtreePaths) -> EngineRegistry:
    """A registry over the session's installed engine."""
    return EngineRegistry(installed_paths, Settings())


# ---------------------------------------------------------------------------
# The bundle digest
# ---------------------------------------------------------------------------


def test_the_bundle_digest_is_stable_across_repeated_computations() -> None:
    root = embedded_engine_root()

    assert engine_bundle_digest(root) == engine_bundle_digest(root)
    assert default_engine_digest() == engine_bundle_digest(root)


def test_a_copied_bundle_hashes_to_the_same_digest(tmp_path: Path) -> None:
    destination = tmp_path / "bundle"
    copy_engine_bundle(embedded_engine_root(), destination)

    assert engine_bundle_digest(destination) == default_engine_digest()


def test_changing_one_bundle_file_changes_the_digest(tmp_path: Path) -> None:
    destination = tmp_path / "bundle"
    copy_engine_bundle(embedded_engine_root(), destination)
    before = engine_bundle_digest(destination)

    (destination / "tools" / "inspect_taskset.py").write_text(
        "# tampered\n", encoding="utf-8"
    )

    assert engine_bundle_digest(destination) != before


def test_the_digest_ignores_caches_and_the_installation_marker(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "bundle"
    copy_engine_bundle(embedded_engine_root(), destination)
    before = engine_bundle_digest(destination)

    cache = destination / "packages" / REFERENCE_PACKAGE / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "taskset.cpython-312.pyc").write_bytes(b"\x00")
    (destination / INSTALLATION_FILENAME).write_text("{}", encoding="utf-8")
    (destination / ".venv").mkdir()
    (destination / ".venv" / "pyvenv.cfg").write_text("home = /x\n", encoding="utf-8")

    assert engine_bundle_digest(destination) == before


def test_the_bundle_carries_no_catalog_object() -> None:
    """Spec section 20.1: the engine is what breaks the digest cycle."""
    paths = {
        entry.relative_path for entry in enumerate_bundle_files(embedded_engine_root())
    }

    assert not {path for path in paths if "catalog" in path}
    assert {"engine.json", "pyproject.toml", "uv.lock"} <= paths
    assert {f"tools/{tool}" for tool in ENGINE_TOOLS} <= paths


# ---------------------------------------------------------------------------
# The descriptor
# ---------------------------------------------------------------------------


def test_the_descriptor_source_digest_matches_the_shipped_package_tree(
    descriptor: EngineDescriptor,
) -> None:
    """Decisions 0003 A8: the first leg of the required triple equality.

    ``Campaign.taskset.ref.package.digest`` and
    ``TasksetLock.resolved_package_digest`` are the other two, and both are
    generated from this value later in the chain. If this leg is wrong, the
    other two are wrong together and the equality proves nothing.
    """
    recomputed = package_source_digest(
        embedded_engine_root() / "packages" / REFERENCE_PACKAGE
    )
    package = _reference_package(descriptor)

    assert package.source_digest == recomputed


def test_the_descriptor_pins_the_verifiers_commit_and_the_host_vocabulary(
    descriptor: EngineDescriptor,
) -> None:
    assert descriptor.verifiers_revision == ("7e1c47d24d055aae587ee8259f77a3e8e193513a")
    assert descriptor.python_version == "3.12"
    assert sorted(descriptor.supported_hosts) == [
        "darwin/amd64",
        "darwin/arm64",
        "linux/amd64",
        "linux/arm64",
    ]


# ---------------------------------------------------------------------------
# A real install
# ---------------------------------------------------------------------------


def test_a_fresh_home_installs_the_engine_into_its_own_environment(
    installed_engine: EngineStatus,
    installed_paths: TechtreePaths,
    registry: EngineRegistry,
) -> None:
    assert installed_engine.digest == default_engine_digest()
    assert installed_engine.installed
    assert installed_engine.verified
    assert Path(installed_engine.path) == installed_paths.engine_dir(
        installed_engine.digest
    )
    assert registry.installed() == [installed_engine.digest]

    python = registry.python(installed_engine.digest)
    assert python.is_file()
    assert python.is_relative_to(Path(installed_engine.path))
    assert _prefix(python) == Path(installed_engine.path) / ".venv"


def test_the_global_python_environment_is_irrelevant(
    installed_engine: EngineStatus, registry: EngineRegistry
) -> None:
    """Techtree's own environment never holds Verifiers; the engine's does."""
    assert _has_verifiers(registry.python(installed_engine.digest))
    assert not _has_verifiers(Path(sys.executable))


def test_the_engine_environment_reports_what_the_descriptor_promised(
    installed_engine: EngineStatus,
    registry: EngineRegistry,
    descriptor: EngineDescriptor,
) -> None:
    reported = _query(registry, installed_engine.digest)

    assert str(reported["python_version"]).startswith(f"{descriptor.python_version}.")
    assert reported["verifiers_version"] == descriptor.verifiers_version
    assert reported["verifiers_commit"] == descriptor.verifiers_revision
    assert reported["taskset_import"] is True


def test_the_reference_taskset_imports_from_inside_the_engine(
    installed_engine: EngineStatus, registry: EngineRegistry
) -> None:
    """Decisions 0003 A8: the digested source is what the engine runs."""
    reported = _query(registry, installed_engine.digest)
    module_file = Path(str(reported["taskset_module_file"])).resolve()
    engine_root = registry.path(installed_engine.digest).resolve()

    assert module_file.is_relative_to(engine_root)
    assert module_file.is_relative_to(engine_root / "packages" / REFERENCE_PACKAGE)


def test_the_validate_and_eval_executables_exist_inside_the_engine(
    installed_engine: EngineStatus, registry: EngineRegistry
) -> None:
    """``docs/verifiers-pin.md`` C3: generic names, addressed absolutely."""
    for name in ("validate", "eval"):
        executable = registry.executable(installed_engine.digest, name)
        assert executable.is_file()
        assert executable.is_relative_to(registry.path(installed_engine.digest))


def test_both_engine_tools_resolve_inside_the_installed_engine(
    installed_engine: EngineStatus, registry: EngineRegistry
) -> None:
    """Decisions 0003 A3: the helpers ship inside the digested bundle."""
    engine_root = registry.path(installed_engine.digest)

    for tool in ENGINE_TOOLS:
        path = registry.tool_path(installed_engine.digest, tool)
        assert path.is_file()
        assert path.parent == engine_root / "tools"

    runner = EngineRunner(registry, installed_engine.digest)
    result = runner.run_python_script(
        registry.tool_path(installed_engine.digest, "inspect_taskset.py"),
        ["--help"],
        timeout=120.0,
    )
    assert result.exit_code == 0
    assert "--taskset-id" in result.stdout


def test_the_installed_bundle_still_hashes_to_its_own_digest(
    installed_engine: EngineStatus, registry: EngineRegistry
) -> None:
    installed_root = registry.path(installed_engine.digest)

    assert engine_bundle_digest(installed_root) == installed_engine.digest
    assert (
        read_engine_descriptor(installed_root).verifiers_revision
        == default_engine_descriptor().verifiers_revision
    )


def test_reinstalling_is_idempotent(
    installed_engine: EngineStatus, installed_paths: TechtreePaths
) -> None:
    marker = installed_paths.engine_dir(installed_engine.digest) / INSTALLATION_FILENAME
    before = marker.read_bytes()

    registry = EngineRegistry(installed_paths, Settings())
    again = EngineInstaller(installed_paths, registry, find_uv()).install()

    assert again.digest == installed_engine.digest
    assert again.installed and again.verified
    assert marker.read_bytes() == before


def test_verify_rejects_an_engine_whose_files_changed(
    installed_engine: EngineStatus, installed_paths: TechtreePaths
) -> None:
    registry = EngineRegistry(installed_paths, Settings())
    installer = EngineInstaller(installed_paths, registry, find_uv())
    tool = registry.tool_path(installed_engine.digest, "inspect_taskset.py")
    original = tool.read_bytes()

    try:
        tool.write_bytes(original + b"\n# tampered\n")
        with pytest.raises(VerificationError, match="have changed"):
            installer.verify(installed_engine.digest)
    finally:
        tool.write_bytes(original)

    assert installer.verify(installed_engine.digest).verified


def test_verify_confirms_the_files_and_the_live_environment(
    installed_engine: EngineStatus, installed_paths: TechtreePaths
) -> None:
    registry = EngineRegistry(installed_paths, Settings())
    verified = EngineInstaller(installed_paths, registry, find_uv()).verify(
        installed_engine.digest
    )

    assert verified.verified
    assert verified.digest == installed_engine.digest


def test_an_engine_is_recorded_as_active_only_after_it_verifies(
    installed_engine: EngineStatus, installed_paths: TechtreePaths
) -> None:
    absent = "sha256:" + "0" * 64
    registry = EngineRegistry(installed_paths, Settings())

    with pytest.raises(EngineError, match="not installed"):
        registry.set_active(absent)

    settings = registry.set_active(installed_engine.digest)
    activated = EngineRegistry(installed_paths, settings)

    assert settings.active_engine_digest == installed_engine.digest
    assert activated.status(installed_engine.digest).active
    assert default_engine_digest() in activated.known()


def test_uninstalling_removes_an_idle_engine_and_refuses_the_active_one(
    tmp_path: Path,
) -> None:
    """Exercised against a recorded installation rather than a built one.

    Removal is about the registry's bookkeeping — what is active, and what is
    on disk — so it does not need half a gigabyte of wheels to be honest.
    """
    paths = paths_from_root(tmp_path / "home")
    ensure_path_layout(paths)
    digest = "sha256:" + "2" * 64
    registry = EngineRegistry(paths, Settings())
    registry.path(digest).mkdir(parents=True)
    registry.record(
        EngineInstallation(
            digest=digest,
            installed_at=datetime.now(UTC),
            python_executable=str(registry.python(digest)),
            descriptor_digest="sha256:" + "3" * 64,
            verified=True,
        )
    )
    assert registry.installed() == [digest]

    active = EngineRegistry(paths, registry.set_active(digest))
    with pytest.raises(EngineError, match="active"):
        EngineInstaller(paths, active, find_uv()).uninstall(digest)

    idle = EngineRegistry(paths, Settings())
    EngineInstaller(paths, idle, find_uv()).uninstall(digest)

    assert idle.installed() == []
    assert not registry.path(digest).exists()


# ---------------------------------------------------------------------------
# Typed failures
# ---------------------------------------------------------------------------


def test_installing_a_digest_this_build_does_not_ship_is_refused(
    tmp_path: Path,
) -> None:
    paths = paths_from_root(tmp_path / "home")
    ensure_path_layout(paths)
    installer = EngineInstaller(paths, EngineRegistry(paths, Settings()), find_uv())

    with pytest.raises(EngineError) as failure:
        installer.install("sha256:" + "1" * 64)

    assert failure.value.code == "engine_digest_unknown"


def test_a_missing_uv_is_a_named_retryable_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(EngineError) as failure:
        find_uv()

    assert failure.value.code == "uv_not_found"
    assert failure.value.retryable


def test_an_unsupported_host_is_refused_before_anything_is_downloaded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = paths_from_root(tmp_path / "home")
    ensure_path_layout(paths)
    installer = EngineInstaller(paths, EngineRegistry(paths, Settings()), find_uv())
    monkeypatch.setattr(platform, "machine", lambda: "sparc64")

    with pytest.raises(EngineError) as failure:
        installer.install()

    assert failure.value.code == "engine_host_unsupported"
    assert not list(paths.engines_dir.glob("sha256-*"))


def test_a_damaged_lock_is_named_and_leaves_no_engine_behind(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A bundle whose lock cannot build it fails cleanly, with nothing left."""
    damaged = tmp_path / "damaged-bundle"
    copy_engine_bundle(embedded_engine_root(), damaged)
    (damaged / "uv.lock").write_text(
        'version = 1\nrevision = 3\nrequires-python = "==3.12.*"\n', encoding="utf-8"
    )
    monkeypatch.setattr(
        installer_module, "embedded_engine_root", lambda *args, **kwargs: damaged
    )

    paths = paths_from_root(tmp_path / "home")
    ensure_path_layout(paths)
    registry = EngineRegistry(paths, Settings())
    installer = EngineInstaller(paths, registry, find_uv())

    with pytest.raises(EngineError) as failure:
        installer.install()

    assert failure.value.code == "engine_lock_mismatch"
    assert registry.installed() == []
    assert not registry.path(engine_bundle_digest(damaged)).exists()
    # Decisions 0004, ratified as 0007 R7: a failed install takes its own
    # marker with it, so the next setup has nothing stale to find.
    assert not list(paths.engines_dir.glob(f"{INSTALLING_MARKER_PREFIX}*"))
    assert installer.interrupted_installs() == []


# ---------------------------------------------------------------------------
# The marker protocol, against a real install. Decisions 0004 / 0007 R7.
# ---------------------------------------------------------------------------


def test_a_finished_install_leaves_its_marker_behind_nowhere(
    installed_paths: TechtreePaths, installed_engine: EngineStatus
) -> None:
    """Written first, removed last — and last is after ``installed.json``."""
    engine = installed_paths.engine_dir(installed_engine.digest)

    assert (engine / INSTALLATION_FILENAME).is_file()
    assert not list(installed_paths.engines_dir.glob(f"{INSTALLING_MARKER_PREFIX}*"))
    assert (
        EngineInstaller(
            installed_paths,
            EngineRegistry(installed_paths, Settings()),
            find_uv(),
        ).interrupted_installs()
        == []
    )


def test_an_install_discards_what_a_killed_one_left_before_building(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A retry starts from nothing, never on top of a half-built environment.

    The install this test starts then fails on a damaged lock, which is the
    point: the discarding happens before any building, so it is observable
    without paying for a successful install.
    """
    damaged = tmp_path / "damaged-bundle"
    copy_engine_bundle(embedded_engine_root(), damaged)
    (damaged / "uv.lock").write_text(
        'version = 1\nrevision = 3\nrequires-python = "==3.12.*"\n', encoding="utf-8"
    )
    monkeypatch.setattr(
        installer_module, "embedded_engine_root", lambda *args, **kwargs: damaged
    )

    paths = paths_from_root(tmp_path / "home")
    ensure_path_layout(paths)
    installer = EngineInstaller(paths, EngineRegistry(paths, Settings()), find_uv())

    # What a machine that lost power halfway through an install looks like.
    stale_digest = "sha256:" + "c" * 64
    stale_engine = paths.engine_dir(stale_digest)
    (stale_engine / ".venv" / "bin").mkdir(parents=True)
    stale_marker = (
        paths.engines_dir
        / f"{INSTALLING_MARKER_PREFIX}{paths.engine_dir(stale_digest).name}"
    )
    stale_marker.write_text("{}\n", encoding="utf-8")

    assert [install.digest for install in installer.interrupted_installs()] == [
        stale_digest
    ]

    with pytest.raises(EngineError):
        installer.install()

    assert not stale_engine.exists()
    assert not stale_marker.exists()
    assert installer.interrupted_installs() == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reference_package(descriptor: EngineDescriptor) -> EnginePackage:
    for package in descriptor.packages:
        if package.name == REFERENCE_PACKAGE:
            return package
    raise AssertionError(f"the engine ships no {REFERENCE_PACKAGE} package")


def _prefix(python: Path) -> Path:
    """Return the environment prefix one interpreter runs in."""
    completed = subprocess.run(
        [str(python), "-c", "import sys; print(sys.prefix)"],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return Path(completed.stdout.strip())


def _has_verifiers(python: Path) -> bool:
    """Whether one interpreter can import the pinned validator at all."""
    completed = subprocess.run(
        [
            str(python),
            "-c",
            "import importlib.util as u; "
            "raise SystemExit(0 if u.find_spec('verifiers') else 1)",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    return completed.returncode == 0


def _query(registry: EngineRegistry, digest: str) -> dict[str, Any]:
    """Ask the installed engine what it is, without going through Techtree."""
    source = (
        "import importlib, json, platform, sys\n"
        "from importlib.metadata import distribution\n"
        "verifiers = distribution('verifiers')\n"
        "recorded = json.loads(verifiers.read_text('direct_url.json') or '{}')\n"
        f"module = importlib.import_module({REFERENCE_MODULE!r})\n"
        "json.dump({\n"
        "    'python_version': platform.python_version(),\n"
        "    'verifiers_version': verifiers.version,\n"
        "    'verifiers_commit': recorded['vcs_info']['commit_id'],\n"
        "    'taskset_import': module is not None,\n"
        "    'taskset_module_file': module.__file__,\n"
        "}, sys.stdout)\n"
    )
    completed = subprocess.run(
        [str(registry.python(digest)), "-c", source],
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    document = json.loads(completed.stdout)
    assert isinstance(document, dict)
    return document
