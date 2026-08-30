# Techtree developer tasks. Spec section 9.6.
#
# Every target runs through uv so the pinned project environment is the only
# environment that matters.

UV ?= uv
RUN := $(UV) run

TOOL_ENGINE_BUNDLE := tools/build_engine_bundle.py
TOOL_FIXTURE_CATALOG := tools/build_fixture_catalog.py
TOOL_GOLDENS := tools/build_goldens.py
TOOL_RELEASE_CORE := tools/build_release_core.py
TOOL_SCHEMAS := tools/export_schemas.py

# Everything the generators own. `generated-check` compares these paths
# between the working tree and a freshly regenerated temporary tree.
#
# `release` also holds two files nobody generates — the founder-owned inputs
# and this directory's README — and comparing them costs nothing: they are
# copied into the temporary tree unchanged, so they can only ever differ if the
# copy itself went wrong.
GENERATED_PATHS := \
	schemas \
	tests/golden \
	release \
	src/techtree/resources/catalog \
	src/techtree/resources/engines \
	src/techtree/resources/release

.DEFAULT_GOAL := check

.PHONY: install lint format format-check typecheck test test-unit test-contract \
	test-integration test-plugin typecheck-plugin plugin-doctor plugin-schemas \
	plugin-founder-skills plugin-release-core plugin-release-core-cli \
	real-model-run real-model-run-single schemas engine-bundle fixture-catalog goldens \
	release-core regenerate generated-check verifiers-preflight check check-plugin clean

install:
	$(UV) sync

lint:
	$(RUN) ruff check .

format:
	$(RUN) ruff format .
	$(RUN) ruff check --fix .

format-check:
	$(RUN) ruff format --check .

typecheck:
	$(RUN) mypy

test:
	$(RUN) pytest

test-unit:
	$(RUN) pytest tests/unit

test-contract:
	$(RUN) pytest tests/contract

test-integration:
	$(RUN) pytest -m integration tests/integration

# The Hermes plugin battery ---------------------------------------------------
#
# The plugin's unit, contract and integration tests live here, in tests/plugin,
# and its repository tooling in tools/plugin. Both read the plugin itself out
# of the checkout beside this one; every target below says so if it is missing.
# The plugin checkout carries the runtime, the Skills and the release bytes and
# nothing else, so an install-time scanner reads only what the plugin does.
#
# The contract tests that talk to a real CLI use the one in this project, which
# is the CLI the plugin is pinned to. Override it to check against another.
TECHTREE_CLI_ARGV ?= $(UV) run --project . techtree

test-plugin:
	TECHTREE_CLI_ARGV="$(TECHTREE_CLI_ARGV)" $(RUN) pytest tests/plugin

# mypy identifies a package by its directory name, and the plugin checkout's
# name is not a Python identifier, so this pass gives it an importable one.
typecheck-plugin:
	$(RUN) python tools/plugin/typecheck.py

# The plugin's own doctor: manifest, schemas, release bytes, runtime imports,
# and host readiness. Exits non-zero on a blocking failure.
plugin-doctor:
	$(RUN) python tools/plugin/plugin_doctor.py

plugin-schemas:
	$(RUN) python tools/plugin/export_tool_schemas.py

# Everything that reads the sibling plugin checkout, in one target. Kept out of
# `check`, which must pass in a clone that has no sibling checkout at all. The
# typecheck belongs here rather than nowhere: it is the only pass that reads the
# plugin the way a host does, through an installed techtree, and it went red and
# unnoticed for as long as it was a target nobody ran (techtree-python-qgr).
check-plugin: test-plugin typecheck-plugin plugin-doctor

# Checks the founder Skills in the plugin checkout against decision 0007's
# behavioural contracts.
plugin-founder-skills:
	$(RUN) python tools/plugin/check_founder_skills.py

# The plugin and the installed Techtree must carry the identical ReleaseCore.
plugin-release-core:
	$(RUN) python tools/plugin/verify_release_core.py

# Asks the installed Techtree CLI which release it belongs to, and compares.
plugin-release-core-cli:
	$(RUN) python tools/plugin/verify_release_core.py --against-installed-cli

# Spends real money. Both variants of a local Campaign are executed against a
# real provider in real Docker containers, so this is never part of `check`,
# never part of CI, and always started by a person who meant to.
real-model-run:
	$(RUN) pytest -m real_model -s \
		tests/integration/test_real_concurrent_comparison.py

# The WP6b single-variant run, kept runnable on its own. Also spends money, and
# proves a subset of what the concurrent comparison above proves.
real-model-run-single:
	$(RUN) pytest -m real_model -s tests/integration/test_real_variant_run.py

schemas:
	$(RUN) python $(TOOL_SCHEMAS)

engine-bundle:
	@if [ -f "$(TOOL_ENGINE_BUNDLE)" ]; then \
		$(RUN) python $(TOOL_ENGINE_BUNDLE); \
	else \
		echo "engine-bundle: pass-through, $(TOOL_ENGINE_BUNDLE) is not part of this build yet"; \
	fi

# Installs the engine into a throwaway home and runs the real model-free
# validation, so it needs uv and a warm or reachable package cache.
fixture-catalog:
	$(RUN) python $(TOOL_FIXTURE_CATALOG)

goldens:
	$(RUN) python $(TOOL_GOLDENS)

# Binds the founder-owned release inputs to the engine and catalog the other
# generators just produced, so it runs after them and never before.
release-core:
	$(RUN) python $(TOOL_RELEASE_CORE)

# Binding order, spec section 25, then the release document over the result.
regenerate: engine-bundle fixture-catalog goldens schemas release-core

# Regenerates into a throwaway copy of the repository and fails on drift.
# It never writes to the working tree.
generated-check:
	@set -e; \
	if [ ! -f "$(TOOL_SCHEMAS)" ]; then \
		echo "generated-check: pass-through, the generators in tools/ are not part of this build yet"; \
		exit 0; \
	fi; \
	work="$$(mktemp -d)"; \
	trap 'rm -rf "$$work"' EXIT HUP INT TERM; \
	tar -cf - \
		--exclude .git \
		--exclude .beads \
		--exclude .venv \
		--exclude __pycache__ \
		--exclude '.*_cache' \
		. | tar -xf - -C "$$work"; \
	$(MAKE) -C "$$work" regenerate; \
	for path in $(GENERATED_PATHS); do \
		if [ ! -e "$$path" ] && [ ! -e "$$work/$$path" ]; then \
			echo "generated-check: skipping $$path, no generator owns it yet"; \
			continue; \
		fi; \
		diff -ru -x __pycache__ "$$path" "$$work/$$path"; \
	done; \
	echo "generated-check: generated artifacts match the working tree"

verifiers-preflight:
	$(RUN) pytest -m preflight tests/preflight

check: format-check lint typecheck test generated-check

clean:
	rm -rf .mypy_cache .pytest_cache .ruff_cache dist build htmlcov .coverage
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
