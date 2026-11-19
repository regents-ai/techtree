# Techtree Hermes plugin developer tasks.
#
# Every target runs through uv so the pinned tooling environment is the only
# environment that matters. `make check` is the plugin's gate: format, lint,
# types and the plugin doctor.

UV ?= uv
RUN := $(UV) run

.DEFAULT_GOAL := check

.PHONY: install format format-check lint typecheck typecheck-scripts doctor \
	schemas release-core release-core-cli check

install:
	$(UV) sync

format:
	$(RUN) ruff format .
	$(RUN) ruff check --fix .

format-check:
	$(RUN) ruff format --check .

lint:
	$(RUN) ruff check .

# mypy identifies a package by its directory name, and `plugin` is not the name
# the package is imported under. The package is checked under an importable
# name through a symbolic link in a scratch directory, which is undone when the
# check ends. The scripts beside it are checked by typecheck-scripts.
typecheck:
	@work="$$(mktemp -d)"; \
	ln -s "$(CURDIR)" "$$work/techtree_hermes"; \
	MYPYPATH="$$work" $(RUN) mypy --namespace-packages \
		--exclude '/techtree_hermes/scripts/' -p techtree_hermes; \
	status=$$?; \
	unlink "$$work/techtree_hermes"; \
	rmdir "$$work"; \
	exit $$status

# The scripts, checked from their own directory.
typecheck-scripts:
	$(RUN) python scripts/typecheck.py

# The plugin's own doctor: manifest, schemas, release bytes, runtime imports,
# and host readiness. Exits non-zero on a blocking failure.
doctor:
	$(RUN) python scripts/plugin_doctor.py

schemas:
	$(RUN) python scripts/export_tool_schemas.py

# Checks the embedded ReleaseCore and prints its digest.
release-core:
	$(RUN) python scripts/verify_release_core.py

# Also asks the `regents` on PATH which release it belongs to, and compares.
release-core-cli:
	$(RUN) python scripts/verify_release_core.py --against-installed-cli

check: format-check lint typecheck typecheck-scripts doctor
