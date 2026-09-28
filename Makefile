.DEFAULT_GOAL := check

.PHONY: check check-cli check-plugin check-plugin-integration check-platform check-required-fixes release readiness

check: check-cli check-plugin check-plugin-integration check-platform check-required-fixes check-contracts

check-cli:
	$(MAKE) -C cli check

check-plugin:
	$(MAKE) -C plugin check

check-plugin-integration:
	$(MAKE) -C cli check-plugin

check-platform:
	cd platform && mix deps.get && mix assets.setup && mix assets.build && mix precommit

# Every site runs the same check against ash-template's current main branch, so a
# newly published required fix reaches every site's next gate. Needs `gh auth login`.
TEMPLATE := repos/regents-ai/ash-template
check-required-fixes:
	cd platform && mkdir -p _build && rev=$$(gh api $(TEMPLATE)/commits/main --jq .sha) \
	&& gh api -H "Accept: application/vnd.github.raw" "$(TEMPLATE)/contents/platform/scripts/check_required_fixes.exs?ref=$$rev" > _build/check_required_fixes.exs \
	&& gh api -H "Accept: application/vnd.github.raw" "$(TEMPLATE)/contents/security/required-fixes.json?ref=$$rev" > _build/required-fixes.json \
	&& elixir _build/check_required_fixes.exs "ash-template $$rev" < _build/required-fixes.json

.PHONY: check-contracts
check-contracts:
	cd contracts && forge fmt --check && forge build --offline && forge test --offline

# The release checks and builds exactly the committed tree, so every change must
# be committed first. A failing gate stops it before anything is built.
release:
	@test -z "$$(git status --porcelain)" || { echo "Commit every change first: the release checks and builds the committed tree." >&2; exit 1; }
	$(MAKE) check
	scripts/release.sh

# Starts the local server on a free port, checks what the agent-readiness scorer
# looks for against it, and stops it. Needs the local development database.
readiness:
	scripts/readiness.sh
