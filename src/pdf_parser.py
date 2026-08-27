"""Decrypts and parses Dime! (KKP Dime Securities) trade confirmation PDFs.

Tuned against a real sample (`scripts/dump_pdf_text.py` output, 2026-08-27):
a foreign-stock BUY confirmation. pdfplumber mangles the table's header row
(Thai/English glyphs get interleaved character-by-character), but the actual
data rows extract cleanly as flat lines, e.g.:

    671785 27/08/2026 BUY NVTS 100.0000000 12.79 USD 1,278.50 2.05 0.00 1,280.55
    [XNAS] 41,617.99 66.73 0.00 41,684.72

One confirmation email can contain multiple order rows, so `parse_pdf`
returns a list of transaction dicts (usually length 1).
"""
import io
import re

import pdfplumber

TRANSACTION_TYPES = {
    "BUY": "Buy",
    "SEL": "Sell",
    "REW": "Reward",
    "EXC": "Exercise Call",
    "EXP": "Exercise Put",
}

# Main order row, e.g.:
# 671785 27/08/2026 BUY NVTS 100.0000000 12.79 USD 1,278.50 2.05 0.00 1,280.55
TRANSACTION_ROW_RE = re.compile(
    r"^(?P<order_id>\d+)\s+"
    r"(?P<settlement_date>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<transaction_type>BUY|SEL|REW|EXC|EXP)\s+"
    r"(?P<security>[A-Z0-9.]+)\s+"
    r"(?P<units>[\d,]+\.\d+)\s+"
    r"(?P<unit_price>[\d,]+\.\d+)\s+"
    r"(?P<currency>[A-Z]{3})\s+"
    r"(?P<gross_amount>[\d,]+\.\d+)\s+"
    r"(?P<vat>[\d,]+\.\d+)\s+"
    r"(?P<withholding_tax>[\d,]+\.\d+)\s+"
    r"(?P<total_amount>[\d,]+\.\d+)\s*$",
    re.MULTILINE,
)

# THB-equivalent row that immediately follows an order row, e.g.:
# [XNAS] 41,617.99 66.73 0.00 41,684.72
EXCHANGE_ROW_RE = re.compile(
    r"^\[(?P<exchange>[A-Za-z0-9]+)\]\s+"
    r"(?P<gross_amount_thb>[\d,]+\.\d+)\s+"
    r"(?P<vat_thb>[\d,]+\.\d+)\s+"
    r"(?P<withholding_tax_thb>[\d,]+\.\d+)\s+"
    r"(?P<total_amount_thb>[\d,]+\.\d+)\s*$",
    re.MULTILINE,
)

# One value per document (attached to every transaction row found in it).
HEADER_PATTERNS = {
    "account_no": r"Account No\.\s*(\d+)",
    "tax_invoice_no": r"Tax Invoice No\.\s*(\S+)",
    "total_buy_thb": r"รวมมูลค่าซื้อ\s*\(THB\)\s*([\d,]+\.\d+)",
    "total_sell_thb": r"รวมมูลค่าขาย\s*\(THB\)\s*([\d,]+\.\d+)",
    "total_fee_thb": r"ค่าธรรมเนียมไม่รวมภาษีมูลค่าเพิ่ม\s*([\d,]+\.\d+)",
    "total_vat_thb": r"ภาษีมูลค่าเพิ่ม\s*\(THB\)\s*([\d,]+\.\d+)",
    "total_withholding_tax_thb": r"ภาษีหัก\s*ณ\s*ที่จ่าย\s*\(THB\)\s*([\d,]+\.\d+)",
    "fx_rate_thb_usd": r"THB/USD\s*=\s*([\d.]+)",
}

EFFECTIVE_ISSUE_DATE_RE = re.compile(
    r"วันที่คำสั่งมีผล\s*วันที่ออกใบกำกับภาษี\s*\n\s*"
    r"(?P<effective_date>\d{2}/\d{2}/\d{4})\s+(?P<issue_date>\d{2}/\d{2}/\d{4})"
)


def extract_text(pdf_bytes: bytes, password: str) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes), password=password) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _parse_headers(text: str) -> dict:
    headers = {}
    for name, pattern in HEADER_PATTERNS.items():
        match = re.search(pattern, text)
        headers[name] = match.group(1).strip() if match else None

    date_match = EFFECTIVE_ISSUE_DATE_RE.search(text)
    headers["effective_date"] = date_match.group("effective_date") if date_match else None
    headers["issue_date"] = date_match.group("issue_date") if date_match else None
    return headers


def parse_fields(text: str) -> list[dict]:
    headers = _parse_headers(text)
    lines = text.splitlines()

    transactions = []
    for i, line in enumerate(lines):
        row_match = TRANSACTION_ROW_RE.match(line)
        if not row_match:
            continue

        row = row_match.groupdict()
        row["transaction_type"] = TRANSACTION_TYPES.get(
            row["transaction_type"], row["transaction_type"]
        )

        # THB-equivalent totals are on the next line, if present.
        if i + 1 < len(lines):
            exchange_match = EXCHANGE_ROW_RE.match(lines[i + 1])
            if exchange_match:
                row.update(exchange_match.groupdict())

        row.update(headers)
        row["parse_status"] = "ok"
        transactions.append(row)

    if not transactions:
        # Nothing matched — surface a row so the email isn't silently dropped;
        # the raw text snippet helps diagnose a layout change.
        fallback = {key: None for key in HEADER_PATTERNS}
        fallback.update(headers)
        fallback["parse_status"] = "unparsed"
        fallback["raw_text_snippet"] = text[:500]
        transactions.append(fallback)

    return transactions


def parse_pdf(pdf_bytes: bytes, password: str) -> list[dict]:
    text = extract_text(pdf_bytes, password)
    return parse_fields(text)
