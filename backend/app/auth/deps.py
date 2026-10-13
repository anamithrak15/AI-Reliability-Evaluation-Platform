from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.tokens import read_token
from app.core.errors import AppError
from app.db.database import get_session
from app.models import User

COOKIE_NAME = "session"


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    """Authenticate from the session cookie; every failure looks the same to the caller."""
    token = request.cookies.get(COOKIE_NAME)
    claims = read_token(token) if token else None
    user = session.get(User, UUID(claims["sub"])) if claims else None
    if user is None or not user.is_active or user.token_version != claims["ver"]:
        raise AppError(401, "not_authenticated", "Sign in to continue")
    return user
