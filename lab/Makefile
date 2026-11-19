# The lab's checks: formatting, lint and types. Light work: no model, no Prime.
.PHONY: check
check:
	uv lock --check
	uv run --locked ruff format --check .
	uv run --locked ruff check .
	uv run --locked mypy
