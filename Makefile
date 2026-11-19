.DEFAULT_GOAL := check

.PHONY: check check-plugin plugin-release-core check-platform platform-setup platform-precommit check-required-fixes check-cli check-siwa-latest release readiness live-check

# make check sets the platform up first (its dependencies and built assets, which
# mix precommit needs), then runs every other gate side by side, each writing its
# output to $(CHECK_LOGS)/<gate>.log; it prints every gate's log, the failed ones
# last, and one line per gate, and fails when any gate failed. No gate writes
# anything another reads.
CHECK_LANES := platform-precommit check-plugin check-required-fixes \
  check-cli check-siwa-latest check-contracts check-formal check-swarm check-lab
CHECK_GATES := platform-setup $(CHECK_LANES)
CHECK_LOGS := platform/_build/check
# Each gate's budget in seconds, about 40% over its time in make check on a 16-core
# Mac shared with other agents' checks (Nov 2026), and 5 s for a gate that takes a
# second or three. A gate over its budget gets a SLOW line under its own at the end;
# it never fails the check.
CHECK_BUDGETS := platform-setup:65 platform-precommit:20 \
  check-plugin:5 check-required-fixes:5 check-cli:5 check-siwa-latest:5 check-contracts:35 \
  check-formal:20 check-swarm:30 check-lab:5
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
	  budget=$$(printf '%s\n' $(CHECK_BUDGETS) | sed -n "s/^$$gate://p"); \
	  if [ "$$3" -gt "$$budget" ]; then echo "SLOW: $$gate took $$3 s (budget $$budget s)"; fi; \
	done; \
	test -z "$$failed"

check-plugin:
	$(MAKE) -C plugin check

# The plugin's embedded ReleaseCore, checked and its digest printed.
plugin-release-core:
	$(MAKE) -C plugin release-core

# The platform's gates, one after another: its dependencies and built assets, then
# mix precommit (the static checks).
check-platform: platform-setup platform-precommit
platform-setup:
	cd platform && mix deps.get && mix assets.setup && mix assets.build
platform-precommit:
	cd platform && mix precommit

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
REGENTS_CLI_REV := c12d8563c46e8b5229e32db76c1a104fb469b7b7
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

# The Swarm Verify models of agent-swarm coordination (swarm-verify/README.md), checked
# with Everystate, then the reference implementation's logs and a seeded run of 128
# workers checked against them, in about 20 s with no Java. swarm-tlc also checks every
# model with TLC and compares the two, which needs Java 17 or later on PATH.
.PHONY: check-swarm swarm-tlc
check-swarm:
	swarm-verify/check.sh

swarm-tlc:
	swarm-verify/check.sh tlc

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
