"""Passwords, sessions, CSRF and at-rest encryption."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings
from .models import now

_hasher = PasswordHasher()

SESSION_COOKIE = "pw_session"
CSRF_COOKIE = "pw_csrf"
CSRF_HEADER = "x-csrf-token"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_id(token: str) -> str:
    """Sessions are stored by hash so a database leak does not leak live cookies."""
    return hashlib.sha256(token.encode()).hexdigest()


def session_expiry():
    return now() + timedelta(hours=get_settings().session_ttl_hours)


def _fernet() -> Fernet:
    key = hashlib.sha256(get_settings().app_secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(enc: str) -> str:
    try:
        return _fernet().decrypt(enc.encode()).decode()
    except InvalidToken as e:  # pragma: no cover
        raise RuntimeError("Cannot decrypt stored secret. APP_SECRET_KEY changed?") from e


def key_hint(plain: str) -> str:
    return plain[-4:] if len(plain) >= 8 else "****"


class RateLimiter:
    """Small in-memory sliding-window limiter. Good enough for a single-process app."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        cutoff = time.monotonic() - self.window
        q = self._hits[key]
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(time.monotonic())
        return True


login_limiter = RateLimiter(limit=10, window_seconds=300)
llm_limiter = RateLimiter(limit=60, window_seconds=60)
