from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.schemas.dataset import Page
from app.schemas.run import CaseResultOut, RunCreate, RunOut
from app.services import run_service

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])

RunStatus = Literal["queued", "running", "completed", "completed_with_errors", "failed", "cancelled"]
ResultStatus = Literal["success", "provider_error", "timeout", "invalid_output", "skipped"]


@router.post("", status_code=202)
def create_run(
    payload: RunCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=100),
    session: Session = Depends(get_session),
) -> RunOut:
    return run_service.create_run(session, payload, idempotency_key)


@router.get("")
def list_runs(
    status: RunStatus | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> Page[RunOut]:
    return run_service.list_runs(session, status, limit, offset)


@router.get("/{run_id}")
def get_run(run_id: UUID, session: Session = Depends(get_session)) -> RunOut:
    return run_service.get_run(session, run_id)


@router.post("/{run_id}/cancel")
def cancel_run(run_id: UUID, session: Session = Depends(get_session)) -> RunOut:
    return run_service.cancel_run(session, run_id)


@router.get("/{run_id}/results")
def list_results(
    run_id: UUID,
    model_alias: str | None = Query(None, max_length=100),
    status: ResultStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> Page[CaseResultOut]:
    return run_service.list_results(session, run_id, model_alias, status, limit, offset)
