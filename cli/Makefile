# Techtree developer tasks. Spec section 9.6.
#
# Every target runs through uv so the pinned project environment is the only
# environment that matters.

UV ?= uv
RUN := $(UV) run

TOOL_ENGINE_BUNDLE := tools/build_engine_bundle.py
TOOL_FIXTURE_CATALOG := tools/build_fixture_catalog.py
TOOL_GOLDENS := tools/build_goldens.py
TOOL_SCHEMAS := tools/export_schemas.py

# Everything the generators own. `generated-check` compares these paths
# between the working tree and a freshly regenerated temporary tree.
GENERATED_PATHS := \
	schemas \
	tests/golden \
	src/techtree/resources/catalog \
	src/techtree/resources/engines

.DEFAULT_GOAL := check

.PHONY: install lint format format-check typecheck test test-unit test-contract \
	test-integration schemas engine-bundle fixture-catalog goldens regenerate \
	generated-check verifiers-preflight check clean

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

schemas:
	$(RUN) python $(TOOL_SCHEMAS)

engine-bundle:
	@if [ -f "$(TOOL_ENGINE_BUNDLE)" ]; then \
		$(RUN) python $(TOOL_ENGINE_BUNDLE); \
	else \
		echo "engine-bundle: pass-through, $(TOOL_ENGINE_BUNDLE) is not part of this build yet"; \
	fi

fixture-catalog:
	@if [ -f "$(TOOL_FIXTURE_CATALOG)" ]; then \
		$(RUN) python $(TOOL_FIXTURE_CATALOG); \
	else \
		echo "fixture-catalog: pass-through, $(TOOL_FIXTURE_CATALOG) is not part of this build yet"; \
	fi

goldens:
	$(RUN) python $(TOOL_GOLDENS)

# Binding order, spec section 25.
regenerate: engine-bundle fixture-catalog goldens schemas

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
