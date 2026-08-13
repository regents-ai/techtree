"""Fixed plugin constants. Specification section 7.4.

Every value here is frozen at build time. Nothing in this module is mutable
and nothing is derived from model input, so a tool argument can never move a
bound, a timeout, or the command the plugin is allowed to run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

# Identity ------------------------------------------------------------------

PLUGIN_ID: Final = "techtree"
PLUGIN_VERSION: Final = "0.1.0"
TOOLSET_NAME: Final = "techtree"

# Repository layout ---------------------------------------------------------

PLUGIN_ROOT: Final = Path(__file__).resolve().parent
MANIFEST_FILENAME: Final = "plugin.yaml"
RELEASE_CORE_FILENAME: Final = "release-core.json"
SKILLS_DIRNAME: Final = "skills"
SKILL_ENTRY_FILENAME: Final = "SKILL.md"

# Techtree CLI boundary -----------------------------------------------------

# The only executable name the plugin ever resolves. It is looked up on PATH;
# no tool argument, manifest field, or model output can name a different one.
CLI_COMMAND: Final = "techtree"

# Machine-mode flags appended to every bridged CLI invocation, exactly once.
CLI_JSON_FLAGS: Final = ("--json", "--no-color", "--no-input")

# The distribution an installation plan may name, and the only one. It is a
# release coordinate, not a setting: no tool argument or model output can
# change what gets installed.
CLI_DISTRIBUTION_NAME: Final = "techtree"

DEFAULT_CLI_TIMEOUT_SECONDS: Final = 120.0

# Bound for CLI work that reaches the public release origin, such as catalog
# refresh or starter-Skill materialization. The plugin itself opens no socket.
DEFAULT_NETWORK_TIMEOUT_SECONDS: Final = 60.0

# Bounds --------------------------------------------------------------------

MAX_CLI_STDOUT_BYTES: Final = 4_000_000
MAX_CLI_STDERR_BYTES: Final = 200_000
MAX_TOOL_RESULT_BYTES: Final = 200_000
MAX_BOOTSTRAP_MANIFEST_BYTES: Final = 256_000
MAX_STARTER_SKILL_BYTES: Final = 256_000

# Lifetimes -----------------------------------------------------------------

INSTALL_PLAN_TTL_SECONDS: Final = 900
DEMO_SESSION_TTL_SECONDS: Final = 604_800

# Release contract ----------------------------------------------------------

SUPPORTED_RELEASE_CORE_SCHEMA: Final = "techtree.release-core.v1"

# The one CLI envelope contract this plugin release speaks.
SUPPORTED_CLI_SCHEMA: Final = "techtree.cli.v1"

# Host lifecycle hooks this plugin takes part in. Both do local bookkeeping
# only: no network, no installation, no Docker, no model call.
SUPPORTED_HOOKS: Final = ("on_session_start", "on_session_end")
