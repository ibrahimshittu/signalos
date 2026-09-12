from __future__ import annotations

from cryptography.fernet import Fernet, MultiFernet


class CredentialCipher:
    """Authenticated encryption for small broker credentials with rotation support.

    Keys must come from a deployment secret manager. New values are encrypted with the
    first key while older keys remain available only for decryption.

    Source: https://cryptography.io/en/latest/fernet/
    """

    def __init__(self, keys: tuple[str, ...]) -> None:
        if not keys:
            raise ValueError("at least one credential encryption key is required")
        self._cipher = MultiFernet([Fernet(key.encode()) for key in keys])

    def encrypt(self, plaintext: str) -> str:
        return self._cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        return self._cipher.decrypt(token.encode()).decode()


class UnavailableCredentialCipher:
    """Fail-closed placeholder used when no deployment encryption key is configured."""

    def encrypt(self, plaintext: str) -> str:
        del plaintext
        raise RuntimeError("broker credential encryption is not configured")

    def decrypt(self, token: str) -> str:
        del token
        raise RuntimeError("broker credential encryption is not configured")
