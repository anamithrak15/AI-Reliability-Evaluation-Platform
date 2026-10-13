import logging

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, verify_password
from app.auth.tokens import issue_action_token, matches_binding, read_action_token
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.seed import seed_demo_dataset
from app.models import Dataset, EvaluationRun, User
from app.models.entities import utcnow
from app.schemas.auth import LoginIn, RegisterIn
from app.services.mailer import Mail

logger = logging.getLogger(__name__)


def register(session: Session, payload: RegisterIn) -> User:
    settings = get_settings()
    if not settings.allow_registration:
        raise AppError(403, "registration_closed", "New account registration is disabled")
    if session.scalar(select(User.id).where(User.email == payload.email)) is not None:
        raise AppError(409, "email_taken", "An account with this email already exists")

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    session.add(user)
    try:
        session.flush()
        if session.scalar(select(func.count()).select_from(User)) == 1:
            # Data created before accounts existed belongs to whoever registers first.
            session.execute(update(Dataset).where(Dataset.user_id.is_(None)).values(user_id=user.id))
            session.execute(
                update(EvaluationRun).where(EvaluationRun.user_id.is_(None)).values(user_id=user.id)
            )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise AppError(409, "email_taken", "An account with this email already exists") from None

    if settings.demo_mode:
        try:
            seed_demo_dataset(session, settings.demo_dataset_path, user.id)
        except Exception:
            session.rollback()
            logger.exception("could not seed the demo dataset for a new account")
    return user


def login(session: Session, payload: LoginIn) -> User:
    user = session.scalar(select(User).where(User.email == payload.email))
    matches, new_hash = verify_password(user.password_hash if user else None, payload.password)
    if user is None or not matches or not user.is_active:
        # One message for every failure so the response never reveals which part was wrong.
        raise AppError(401, "invalid_credentials", "Incorrect email or password")
    if new_hash:
        user.password_hash = new_hash
        session.commit()
    return user


def _bad_link() -> AppError:
    return AppError(400, "invalid_token", "This link is invalid or has expired")


def _link(path: str, token: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/#/{path}?token={token}"


def verification_mail(user: User) -> Mail:
    settings = get_settings()
    token = issue_action_token(user, "verify", settings.verify_token_minutes)
    return Mail(
        to=user.email,
        subject="Verify your email address",
        body="Confirm your email address to finish setting up your account:\n\n"
        f"{_link('verify-email', token)}\n\nThe link expires in "
        f"{settings.verify_token_minutes // 60} hours. If you did not sign up, ignore this message.\n",
    )


def reset_mail(user: User) -> Mail:
    settings = get_settings()
    token = issue_action_token(user, "reset", settings.reset_token_minutes)
    return Mail(
        to=user.email,
        subject="Reset your password",
        body="Use this link to choose a new password:\n\n"
        f"{_link('reset-password', token)}\n\nThe link works once and expires in "
        f"{settings.reset_token_minutes} minutes. If you did not ask for this, ignore this message.\n",
    )


def _user_for_token(session: Session, token: str, purpose: str) -> User:
    decoded = read_action_token(token, purpose)
    user = session.get(User, decoded[0]) if decoded else None
    if user is None or not user.is_active or not matches_binding(user, purpose, decoded[1]):
        raise _bad_link()
    return user


def verify_email(session: Session, token: str) -> User:
    user = _user_for_token(session, token, "verify")
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
        session.commit()
    return user


def reset_password(session: Session, token: str, new_password: str) -> None:
    user = _user_for_token(session, token, "reset")
    user.password_hash = hash_password(new_password)
    # Following the link proves the mailbox is theirs; ending old sessions covers a stolen cookie.
    user.token_version += 1
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
    session.commit()


def change_password(session: Session, user: User, current: str, new: str) -> User:
    matches, _ = verify_password(user.password_hash, current)
    if not matches:
        raise AppError(400, "invalid_credentials", "Current password is incorrect")
    user.password_hash = hash_password(new)
    user.token_version += 1
    session.commit()
    return user
