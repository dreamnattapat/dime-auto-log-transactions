---
name: dime-dashboard
description: Open, refresh, or sync the Dime! P&L dashboard and transactions spreadsheet in this repo. Use when the user asks to open/view/show the dashboard or the Excel file, refresh/regenerate it, or pull in new Dime! trades.
argument-hint: "[open | refresh | sync | excel]"
---

# Dime! dashboard

Everything goes through the repo's `Makefile` (run from the project root). It
calls `venv/bin/python` directly, so there's no need to activate the venv.

Pick the target based on what the user asked for (or on `$ARGUMENTS` if given):

| Request | Command | What it does |
|---|---|---|
| "open the dashboard" (default) | `make open` | Opens `data/dashboard.html` in the browser as-is |
| "refresh / regenerate the dashboard" | `make dashboard` | Rebuilds from `data/dime_transactions.xlsx`, then opens it. No Gmail access |
| "sync" / "pull new trades" / "update everything" | `make sync` | Fetches new Dime! emails into the spreadsheet, rebuilds the dashboard, opens it |
| "open the spreadsheet / Excel" | `make excel` | Opens `data/dime_transactions.xlsx` |
| "test the parser" | `make dry-run LIMIT=3` | Parses recent emails without writing anything |

Run `make` with no arguments to list every target.

## Notes

- Before `make open`, check when `data/dashboard.html` was last modified. If
  it's more than a few days old, tell the user and offer `make sync`. The
  dashboard only changes when a sync or rebuild runs.
- `make sync` needs network access to Gmail and may open a browser for OAuth
  if `credentials/token.json` has expired. If it fails, show the user the error
  and point them to `logs/dime_log.log`.
- `data/`, `logs/` and `credentials/` are gitignored and hold personal
  financial data. Don't commit, upload or paste their contents anywhere.
- When you're done, give a one-line summary, such as "Opened the dashboard
  (last updated Aug 29)" or "Synced 2 new trades and opened the dashboard."
