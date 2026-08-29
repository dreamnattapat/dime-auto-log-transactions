#!/usr/bin/env python3
import argparse
import logging
import sys

import analytics
import config
import dashboard
import excel_writer
import gmail_client
import pdf_parser
import state
from secrets_store import get_pdf_password


def setup_logging() -> None:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(config.LOG_FILE),
            logging.StreamHandler(sys.stdout),
        ],
    )


def run(limit: int | None, dry_run: bool) -> None:
    logger = logging.getLogger(__name__)
    logger.info("Starting Dime! transaction sync (limit=%s, dry_run=%s)", limit, dry_run)

    password = get_pdf_password()
    service = gmail_client.get_gmail_service()

    processed_ids = state.load_processed_ids(config.PROCESSED_IDS_FILE)
    message_ids = gmail_client.find_dime_message_ids(service, max_results=limit)
    new_ids = [mid for mid in message_ids if mid not in processed_ids]

    logger.info("Found %d Dime! emails total, %d new", len(message_ids), len(new_ids))

    added = 0
    failed = 0
    for message_id in new_ids:
        try:
            email = gmail_client.fetch_pdf_attachment(service, message_id)
            if email is None:
                processed_ids.add(message_id)
                continue

            transactions = pdf_parser.parse_pdf(email.pdf_bytes, password)
            rows = excel_writer.build_rows(message_id, email.internal_date_ms, transactions)

            if dry_run:
                logger.info("[dry-run] would append %d row(s): %s", len(rows), rows)
            else:
                excel_writer.append_transactions(config.OUTPUT_EXCEL_FILE, rows)
                logger.info("Appended %d row(s) from message %s", len(rows), message_id)

            processed_ids.add(message_id)
            added += 1
        except Exception:
            logger.exception("Failed to process message %s", message_id)
            failed += 1

    if not dry_run:
        state.save_processed_ids(config.PROCESSED_IDS_FILE, processed_ids)
        dashboard.write_dashboard(config.DASHBOARD_FILE, analytics.build_analytics(config.OUTPUT_EXCEL_FILE))
        logger.info("Updated dashboard at %s", config.DASHBOARD_FILE)

    logger.info("Done. Added=%d Failed=%d", added, failed)


def main() -> None:
    sys.path.insert(0, str(config.ROOT_DIR / "src"))
    parser = argparse.ArgumentParser(description="Sync Dime! transaction emails into Excel")
    parser.add_argument("--limit", type=int, default=None, help="Max emails to scan (for testing)")
    parser.add_argument("--dry-run", action="store_true", help="Parse but don't write Excel/state")
    args = parser.parse_args()

    setup_logging()
    run(limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
