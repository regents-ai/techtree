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
PLUGIN_VERSION: Final = "0.6.0"
TOOLSET_NAME: Final = "techtree"

# Repository layout ---------------------------------------------------------

PLUGIN_ROOT: Final = Path(__file__).resolve().parent.parent
MANIFEST_FILENAME: Final = "plugin.yaml"
RELEASE_CORE_FILENAME: Final = "release-core.json"
SKILLS_DIRNAME: Final = "skills"
SKILL_ENTRY_FILENAME: Final = "SKILL.md"

# regents boundary ----------------------------------------------------------

# The only executable name the plugin ever resolves. It is looked up on PATH;
# no tool argument, manifest field, or model output can name a different one.
# Techtree is the `techtree` namespace of the Regents command line, so every
# bridged call starts with ``CLI_NAMESPACE``.
CLI_COMMAND: Final = "regents"
CLI_NAMESPACE: Final = ("techtree",)

# The machine-mode flag appended to every bridged call, exactly once. regents
# prints no colour and asks no question under it: a step that needs a person's
# agreement answers ``approval_required`` instead of waiting for input.
CLI_JSON_FLAGS: Final = ("--json",)

# The whole environment a bridged call is given. Named here, copied by name,
# and nothing else goes across: a host agent's session carries whatever the
# person who started it had exported — cloud credentials, provider keys for
# unrelated services, tokens for things that have no business hearing about an
# evaluation — and a call that inherits all of it hands every one of them to a
# process that needs none of them.
#
# It is the same list regents gives its detached run worker, plus what a
# terminal needs:
#
# * PATH, HOME, TMPDIR — find regents and the tools it runs, find the Techtree
#   home (``~/.regents/techtree``) and the Prime CLI configuration under the
#   home directory, and put scratch files where this host expects them;
# * LANG, LC_ALL, LC_CTYPE, TERM — how text is encoded, and what the terminal
#   can render, for the commands whose output goes to a person's screen.
#
# A model-provider credential is deliberately absent, and costs nothing: a run
# authenticates from the Prime CLI configuration under HOME, and the regents
# worker does not inherit one either.
CLI_ENVIRONMENT_ALLOWLIST: Final = (
    "PATH",
    "HOME",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
)

# The distribution an installation plan may name, and the only one. It is a
# release coordinate, not a setting: no tool argument or model output can
# change what gets installed.
CLI_DISTRIBUTION_NAME: Final = "regents-cli"

# The Python an installation plan installs regents on, and the only one. Also
# a release coordinate (Techtree decisions document 0034).
#
# Left to choose, uv installs onto whatever Python this machine already treats
# as its default, which on a current Mac is newer than Techtree supports
# (``regents techtree doctor`` requires >=3.12,<3.14). The install then
# succeeds and the doctor reports a wrong interpreter as the first thing a new
# user sees. Naming it here is the whole fix.
CLI_PYTHON_SERIES: Final = "3.12"

DEFAULT_CLI_TIMEOUT_SECONDS: Final = 120.0

# Bound for regents work that reaches the public release origin, such as catalog
# refresh or starter-Skill materialization. The plugin itself opens no socket.
DEFAULT_NETWORK_TIMEOUT_SECONDS: Final = 60.0

# Bounds --------------------------------------------------------------------

MAX_CLI_STDOUT_BYTES: Final = 4_000_000
MAX_CLI_STDERR_BYTES: Final = 200_000
MAX_TOOL_RESULT_BYTES: Final = 200_000
MAX_BOOTSTRAP_MANIFEST_BYTES: Final = 256_000

# Lifetimes -----------------------------------------------------------------

INSTALL_PLAN_TTL_SECONDS: Final = 900
DEMO_SESSION_TTL_SECONDS: Final = 604_800

# Release contract ----------------------------------------------------------

SUPPORTED_RELEASE_CORE_SCHEMA: Final = "techtree.release-core.v3"

# Host lifecycle hooks this plugin takes part in. Both do local bookkeeping
# only: no network, no installation, no Docker, no model call.
SUPPORTED_HOOKS: Final = ("on_session_start", "on_session_end")
