#!/usr/bin/env python3
"""Regenerate the HTML dashboard from data/dime_transactions.xlsx without
running a Gmail sync. Useful after editing the spreadsheet by hand, or to
preview dashboard.py changes.

Usage:
    python3 scripts/generate_dashboard.py
"""
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import analytics  # noqa: E402
import config  # noqa: E402
import dashboard  # noqa: E402


def main() -> None:
    result = analytics.build_analytics(config.OUTPUT_EXCEL_FILE)
    dashboard.write_dashboard(config.DASHBOARD_FILE, result)
    print(f"Wrote {config.DASHBOARD_FILE}")
    webbrowser.open(config.DASHBOARD_FILE.as_uri())


if __name__ == "__main__":
    main()
