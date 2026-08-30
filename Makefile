.DEFAULT_GOAL := check

.PHONY: check check-cli check-plugin check-plugin-integration check-platform

check: check-cli check-plugin check-plugin-integration check-platform

check-cli:
	$(MAKE) -C cli check

check-plugin:
	$(MAKE) -C plugin check

check-plugin-integration:
	$(MAKE) -C cli check-plugin

check-platform:
	cd platform && mix deps.get && mix assets.setup && mix assets.build && mix check
