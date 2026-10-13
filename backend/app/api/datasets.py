from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db.database import get_session
from app.models import User
from app.schemas.dataset import (
    DatasetCreate,
    DatasetCreated,
    DatasetSummary,
    Page,
    VersionCreate,
    VersionDetail,
    VersionSummary,
)
from app.services import dataset_service

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


@router.post("", status_code=201)
def create_dataset(
    payload: DatasetCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> DatasetCreated:
    return dataset_service.create_dataset(session, payload, user.id)


@router.get("")
def list_datasets(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Page[DatasetSummary]:
    return dataset_service.list_datasets(session, user.id, limit, offset)


@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> DatasetSummary:
    return dataset_service.get_dataset(session, dataset_id, user.id)


@router.post("/{dataset_id}/versions", status_code=201)
def create_version(
    dataset_id: UUID,
    payload: VersionCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> VersionSummary:
    return dataset_service.create_version(session, dataset_id, payload, user.id)


@router.get("/{dataset_id}/versions")
def list_versions(
    dataset_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[VersionSummary]:
    return dataset_service.list_versions(session, dataset_id, user.id)


@router.get("/{dataset_id}/versions/{version_number}")
def get_version(
    dataset_id: UUID,
    version_number: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> VersionDetail:
    return dataset_service.get_version(session, dataset_id, version_number, user.id)
