import json
import logging
from pathlib import Path

from sqlalchemy import select

from app.db.database import SessionLocal
from app.models import Dataset
from app.schemas.dataset import DatasetCreate
from app.services import dataset_service

logger = logging.getLogger(__name__)


def seed_demo_dataset(path: str) -> bool:
    """Idempotent by dataset name. Returns True if a dataset was created."""
    payload = DatasetCreate.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
    with SessionLocal() as session:
        if session.scalar(select(Dataset.id).where(Dataset.name == payload.name)) is not None:
            return False
        dataset_service.create_dataset(session, payload)
    logger.info("seeded demo dataset '%s'", payload.name)
    return True
