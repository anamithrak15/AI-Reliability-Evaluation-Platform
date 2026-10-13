import logging

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, verify_password
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.seed import seed_demo_dataset
from app.models import Dataset, EvaluationRun, User
from app.schemas.auth import LoginIn, RegisterIn

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
