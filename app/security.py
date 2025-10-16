import base64
import os
from functools import lru_cache
from cryptography.fernet import Fernet, InvalidToken


def _load_key_from_env() -> bytes:
    key = os.getenv("SECURE_ENCRYPTION_KEY")
    if not key:
        key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    try:
        return key.encode()
    except Exception as exc:
        raise RuntimeError("Invalid SECURE_ENCRYPTION_KEY") from exc


@lru_cache(maxsize=1)
def get_fernet() -> Fernet:
    return Fernet(_load_key_from_env())


def encrypt_text(plain_text: str) -> bytes:
    if plain_text is None:
        plain_text = ""
    return get_fernet().encrypt(plain_text.encode("utf-8"))


def decrypt_text(cipher_bytes: bytes) -> str:
    if not cipher_bytes:
        return ""
    try:
        return get_fernet().decrypt(cipher_bytes).decode("utf-8")
    except InvalidToken:
        return "[DECRYPTION ERROR]"
