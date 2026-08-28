"""Fixed plugin constants. Specification section 7.4.

Every value here is frozen at build time. Nothing in this module is mutable
and nothing is derived from model input, so a tool argument can never move a
bound, a timeout, or the command the plugin is allowed to run.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

# Identity ------------------------------------------------------------------

PLUGIN_ID: Final = "techtree"
PLUGIN_VERSION: Final = "0.1.0"
TOOLSET_NAME: Final = "techtree"

# Repository layout ---------------------------------------------------------

PLUGIN_ROOT: Final = Path(__file__).resolve().parent.parent
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

# The whole environment a bridged Techtree call is given. Named here, copied by
# name, and nothing else goes across: a host agent's session carries whatever
# the person who started it had exported — cloud credentials, provider keys for
# unrelated services, tokens for things that have no business hearing about an
# evaluation — and a call that inherits all of it hands every one of them to a
# process that needs none of them.
#
# It is the same list Techtree's own launcher gives its detached worker, plus
# what the CLI needs that a worker does not:
#
# * PATH, HOME, TMPDIR — find the CLI and the tools it runs, find the Prime CLI
#   configuration and the package caches that hang off a home directory, and
#   put scratch files where this host expects them;
# * XDG_DATA_HOME — where the CLI resolves its own home from, on the platforms
#   that use it. Dropping it would point the plugin at a different Techtree
#   home than the one the person uses in their own terminal;
# * TECHTREE_HOME, TECHTREE_LOG_LEVEL — Techtree's own variables, and the two
#   the worker is given;
# * LANG, LC_ALL, LC_CTYPE, TERM — how text is encoded, and what the terminal
#   can render, for the commands whose output goes to a person's screen.
#
# A model-provider credential is deliberately absent, and costs nothing: a run
# authenticates from the Prime CLI configuration under HOME, and Techtree's own
# worker does not inherit one either.
CLI_ENVIRONMENT_ALLOWLIST: Final = (
    "PATH",
    "HOME",
    "TMPDIR",
    "XDG_DATA_HOME",
    "TECHTREE_HOME",
    "TECHTREE_LOG_LEVEL",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
)

# The distribution an installation plan may name, and the only one. It is a
# release coordinate, not a setting: no tool argument or model output can
# change what gets installed.
CLI_DISTRIBUTION_NAME: Final = "techtree"

# The Python an installation plan installs Techtree on, and the only one. Also
# a release coordinate: this release states the Python it needs, and the
# published install command names it (Techtree decisions document 0034).
#
# Left to choose, uv installs onto whatever Python this machine already treats
# as its default, which on a current Mac is newer than Techtree supports. The
# install then succeeds and Techtree's own Doctor reports a wrong interpreter
# as the first thing a new user sees. Naming it here is the whole fix.
CLI_PYTHON_SERIES: Final = "3.12"

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

# Where the plugin writes -----------------------------------------------------
#
# One location, named here, documented in the README's removal section, and
# used for exactly one thing: holding a proposed Skill for the seconds between
# the plugin writing it down and Techtree taking its own snapshot.
#
# It is deliberately not the shared OS temporary directory. A proposed Skill
# is participant content, a cleanup can fail, and a file left behind in
# /tmp is a file nobody can be told about in advance. This one has an address
# a person can be given, check, and delete.

#: The directory the plugin owns under the user's state home.
PLUGIN_STATE_DIRNAME: Final = "techtree-hermes"

#: The only subdirectory of it the plugin ever writes to.
PROPOSAL_STAGING_DIRNAME: Final = "proposals"


def plugin_state_home() -> Path:
    """Return the one directory this plugin may write to.

    Resolved at call time, never at import: registration must touch no
    filesystem, and a constant computed at import would make that promise
    depend on nobody ever adding a `mkdir` beside it.
    """
    configured = os.environ.get("XDG_STATE_HOME")
    base = Path(configured) if configured else Path.home() / ".local" / "state"
    return base / PLUGIN_STATE_DIRNAME


def proposal_staging_home() -> Path:
    """Return where a proposed Skill is written while Techtree takes it over."""
    return plugin_state_home() / PROPOSAL_STAGING_DIRNAME


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
