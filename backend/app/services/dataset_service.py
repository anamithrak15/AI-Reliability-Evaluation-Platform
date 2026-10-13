import hashlib
import json
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Dataset, DatasetVersion, TestCase
from app.repositories import dataset_repo
from app.schemas.dataset import (
    CaseBatch,
    CaseOut,
    DatasetCreate,
    DatasetCreated,
    DatasetSummary,
    Page,
    VersionDetail,
    VersionSummary,
)


def compute_content_hash(batch: CaseBatch) -> str:
    """SHA-256 over canonical JSON; independent of case order and dict key order."""
    cases = sorted(
        (c.model_dump(mode="json") for c in batch.cases), key=lambda c: c["case_key"]
    )
    canonical = json.dumps(
        {"schema_version": batch.schema_version, "cases": cases},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _dataset_summary(row) -> DatasetSummary:
    dataset, version_count, latest = row
    return DatasetSummary(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        created_at=dataset.created_at,
        version_count=version_count,
        latest_version_number=latest,
    )


def _version_summary(version: DatasetVersion, case_count: int) -> VersionSummary:
    return VersionSummary(
        id=version.id,
        dataset_id=version.dataset_id,
        version_number=version.version_number,
        schema_version=version.schema_version,
        content_hash=version.content_hash,
        case_count=case_count,
        created_at=version.created_at,
    )


def _insert_version(session: Session, dataset_id: UUID, number: int, batch: CaseBatch):
    version = DatasetVersion(
        dataset_id=dataset_id,
        version_number=number,
        schema_version=batch.schema_version,
        content_hash=compute_content_hash(batch),
    )
    session.add(version)
    session.flush()
    session.add_all(
        TestCase(
            dataset_version_id=version.id,
            case_key=c.case_key,
            input=c.input,
            expected_output=c.expected_output,
            evaluation_config=c.evaluation_config,
            tags=c.tags,
        )
        for c in batch.cases
    )
    session.flush()
    return version


def create_dataset(session: Session, payload: DatasetCreate, user_id: UUID) -> DatasetCreated:
    limit = get_settings().max_datasets_per_user
    if dataset_repo.count_datasets(session, user_id) >= limit:
        raise AppError(
            429, "quota_exceeded", f"Each account can hold at most {limit} datasets"
        )
    dataset = Dataset(name=payload.name, description=payload.description, user_id=user_id)
    session.add(dataset)
    session.flush()
    version = _insert_version(session, dataset.id, 1, payload)
    session.commit()
    return DatasetCreated(
        dataset=_dataset_summary((dataset, 1, 1)),
        version=_version_summary(version, len(payload.cases)),
    )


def _require_dataset(session: Session, dataset_id: UUID, user_id: UUID):
    # Another user's dataset is reported as missing so its existence is not revealed.
    row = dataset_repo.get_dataset_row(session, dataset_id, user_id)
    if row is None:
        raise AppError(404, "dataset_not_found", "Dataset not found")
    return row


def list_datasets(session: Session, user_id: UUID, limit: int, offset: int) -> Page[DatasetSummary]:
    rows, total = dataset_repo.list_datasets(session, user_id, limit, offset)
    return Page(items=[_dataset_summary(r) for r in rows], total=total, limit=limit, offset=offset)


def get_dataset(session: Session, dataset_id: UUID, user_id: UUID) -> DatasetSummary:
    return _dataset_summary(_require_dataset(session, dataset_id, user_id))


def create_version(
    session: Session, dataset_id: UUID, batch: CaseBatch, user_id: UUID
) -> VersionSummary:
    _require_dataset(session, dataset_id, user_id)
    # Row lock serializes concurrent version creation for one dataset.
    if dataset_repo.lock_dataset(session, dataset_id) is None:
        raise AppError(404, "dataset_not_found", "Dataset not found")
    latest = dataset_repo.latest_version(session, dataset_id)
    if latest is not None and latest.content_hash == compute_content_hash(batch):
        session.rollback()
        raise AppError(
            409,
            "duplicate_version",
            f"Content is identical to version {latest.version_number}",
        )
    number = (latest.version_number if latest else 0) + 1
    try:
        version = _insert_version(session, dataset_id, number, batch)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise AppError(409, "version_conflict", "Concurrent version creation, please retry") from None
    return _version_summary(version, len(batch.cases))


def list_versions(session: Session, dataset_id: UUID, user_id: UUID) -> list[VersionSummary]:
    _require_dataset(session, dataset_id, user_id)
    return [_version_summary(v, n) for v, n in dataset_repo.list_versions(session, dataset_id)]


def get_version(
    session: Session, dataset_id: UUID, version_number: int, user_id: UUID
) -> VersionDetail:
    _require_dataset(session, dataset_id, user_id)
    version = dataset_repo.get_version_with_cases(session, dataset_id, version_number)
    if version is None:
        raise AppError(404, "version_not_found", "Dataset version not found")
    cases = sorted(version.test_cases, key=lambda c: c.case_key)
    summary = _version_summary(version, len(cases))
    return VersionDetail(
        **summary.model_dump(), cases=[CaseOut.model_validate(c) for c in cases]
    )
