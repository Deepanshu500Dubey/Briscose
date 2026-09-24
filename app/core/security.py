"""Password hashing, JWT access tokens, and opaque refresh tokens."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

_password_hasher = PasswordHash.recommended()  # Argon2, per pwdlib's recommended scheme


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password. Never store plaintext passwords."""
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    return _password_hasher.verify(plain_password, hashed_password)


def create_access_token(
    subject: str,
    role: str,
    token_version: int,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token for the given subject (user id).

    Embeds `role` (so authorization doesn't require a DB round-trip on every
    request) and `token_version` (so bumping it on the user row invalidates
    every outstanding access token immediately).
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "token_version": token_version,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Raises jwt.PyJWTError (or a subclass, e.g. ExpiredSignatureError,
    InvalidTokenError) if the token is invalid or expired. Callers are
    expected to catch this and translate it into an HTTP error.
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def generate_refresh_token() -> tuple[str, str]:
    """Generate a new opaque refresh token.

    Returns (raw_token, token_hash). Only the hash is ever persisted; the
    raw value is handed to the client once and is not recoverable from the
    stored hash.
    """
    raw_token = secrets.token_urlsafe(32)
    return raw_token, hash_refresh_token(raw_token)


def hash_refresh_token(raw_token: str) -> str:
    """Hash a raw refresh token for lookup/storage.

    Refresh tokens are already high-entropy random values (not
    user-chosen secrets like passwords), so a fast, deterministic hash is
    appropriate here — unlike passwords, there's no need for a slow,
    salted KDF such as Argon2.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
