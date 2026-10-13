from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import COOKIE_NAME, get_session_user
from app.auth.tokens import issue_token
from app.core.client_ip import client_ip
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.rate_limit import enforce
from app.db.database import get_session
from app.models import User
from app.schemas.auth import (
    ChangePasswordIn,
    EmailIn,
    LoginIn,
    RegisterIn,
    ResetPasswordIn,
    TokenIn,
    UserOut,
)
from app.services import auth_service, mailer

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
    payload: RegisterIn,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
) -> UserOut:
    enforce("auth_register", _client(request), get_settings().auth_register_per_window)
    user = auth_service.register(session, payload)
    background.add_task(mailer.send, auth_service.verification_mail(user))
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
def me(user: User = Depends(get_session_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/verify-email")
def verify_email(
    payload: TokenIn, request: Request, session: Session = Depends(get_session)
) -> UserOut:
    enforce("auth_token", _client(request), get_settings().auth_email_per_window * 4)
    return UserOut.model_validate(auth_service.verify_email(session, payload.token))


@router.post("/resend-verification", status_code=202)
def resend_verification(
    background: BackgroundTasks, user: User = Depends(get_session_user)
) -> None:
    enforce("auth_resend", str(user.id), get_settings().auth_email_per_window)
    if user.email_verified_at is None:
        background.add_task(mailer.send, auth_service.verification_mail(user))


@router.post("/forgot-password", status_code=202)
def forgot_password(
    payload: EmailIn,
    request: Request,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
) -> None:
    limit = get_settings().auth_email_per_window
    enforce("auth_forgot_ip", _client(request), limit * 2)
    enforce("auth_forgot_email", payload.email, limit)
    user = session.scalar(select(User).where(User.email == payload.email))
    # Same response whether or not the account exists, so this cannot be used to probe for emails.
    if user is not None and user.is_active:
        background.add_task(mailer.send, auth_service.reset_mail(user))


@router.post("/reset-password", status_code=204)
def reset_password(
    payload: ResetPasswordIn, request: Request, session: Session = Depends(get_session)
) -> None:
    enforce("auth_token", _client(request), get_settings().auth_email_per_window * 4)
    auth_service.reset_password(session, payload.token, payload.password)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordIn,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(get_session_user),
) -> UserOut:
    enforce("auth_change", str(user.id), get_settings().auth_login_email_per_window)
    if payload.current_password == payload.new_password:
        raise AppError(400, "password_unchanged", "Choose a password different from the current one")
    user = auth_service.change_password(session, user, payload.current_password, payload.new_password)
    _start_session(response, user)  # the version bump ended the old cookie, so keep this device signed in
    return UserOut.model_validate(user)
