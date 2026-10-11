import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.evaluation import registry
from app.models import Dataset, DatasetVersion, EvaluationRun
from app.models.entities import utcnow
from app.repositories import run_repo
from app.schemas.dataset import Page
from app.schemas.run import CaseResultOut, Progress, RunCreate, RunOut
from app.services.queue import enqueue_run

logger = logging.getLogger(__name__)


def _run_out(run: EvaluationRun, counts: dict[str, int]) -> RunOut:
    return RunOut(
        id=run.id,
        dataset_version_id=run.dataset_version_id,
        status=run.status,
        baseline_run_id=run.baseline_run_id,
        config=run.config_snapshot,
        progress=Progress(
            total_pairs=run.config_snapshot.get("total_pairs", 0),
            completed_pairs=sum(counts.values()),
            by_status=counts,
        ),
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_summary=run.error_summary,
    )


def _require_run(session: Session, run_id: UUID) -> EvaluationRun:
    run = run_repo.get_run(session, run_id)
    if run is None:
        raise AppError(404, "run_not_found", "Run not found")
    return run


def get_run(session: Session, run_id: UUID) -> RunOut:
    run = _require_run(session, run_id)
    return _run_out(run, run_repo.status_counts(session, [run.id])[run.id])


def list_runs(session: Session, status: str | None, limit: int, offset: int) -> Page[RunOut]:
    runs, total = run_repo.list_runs(session, status, limit, offset)
    counts = run_repo.status_counts(session, [r.id for r in runs])
    return Page(items=[_run_out(r, counts[r.id]) for r in runs], total=total, limit=limit, offset=offset)


def create_run(session: Session, payload: RunCreate, idempotency_key: str | None) -> RunOut:
    settings = get_settings()
    if idempotency_key:
        existing = run_repo.get_by_idempotency_key(session, idempotency_key)
        if existing:
            return get_run(session, existing.id)

    version = session.get(DatasetVersion, payload.dataset_version_id)
    if version is None:
        raise AppError(404, "dataset_version_not_found", "Dataset version not found")
    unknown = [a for a in payload.model_aliases if not registry.is_allowed_model(a)]
    if unknown:
        raise AppError(
            400, "unknown_model", "Model alias is not in the allowlist",
            [{"loc": "model_aliases", "message": f"unknown: {', '.join(unknown)}"}],
        )
    if payload.evaluation_profile not in registry.EVALUATION_PROFILES:
        raise AppError(400, "unknown_evaluation_profile", "Unknown evaluation profile")
    if payload.baseline_run_id and run_repo.get_run(session, payload.baseline_run_id) is None:
        raise AppError(404, "baseline_run_not_found", "Baseline run not found")
    if run_repo.count_active(session) >= settings.max_active_runs:
        raise AppError(429, "too_many_active_runs", "Too many runs are queued or running; try later")

    # Server-side hard limits win over whatever the client asked for.
    concurrency = min(payload.max_concurrency, settings.max_concurrency_limit)
    max_cases = min(payload.max_cases, settings.max_cases_per_dataset)
    case_count = min(run_repo.count_cases(session, version.id), max_cases)
    dataset = session.get(Dataset, version.dataset_id)

    run = EvaluationRun(
        dataset_version_id=version.id,
        status="queued",
        baseline_run_id=payload.baseline_run_id,
        idempotency_key=idempotency_key,
        config_snapshot={
            "dataset_id": str(version.dataset_id),
            "dataset_name": dataset.name,
            "dataset_version_number": version.version_number,
            "content_hash": version.content_hash,
            "model_aliases": payload.model_aliases,
            "evaluation_profile": payload.evaluation_profile,
            "requested": {"max_concurrency": payload.max_concurrency, "max_cases": payload.max_cases},
            "max_concurrency": concurrency,
            "max_cases": max_cases,
            "max_retries": settings.max_retries,
            "total_pairs": case_count * len(payload.model_aliases),
            "demo_mode": settings.demo_mode,
        },
    )
    session.add(run)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = run_repo.get_by_idempotency_key(session, idempotency_key) if idempotency_key else None
        if existing:
            return get_run(session, existing.id)
        raise

    try:
        enqueue_run(run.id)
    except Exception:
        logger.exception("failed to enqueue run", extra={"run_id": str(run.id)})
        # The run never started, so remove it rather than invent an invalid transition.
        session.delete(run)
        session.commit()
        raise AppError(503, "queue_unavailable", "Job queue is unavailable; run was not started") from None
    return get_run(session, run.id)


def cancel_run(session: Session, run_id: UUID) -> RunOut:
    _require_run(session, run_id)
    if not run_repo.transition(
        session, run_id, {"queued", "running"}, "cancelled", completed_at=utcnow()
    ):
        raise AppError(409, "run_not_cancellable", "Run is already finished")
    session.expire_all()
    return get_run(session, run_id)


def list_results(
    session: Session, run_id: UUID, model_alias: str | None, status: str | None, limit: int, offset: int
) -> Page[CaseResultOut]:
    _require_run(session, run_id)
    rows, total = run_repo.list_results(session, run_id, model_alias, status, limit, offset)
    items = [
        CaseResultOut(
            id=r.id, test_case_id=r.test_case_id, case_key=case_key,
            model_alias=r.model_alias, status=r.status, output=r.output,
            latency_ms=r.latency_ms, input_tokens=r.input_tokens,
            output_tokens=r.output_tokens, estimated_cost_usd=r.estimated_cost_usd,
            error_code=r.error_code, error_message_redacted=r.error_message_redacted,
            attempt_count=r.attempt_count, created_at=r.created_at,
        )
        for r, case_key in rows
    ]
    return Page(items=items, total=total, limit=limit, offset=offset)
