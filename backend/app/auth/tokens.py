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
