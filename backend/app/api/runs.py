from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.schemas.comparison import BaselineSet, ComparisonOut, RegressionsOut, ReportOut
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


@router.post("/{run_id}/baseline")
def set_baseline(
    run_id: UUID, payload: BaselineSet, session: Session = Depends(get_session)
) -> RunOut:
    return run_service.set_baseline(session, run_id, payload.baseline_run_id)


@router.get("/{run_id}/comparison")
def get_comparison(run_id: UUID, session: Session = Depends(get_session)) -> ComparisonOut:
    return run_service.get_comparison(session, run_id)


@router.get("/{run_id}/regressions")
def get_regressions(run_id: UUID, session: Session = Depends(get_session)) -> RegressionsOut:
    return run_service.get_regressions(session, run_id)


@router.get("/{run_id}/report")
def get_report(run_id: UUID, session: Session = Depends(get_session)) -> ReportOut:
    return run_service.get_report(session, run_id)


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
