#!/usr/bin/env python3
"""Debug helper: fetch one Dime! email's PDF, decrypt it, and print both the
raw extracted text and the fields the current regexes pick out.

Use this to tune the FIELD_PATTERNS in src/pdf_parser.py against a real
sample — the raw text output shows exactly what labels/formatting Dime!
actually uses.

Usage:
    python3 scripts/dump_pdf_text.py            # most recent Dime! email
    python3 scripts/dump_pdf_text.py <message_id>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import gmail_client  # noqa: E402
import pdf_parser  # noqa: E402
from secrets_store import get_pdf_password  # noqa: E402


def main() -> None:
    service = gmail_client.get_gmail_service()
    password = get_pdf_password()

    if len(sys.argv) > 1:
        message_id = sys.argv[1]
    else:
        ids = gmail_client.find_dime_message_ids(service, max_results=1)
        if not ids:
            print("No Dime! emails found.")
            return
        message_id = ids[0]

    print(f"Message ID: {message_id}\n")
    email = gmail_client.fetch_pdf_attachment(service, message_id)
    if email is None:
        print("No PDF attachment found on this message.")
        return

    text = pdf_parser.extract_text(email.pdf_bytes, password)
    print("=" * 60)
    print("RAW EXTRACTED TEXT")
    print("=" * 60)
    print(text)

    print("\n" + "=" * 60)
    print("PARSED FIELDS (current regexes)")
    print("=" * 60)
    fields = pdf_parser.parse_fields(text)
    for key, value in fields.items():
        if key == "raw_text":
            continue
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
