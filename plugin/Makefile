# Techtree Hermes plugin developer tasks.
#
# Every target runs through uv so the pinned tooling environment is the only
# environment that matters. `make check` is this repository's gate: format,
# lint, types.
#
# The test battery is not here. This checkout is what an install-time scanner
# reads, and a suite that proves the guards work has to carry the attacks they
# catch — fake private keys, destructive command strings — which is exactly
# what a scanner is right to refuse. So the plugin's unit, contract and
# integration tests, and the tooling that runs them, live in the Techtree
# repository beside this one, and run there with `make test-plugin`.

UV ?= uv
RUN := $(UV) run

.DEFAULT_GOAL := check

.PHONY: install format format-check lint typecheck check

install:
	$(UV) sync

format:
	$(RUN) ruff format .
	$(RUN) ruff check --fix .

format-check:
	$(RUN) ruff format --check .

lint:
	$(RUN) ruff check .

# mypy identifies a package by its directory name, and `techtree-hermes` is not
# a Python identifier. The package is checked under an importable name through
# a symbolic link in a scratch directory, which is undone when the check ends.
typecheck:
	@work="$$(mktemp -d)"; \
	ln -s "$(CURDIR)" "$$work/techtree_hermes"; \
	MYPYPATH="$$work" $(RUN) mypy --namespace-packages -p techtree_hermes; \
	status=$$?; \
	unlink "$$work/techtree_hermes"; \
	rmdir "$$work"; \
	exit $$status

check: format-check lint typecheck
	@echo
	@echo "The plugin's tests run from the Techtree repository beside this one:"
	@echo "    make test-plugin        (in the techtree-python checkout)"
