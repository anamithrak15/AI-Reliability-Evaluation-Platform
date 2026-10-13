from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Dataset, DatasetVersion, TestCase


def _summary_query():
    return (
        select(Dataset, func.count(DatasetVersion.id), func.max(DatasetVersion.version_number))
        .outerjoin(DatasetVersion, DatasetVersion.dataset_id == Dataset.id)
        .group_by(Dataset.id)
    )


def list_datasets(session: Session, user_id: UUID, limit: int, offset: int):
    rows = session.execute(
        _summary_query()
        .where(Dataset.user_id == user_id)
        .order_by(Dataset.created_at.desc(), Dataset.id)
        .limit(limit)
        .offset(offset)
    ).all()
    total = count_datasets(session, user_id)
    return rows, total


def count_datasets(session: Session, user_id: UUID) -> int:
    return (
        session.scalar(select(func.count()).select_from(Dataset).where(Dataset.user_id == user_id))
        or 0
    )


def get_dataset_row(session: Session, dataset_id: UUID, user_id: UUID):
    return session.execute(
        _summary_query().where(Dataset.id == dataset_id, Dataset.user_id == user_id)
    ).one_or_none()


def lock_dataset(session: Session, dataset_id: UUID) -> Dataset | None:
    return session.scalar(select(Dataset).where(Dataset.id == dataset_id).with_for_update())


def latest_version(session: Session, dataset_id: UUID) -> DatasetVersion | None:
    return session.scalar(
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_number.desc())
        .limit(1)
    )


def list_versions(session: Session, dataset_id: UUID):
    return session.execute(
        select(DatasetVersion, func.count(TestCase.id))
        .outerjoin(TestCase, TestCase.dataset_version_id == DatasetVersion.id)
        .where(DatasetVersion.dataset_id == dataset_id)
        .group_by(DatasetVersion.id)
        .order_by(DatasetVersion.version_number.desc())
    ).all()


def get_version_with_cases(
    session: Session, dataset_id: UUID, version_number: int
) -> DatasetVersion | None:
    return session.scalar(
        select(DatasetVersion)
        .where(
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.version_number == version_number,
        )
        .options(selectinload(DatasetVersion.test_cases))
    )
