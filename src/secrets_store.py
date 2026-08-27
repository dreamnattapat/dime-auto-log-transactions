import keyring

from config import KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT


def get_pdf_password() -> str:
    password = keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
    if not password:
        raise RuntimeError(
            "No PDF password found in macOS Keychain. "
            "Run `python3 scripts/setup_secret.py` first."
        )
    return password


def set_pdf_password(password: str) -> None:
    keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT, password)
