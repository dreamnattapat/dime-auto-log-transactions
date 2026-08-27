import base64
import logging
from dataclasses import dataclass

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config

logger = logging.getLogger(__name__)


@dataclass
class DimeEmail:
    message_id: str
    internal_date_ms: int
    pdf_filename: str
    pdf_bytes: bytes


def get_gmail_service():
    creds = None
    if config.TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(config.TOKEN_FILE), config.GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not config.CLIENT_SECRET_FILE.exists():
                raise RuntimeError(
                    f"Missing {config.CLIENT_SECRET_FILE}. Download an OAuth Desktop "
                    "client_secret.json from Google Cloud Console (see README) and place it there."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(config.CLIENT_SECRET_FILE), config.GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)
        config.CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        config.TOKEN_FILE.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def find_dime_message_ids(service, max_results: int | None = None) -> list[str]:
    ids: list[str] = []
    page_token = None
    while True:
        resp = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=config.GMAIL_SEARCH_QUERY,
                pageToken=page_token,
                maxResults=min(500, max_results) if max_results else 500,
            )
            .execute()
        )
        ids.extend(m["id"] for m in resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token or (max_results and len(ids) >= max_results):
            break
    return ids[:max_results] if max_results else ids


def fetch_pdf_attachment(service, message_id: str) -> DimeEmail | None:
    msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    internal_date_ms = int(msg["internalDate"])

    parts = msg.get("payload", {}).get("parts", []) or []
    pdf_part = _find_pdf_part(parts)
    if pdf_part is None:
        logger.warning("Message %s has no PDF attachment, skipping", message_id)
        return None

    attachment_id = pdf_part["body"]["attachmentId"]
    attachment = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
        .execute()
    )
    pdf_bytes = base64.urlsafe_b64decode(attachment["data"])

    return DimeEmail(
        message_id=message_id,
        internal_date_ms=internal_date_ms,
        pdf_filename=pdf_part.get("filename", f"{message_id}.pdf"),
        pdf_bytes=pdf_bytes,
    )


def _find_pdf_part(parts):
    for part in parts:
        filename = part.get("filename", "")
        if filename.lower().endswith(".pdf"):
            return part
        nested = part.get("parts")
        if nested:
            found = _find_pdf_part(nested)
            if found:
                return found
    return None
