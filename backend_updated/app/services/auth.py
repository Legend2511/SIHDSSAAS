"""
WeatherGPT — Auth Service

Minimal, dependency-light authentication:
  - Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib `hashlib`, no
    extra native/compiled dependency such as bcrypt).
  - Sessions are stateless JWT access tokens (PyJWT), signed with
    `settings.secret_key`.

This is intentionally simple for an MVP/demo. Before any real deployment,
set a strong, random `SECRET_KEY` in `.env` and serve the API over HTTPS.
"""

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from app.core.config import settings

_PBKDF2_ITERATIONS = 260_000
_ALGORITHM = "HS256"


# =============================================================================
# Password hashing
# =============================================================================

def hash_password(password: str) -> str:
    """Hash a password as `pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>`."""
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded_hash: Optional[str]) -> bool:
    """Verify a plaintext password against a hash produced by `hash_password`."""
    if not encoded_hash:
        return False
    try:
        algorithm, iterations_str, salt_hex, hash_hex = encoded_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


# =============================================================================
# JWT access tokens
# =============================================================================

def create_access_token(*, user_id: str, email: str) -> str:
    """Create a signed JWT access token carrying the user id and email."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT access token. Returns the payload, or None if invalid/expired."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
