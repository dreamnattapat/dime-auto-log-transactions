# Shortcuts for the Dime! auto-logger. Run `make` to list targets.
# Uses the venv's python directly, so no need to `source venv/bin/activate`.

PYTHON    := venv/bin/python
DASHBOARD := data/dashboard.html
EXCEL     := data/dime_transactions.xlsx
PLIST     := com.dreamnattapat.dimelog
LIMIT     ?= 3

.DEFAULT_GOAL := help
.PHONY: help open excel dashboard sync dry-run logs install secret schedule-status schedule-run

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

open: ## Open the dashboard in your browser (as-is, no refresh)
	@test -f $(DASHBOARD) || { echo "No $(DASHBOARD) yet — run 'make dashboard' or 'make sync'"; exit 1; }
	open $(DASHBOARD)

excel: ## Open the transactions spreadsheet in Excel/Numbers
	open $(EXCEL)

dashboard: ## Rebuild the dashboard from the spreadsheet and open it (no Gmail sync)
	$(PYTHON) scripts/generate_dashboard.py

sync: ## Pull new Dime! emails into Excel, rebuild the dashboard, open it
	$(PYTHON) src/main.py
	open $(DASHBOARD)

dry-run: ## Parse the latest LIMIT emails without writing anything (default LIMIT=3)
	$(PYTHON) src/main.py --limit $(LIMIT) --dry-run

logs: ## Follow the sync log
	tail -f logs/dime_log.log

install: ## Create the venv and install dependencies
	python3 -m venv venv
	$(PYTHON) -m pip install -r requirements.txt

secret: ## Store/replace the PDF password (birthdate) in the Keychain
	$(PYTHON) scripts/setup_secret.py

schedule-status: ## Show whether the daily launchd job is loaded
	@launchctl list | grep dimelog || echo "Not loaded"

schedule-run: ## Trigger the launchd job right now
	launchctl start $(PLIST)
