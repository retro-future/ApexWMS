"""Argon2id password hashing (PRD §9 Security)."""

from argon2 import PasswordHasher as _Argon2Hasher
from argon2.exceptions import InvalidHashError, VerificationError


class Argon2PasswordHasher:
    """Implements the application ``PasswordHasher`` port."""

    def __init__(self) -> None:
        # argon2-cffi defaults use the argon2id variant.
        self._hasher = _Argon2Hasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False
