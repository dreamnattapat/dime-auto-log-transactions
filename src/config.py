from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_DIR = ROOT_DIR / "credentials"
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"

CLIENT_SECRET_FILE = CREDENTIALS_DIR / "client_secret.json"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"

PROCESSED_IDS_FILE = DATA_DIR / "processed_ids.json"
OUTPUT_EXCEL_FILE = DATA_DIR / "dime_transactions.xlsx"
LOG_FILE = LOGS_DIR / "dime_log.log"

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

EMAIL_SUBJECT = "[Dime!] ใบยืนยันการซื้อขาย"
GMAIL_SEARCH_QUERY = f'subject:"{EMAIL_SUBJECT}" has:attachment'

# Keychain entry for the PDF password (your birthdate, DDMMYYYY)
KEYCHAIN_SERVICE = "dime-auto-log-transactions"
KEYCHAIN_ACCOUNT = "pdf-password"
