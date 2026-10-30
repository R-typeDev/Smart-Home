from cryptography.fernet import Fernet, InvalidToken

from config import get_env


def _get_cipher() -> Fernet:
    key = get_env("SMART_HOME_SECRET_KEY")

    if not key:
        raise RuntimeError(
            "SMART_HOME_SECRET_KEY is not configured."
        )

    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as error:
        raise RuntimeError(
            "SMART_HOME_SECRET_KEY is invalid."
        ) from error


def encrypt_secret(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("Secret value cannot be empty.")

    return _get_cipher().encrypt(value.encode("utf-8"))


def decrypt_secret(encrypted_value: bytes) -> str:
    if not isinstance(encrypted_value, bytes) or not encrypted_value:
        raise ValueError("Encrypted secret cannot be empty.")

    try:
        decrypted = _get_cipher().decrypt(encrypted_value)
        return decrypted.decode("utf-8")
    except (InvalidToken, UnicodeDecodeError) as error:
        raise RuntimeError(
            "Could not decrypt secret. Check the encryption key."
        ) from error