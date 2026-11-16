.DEFAULT_GOAL := check

.PHONY: check check-plugin plugin-release-core check-platform platform-setup platform-precommit platform-test check-required-fixes check-cli check-siwa-latest release readiness browser live-check

# make check sets the platform up first (its dependencies and built assets, which
# both platform gates need), then runs every other gate side by side, each writing
# its output to $(CHECK_LOGS)/<gate>.log; it prints every gate's log, the failed
# ones last, and one line per gate, and fails when any gate failed. mix precommit
# (the static checks, then the browser walk) and mix test both compile _build/test,
# which Mix does for one of them at a time. The walk's own server rebuilds
# assets/vendor and priv/static/assets, which no ExUnit test reads but one asking
# for site.css, rewritten in place and never absent; and it drops and makes only
# its own database. The other gates write nothing another reads.
CHECK_LANES := platform-precommit platform-test check-change-runner check-plugin check-required-fixes \
  check-cli check-siwa-latest check-contracts check-formal check-lab
CHECK_GATES := platform-setup $(CHECK_LANES)
CHECK_LOGS := platform/_build/check
# One gate, its output in its own log, then its exit code and seconds in the results.
CHECK_GATE = start=$$(date +%s); $(MAKE) --no-print-directory $$gate > $(CHECK_LOGS)/$$gate.log 2>&1; \
  code=$$?; echo "$$gate $$code $$(( $$(date +%s) - start ))" >> $(CHECK_LOGS)/results
check:
	@mkdir -p $(CHECK_LOGS) && : > $(CHECK_LOGS)/results
	@echo "Setting the platform up, then running $(words $(CHECK_LANES)) gates side by side; each writes $(CHECK_LOGS)/<gate>.log."
	@gate=platform-setup; $(CHECK_GATE); \
	grep -q "^platform-setup 0 " $(CHECK_LOGS)/results || \
	  { echo "== platform-setup FAILED ($(CHECK_LOGS)/platform-setup.log)"; cat $(CHECK_LOGS)/platform-setup.log; exit 1; }
	@for gate in $(CHECK_LANES); do ($(CHECK_GATE)) & done; wait
	@failed=; \
	for gate in $(CHECK_GATES); do \
	  if grep -q "^$$gate 0 " $(CHECK_LOGS)/results; then \
	    echo; echo "== $$gate ($(CHECK_LOGS)/$$gate.log)"; cat $(CHECK_LOGS)/$$gate.log; \
	  else failed="$$failed $$gate"; fi; \
	done; \
	for gate in $$failed; do \
	  echo; echo "== $$gate FAILED ($(CHECK_LOGS)/$$gate.log)"; cat $(CHECK_LOGS)/$$gate.log; \
	done; \
	echo; \
	for gate in $(CHECK_GATES); do \
	  set -- $$(grep "^$$gate " $(CHECK_LOGS)/results); \
	  if [ "$$2" = 0 ]; then echo "$$gate: ok in $$3 s"; else echo "$$gate: FAILED after $$3 s"; fi; \
	done; \
	test -z "$$failed"

check-plugin:
	$(MAKE) -C plugin check

# The plugin's embedded ReleaseCore, checked and its digest printed.
plugin-release-core:
	$(MAKE) -C plugin release-core

# The platform's gates, one after another: its dependencies and built assets, then
# mix precommit (the static checks, the script tests and the browser walk), then
# mix test.
check-platform: platform-setup platform-precommit platform-test
platform-setup:
	cd platform && mix deps.get && mix assets.setup && mix assets.build
platform-precommit:
	cd platform && mix precommit
platform-test:
	cd platform && mix test

# The browser tests alone: the main pages in headless Chromium at 1280, 390 and
# 320 wide, signed out and signed in. check-platform runs them too.
browser:
	cd platform/assets && npm run test:browser

# The live site, signed out, in headless Chromium at 1280 and 390 wide: the commit
# it runs, every public page and document, the browser tools the home page offers,
# the Agent Message window and the theme switch; then two reads signed with this
# Mac's own agent key through the regents command line: who the agent is and that
# it is paired, and its person's Points (scripts/live-check.sh). It writes nothing;
# the signed reads change only the time the site last saw the agent. Run it
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
REGENTS_CLI_REV := 4a781568f763e2f7c1165684c4d8d8e2341ce0ee
check-cli:
	uv run --no-project --with "regents-cli[check] @ git+https://github.com/regents-ai/regents-cli@$(REGENTS_CLI_REV)" \
	  python -m regents_cli.check_commands cli/commands.json platform/priv/public/openapi.json

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

# Under nice: the Solidity compiler and the fuzzer take every core they can, and
# beside the other gates in make check they give way to them.
.PHONY: check-contracts
check-contracts:
	cd contracts && forge fmt --check && nice forge build --offline && nice forge test --offline

# The lab: the payment-terms environment, its runner and the training settings file.
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
