import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt

from app.core.config import get_settings
from app.models import User

_ALGORITHM = "HS256"


def issue_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(user.id),
        "ver": user.token_version,
        "iat": now,
        "exp": now + timedelta(days=settings.session_days),
    }
    return jwt.encode(claims, settings.secret_key, algorithm=_ALGORITHM)


def read_token(token: str) -> dict[str, Any] | None:
    """Verified claims, or None for anything malformed, expired, tampered with or unsigned."""
    try:
        claims = jwt.decode(
            token, get_settings().secret_key, algorithms=[_ALGORITHM],
            options={"require": ["exp", "sub", "ver"]},
        )
        UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None
    return claims


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def issue_action_token(user: User, purpose: str, minutes: int) -> str:
    """Short-lived emailed token. The audience keeps one purpose's token from working for another.

    Reset tokens bind to the current password hash and verification tokens to the current email,
    so using one (or changing the account) invalidates it.
    """
    now = datetime.now(UTC)
    bound = user.password_hash if purpose == "reset" else user.email
    claims = {
        "sub": str(user.id),
        "aud": purpose,
        "bind": _fingerprint(bound),
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(claims, get_settings().secret_key, algorithm=_ALGORITHM)


def read_action_token(token: str, purpose: str) -> tuple[UUID, str] | None:
    """(user id, bound fingerprint), or None when invalid, expired or issued for another purpose."""
    try:
        claims = jwt.decode(
            token, get_settings().secret_key, algorithms=[_ALGORITHM], audience=purpose,
            options={"require": ["exp", "sub", "aud", "bind"]},
        )
        return UUID(claims["sub"]), str(claims["bind"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


def matches_binding(user: User, purpose: str, fingerprint: str) -> bool:
    bound = user.password_hash if purpose == "reset" else user.email
    return hmac.compare_digest(_fingerprint(bound), fingerprint)
