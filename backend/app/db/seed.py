import json
import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Dataset
from app.schemas.dataset import DatasetCreate
from app.services import dataset_service

logger = logging.getLogger(__name__)


def seed_demo_dataset(session: Session, path: str, user_id: UUID) -> bool:
    """Give one user a private copy of the demo dataset. Idempotent per user and name."""
    payload = DatasetCreate.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
    owned = select(Dataset.id).where(Dataset.name == payload.name, Dataset.user_id == user_id)
    if session.scalar(owned) is not None:
        return False
    dataset_service.create_dataset(session, payload, user_id)
    logger.info("seeded demo dataset '%s' for a new account", payload.name)
    return True
