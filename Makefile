.DEFAULT_GOAL := check

.PHONY: check check-plugin plugin-release-core check-platform check-required-fixes check-cli check-siwa-latest release readiness browser live-check

check: check-change-runner check-plugin check-platform check-required-fixes check-cli check-siwa-latest check-contracts check-formal check-lab

check-plugin:
	$(MAKE) -C plugin check

# The plugin's embedded ReleaseCore, checked and its digest printed.
plugin-release-core:
	$(MAKE) -C plugin release-core

check-platform:
	cd platform && mix deps.get && mix assets.setup && mix assets.build && mix precommit

# The browser tests alone: the main pages in headless Chromium at 1280, 390 and
# 320 wide, signed out and signed in. check-platform runs them too.
browser:
	cd platform/assets && npm run test:browser

# The live site, signed out, in headless Chromium at 1280 and 390 wide: the commit
# it runs, every public page and document, the browser tools the home page offers
# and the Agent Message window (scripts/live-check.sh). It writes nothing. Run it
# after each release; COMMIT=<commit> names the released commit once the release
# record sits on top of it.
live-check:
	scripts/live-check.sh $(COMMIT)

# Every site runs the same check against ash-template's current main branch, so a
# newly published required fix reaches every site's next gate. Needs `gh auth login`.
TEMPLATE := repos/regents-ai/ash-template
check-required-fixes:
	cd platform && mkdir -p _build && rev=$$(gh api $(TEMPLATE)/commits/main --jq .sha) \
	&& gh api -H "Accept: application/vnd.github.raw" "$(TEMPLATE)/contents/platform/scripts/check_required_fixes.exs?ref=$$rev" > _build/check_required_fixes.exs \
	&& gh api -H "Accept: application/vnd.github.raw" "$(TEMPLATE)/contents/security/required-fixes.json?ref=$$rev" > _build/required-fixes.json \
	&& elixir _build/check_required_fixes.exs "ash-template $$rev" < _build/required-fixes.json

# The command description check is regents-cli's own checker at the commit pinned
# here, run by uv straight from GitHub. Move the pin in a commit.
REGENTS_CLI_REV := fd325437e29fc6b239955e6ce946168bea2fb4ef
check-cli:
	uv run --no-project --with "regents-cli[check] @ git+https://github.com/regents-ai/regents-cli@$(REGENTS_CLI_REV)" \
	  python -m regents_cli.check_commands cli/commands.json cli/openapi.json

# Every site is on the newest SIWA: the newest regents-cli release on PyPI (the pin
# above, the agent guide and the install lines) and the newest change to the SIWA
# library in elixir-utils. Needs `gh auth login`.
check-siwa-latest:
	scripts/check-siwa-latest.sh $(REGENTS_CLI_REV)

# The model of the Wallet Bench funding cap (formal/wallet_bench_funding/README.md):
# its witness traces and random runs, in seconds, with no Java. formal-proof adds
# Apalache's proof for every depth, which needs Java 17 or later on PATH.
.PHONY: check-formal formal-proof
check-formal:
	formal/wallet_bench_funding/check.sh

formal-proof:
	formal/wallet_bench_funding/check.sh proof

.PHONY: check-contracts
check-contracts:
	cd contracts && forge fmt --check && forge build --offline && forge test --offline

# The lab: the payment-terms environment, its runner and the Train report checks.
.PHONY: check-lab
check-lab:
	$(MAKE) -C lab check

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

# The template change loop; BASE=<ref> selects the comparison.
.PHONY: check-change
check-change:
	python3 scripts/check-change.py

.PHONY: check-change-runner
check-change-runner:
	python3 -m unittest discover -s scripts/tests -p 'test_check_change.py'
