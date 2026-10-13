from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.auth.deps import COOKIE_NAME, get_current_user
from app.auth.tokens import issue_token
from app.core.client_ip import client_ip
from app.core.config import get_settings
from app.core.rate_limit import enforce
from app.db.database import get_session
from app.models import User
from app.schemas.auth import LoginIn, RegisterIn, UserOut
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _client(request: Request) -> str:
    return client_ip(request)


def _start_session(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        issue_token(user),
        max_age=settings.session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


@router.post("/register", status_code=201)
def register(
    payload: RegisterIn, request: Request, response: Response, session: Session = Depends(get_session)
) -> UserOut:
    enforce("auth_register", _client(request), get_settings().auth_register_per_window)
    user = auth_service.register(session, payload)
    _start_session(response, user)
    return UserOut.model_validate(user)


@router.post("/login")
def login(
    payload: LoginIn, request: Request, response: Response, session: Session = Depends(get_session)
) -> UserOut:
    settings = get_settings()
    enforce("auth_login_ip", _client(request), settings.auth_login_ip_per_window)
    enforce("auth_login_email", payload.email, settings.auth_login_email_per_window)
    user = auth_service.login(session, payload)
    _start_session(response, user)
    return UserOut.model_validate(user)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
