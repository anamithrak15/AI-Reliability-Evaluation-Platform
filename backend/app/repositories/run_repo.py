from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import CaseMetric, CaseResult, EvaluationRun, TestCase
from app.services.run_state import ACTIVE_STATES, assert_transition


def get_run(session: Session, run_id: UUID) -> EvaluationRun | None:
    return session.get(EvaluationRun, run_id)


def get_by_idempotency_key(session: Session, key: str) -> EvaluationRun | None:
    return session.scalar(select(EvaluationRun).where(EvaluationRun.idempotency_key == key))


def count_active(session: Session) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(EvaluationRun).where(
                EvaluationRun.status.in_(ACTIVE_STATES)
            )
        )
        or 0
    )


def count_cases(session: Session, dataset_version_id: UUID) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(TestCase).where(
                TestCase.dataset_version_id == dataset_version_id
            )
        )
        or 0
    )


def status_counts(session: Session, run_ids: list[UUID]) -> dict[UUID, dict[str, int]]:
    result: dict[UUID, dict[str, int]] = {rid: {} for rid in run_ids}
    if not run_ids:
        return result
    rows = session.execute(
        select(CaseResult.run_id, CaseResult.status, func.count())
        .where(CaseResult.run_id.in_(run_ids))
        .group_by(CaseResult.run_id, CaseResult.status)
    ).all()
    for run_id, status, n in rows:
        result[run_id][status] = n
    return result


def list_runs(session: Session, status: str | None, limit: int, offset: int):
    base = select(EvaluationRun)
    count = select(func.count()).select_from(EvaluationRun)
    if status:
        base = base.where(EvaluationRun.status == status)
        count = count.where(EvaluationRun.status == status)
    runs = session.scalars(
        base.order_by(EvaluationRun.created_at.desc(), EvaluationRun.id).limit(limit).offset(offset)
    ).all()
    return runs, session.scalar(count) or 0


def transition(
    session: Session, run_id: UUID, from_states: set[str], to: str, **values: object
) -> bool:
    """Atomic compare-and-set on status; False if the run was not in an expected state."""
    for state in from_states:
        assert_transition(state, to)
    result = session.execute(
        update(EvaluationRun)
        .where(EvaluationRun.id == run_id, EvaluationRun.status.in_(from_states))
        .values(status=to, **values)
    )
    session.commit()
    return result.rowcount == 1


def take_over_stale(session: Session, run_id: UUID, stale_started_at: datetime, now: datetime) -> bool:
    result = session.execute(
        update(EvaluationRun)
        .where(
            EvaluationRun.id == run_id,
            EvaluationRun.status == "running",
            EvaluationRun.started_at == stale_started_at,
        )
        .values(started_at=now)
    )
    session.commit()
    return result.rowcount == 1


def list_results(
    session: Session, run_id: UUID, model_alias: str | None, status: str | None, limit: int, offset: int
):
    filters = [CaseResult.run_id == run_id]
    if model_alias:
        filters.append(CaseResult.model_alias == model_alias)
    if status:
        filters.append(CaseResult.status == status)
    rows = session.execute(
        select(CaseResult, TestCase.case_key)
        .join(TestCase, TestCase.id == CaseResult.test_case_id)
        .where(*filters)
        .order_by(TestCase.case_key, CaseResult.model_alias)
        .limit(limit)
        .offset(offset)
    ).all()
    total = session.scalar(select(func.count()).select_from(CaseResult).where(*filters)) or 0
    return rows, total


def results_with_metrics(session: Session, run_id: UUID) -> list[tuple[CaseResult, dict[str, Decimal | None]]]:
    results = session.scalars(select(CaseResult).where(CaseResult.run_id == run_id)).all()
    metrics = metrics_for(session, [r.id for r in results])
    return [(r, metrics[r.id]) for r in results]


def metrics_for(session: Session, result_ids: list[UUID]) -> dict[UUID, dict[str, Decimal | None]]:
    out: dict[UUID, dict[str, Decimal | None]] = {rid: {} for rid in result_ids}
    if result_ids:
        for rid, name, value in session.execute(
            select(CaseMetric.case_result_id, CaseMetric.metric_name, CaseMetric.metric_value)
            .where(CaseMetric.case_result_id.in_(result_ids))
        ):
            out[rid][name] = value
    return out
