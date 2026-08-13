# Techtree Hermes plugin developer tasks.
#
# Every target runs through uv so the pinned tooling environment is the only
# environment that matters. `make check` is the gate: format, lint, types,
# doctor, tests.

UV ?= uv
RUN := $(UV) run

.DEFAULT_GOAL := check

.PHONY: install format format-check lint typecheck doctor schemas founder-skills \
	release-core \
	release-core-cli \
	test test-unit test-contract test-cli-contract check

install:
	$(UV) sync

format:
	$(RUN) ruff format .
	$(RUN) ruff check --fix .

format-check:
	$(RUN) ruff format --check .

lint:
	$(RUN) ruff check .

typecheck:
	$(RUN) python scripts/typecheck.py

# The plugin's own doctor: manifest, schemas, release bytes, runtime imports,
# and host readiness. Exits non-zero on a blocking failure.
doctor:
	$(RUN) python scripts/plugin_doctor.py

schemas:
	$(RUN) python scripts/export_tool_schemas.py

# Checks the founder Skills against decision 0007's behavioural contracts.
# Neither exists yet; run it over tests/fixtures/skills to see the shape.
founder-skills:
	$(RUN) python scripts/check_founder_skills.py

release-core:
	$(RUN) python scripts/verify_release_core.py

# Asks the installed Techtree CLI which release it belongs to, and compares.
release-core-cli:
	$(RUN) python scripts/verify_release_core.py --against-installed-cli

test:
	$(RUN) pytest

test-unit:
	$(RUN) pytest tests/unit

test-contract:
	$(RUN) pytest tests/contract

# Runs the read-only contract tests against a real Techtree CLI. Set
# TECHTREE_CLI_ARGV when the CLI is not on PATH, for example:
#   make test-cli-contract TECHTREE_CLI_ARGV="uv run --project ../techtree-python techtree"
test-cli-contract:
	TECHTREE_CLI_ARGV="$(TECHTREE_CLI_ARGV)" $(RUN) pytest -m real_cli tests/contract

check: format-check lint typecheck doctor test
