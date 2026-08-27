#!/usr/bin/env python3
"""One-time setup: store your birthdate (PDF password) in the macOS Keychain.

The value never touches disk in plaintext — it's handed straight to the
Keychain via the `keyring` library.
"""
import getpass
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from secrets_store import set_pdf_password  # noqa: E402


def main() -> None:
    print("This stores your Dime! PDF password (birthdate, format DDMMYYYY)")
    print("encrypted in your macOS login Keychain.\n")
    value = getpass.getpass("Enter birthdate as DDMMYYYY (input hidden): ").strip()

    if not re.fullmatch(r"\d{8}", value):
        print("Error: expected exactly 8 digits in DDMMYYYY format.", file=sys.stderr)
        sys.exit(1)

    set_pdf_password(value)
    print("Saved to Keychain (service='dime-auto-log-transactions', account='pdf-password').")
    print("You can verify it in Keychain Access.app, or revoke it any time by deleting that entry.")


if __name__ == "__main__":
    main()
