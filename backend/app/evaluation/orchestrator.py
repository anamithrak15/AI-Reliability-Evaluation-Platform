import logging
import time
from collections import defaultdict, deque
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import redact
from app.evaluation.errors import LLMError, LLMTimeout
from app.evaluation.evaluators import Metric, evaluate
from app.evaluation.llm_adapter import call_model
from app.models import CaseMetric, CaseResult, EvaluationRun, TestCase
from app.models.entities import utcnow
from app.repositories import run_repo
from app.services import comparison_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Outcome:
    status: str
    output: Any = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: Any = None
    error_code: str | None = None
    error_message: str | None = None
    attempts: int = 1


def call_with_retries(
    alias: str, case_key: str, messages: list[dict[str, Any]], max_retries: int, backoff: float
) -> Outcome:
    """Retries only transient errors, at most max_retries extra attempts. Never raises."""
    attempt = 0
    while True:
        attempt += 1
        try:
            r = call_model(alias, case_key, messages, attempt)
            return Outcome(
                "success", r.content, r.latency_ms, r.input_tokens, r.output_tokens,
                r.estimated_cost_usd, attempts=attempt,
            )
        except LLMError as exc:
            if exc.transient and attempt <= max_retries:
                time.sleep(backoff * 2 ** (attempt - 1))
                continue
            status = "timeout" if isinstance(exc, LLMTimeout) else "provider_error"
            return Outcome(
                status, latency_ms=exc.latency_ms, error_code=exc.code,
                error_message=redact(str(exc)), attempts=attempt,
            )
        except Exception as exc:  # adapter bug or bad config: do not retry blindly
            return Outcome(
                "provider_error", error_code="adapter_error",
                error_message=redact(f"{type(exc).__name__}: {exc}"), attempts=attempt,
            )


def _score(case: TestCase | None, o: Outcome) -> list[Metric]:
    if case is None or o.status != "success":
        return []
    try:
        return evaluate(case.evaluation_config, case.expected_output, o.output)
    except Exception as exc:  # a bad evaluator must not lose the model result
        logger.exception("evaluator failed", extra={"case_key": case.case_key})
        return [Metric("quality", None, {"reason": redact(f"{type(exc).__name__}: {exc}")})]


def _persist(
    session: Session, run_id: UUID, test_case_id: UUID, alias: str, o: Outcome,
    case: TestCase | None = None,
) -> None:
    # ON CONFLICT DO NOTHING keeps duplicate job delivery from creating duplicate rows.
    result_id = session.scalar(
        pg_insert(CaseResult)
        .values(
            run_id=run_id, test_case_id=test_case_id, model_alias=alias, status=o.status,
            output=o.output, latency_ms=o.latency_ms, input_tokens=o.input_tokens,
            output_tokens=o.output_tokens, estimated_cost_usd=o.estimated_cost_usd,
            error_code=o.error_code, error_message_redacted=o.error_message,
            attempt_count=o.attempts,
        )
        .on_conflict_do_nothing(index_elements=["run_id", "test_case_id", "model_alias"])
        .returning(CaseResult.id)
    )
    metrics = _score(case, o) if result_id else []
    if metrics:
        session.execute(
            pg_insert(CaseMetric)
            .values([
                {"case_result_id": result_id, "metric_name": m.name,
                 "metric_value": m.value, "metric_details": m.details}
                for m in metrics
            ])
            .on_conflict_do_nothing(index_elements=["case_result_id", "metric_name"])
        )
    session.commit()


def _claim(session: Session, run_id: UUID, stale_seconds: int) -> bool:
    now = utcnow()
    if run_repo.transition(session, run_id, {"queued"}, "running", started_at=now):
        return True
    run = run_repo.get_run(session, run_id)
    if run and run.status == "running" and run.started_at:
        # A running run whose worker died is resumed; finished pairs are skipped.
        if now - run.started_at > timedelta(seconds=stale_seconds):
            return run_repo.take_over_stale(session, run_id, run.started_at, now)
    return False


def _stop_reason(session: Session, run_id: UUID, deadline: float) -> str | None:
    if session.scalar(select(EvaluationRun.status).where(EvaluationRun.id == run_id)) != "running":
        return "cancelled"
    if time.monotonic() >= deadline:
        return "run_timeout"
    return None


def _finalize(session: Session, run_id: UUID) -> None:
    counts = dict(
        session.execute(
            select(CaseResult.status, func.count())
            .where(CaseResult.run_id == run_id)
            .group_by(CaseResult.status)
        ).all()
    )
    total, ok = sum(counts.values()), counts.get("success", 0)
    final = "failed" if ok == 0 else "completed" if ok == total else "completed_with_errors"
    problems = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()) if k != "success")
    run_repo.transition(
        session, run_id, {"running"}, final,
        completed_at=utcnow(), error_summary=problems or ("no_work" if total == 0 else None),
    )
    # Derived data must never change the run outcome.
    try:
        session.expire_all()
        run = run_repo.get_run(session, run_id)
        comparison_service.store_summaries(session, run)
        if run.baseline_run_id:
            comparison_service.refresh_regressions(session, run)
    except Exception:
        session.rollback()
        logger.exception("summary/regression computation failed", extra={"run_id": str(run_id)})


def _process(session: Session, run_id: UUID, settings: Settings) -> None:
    run = run_repo.get_run(session, run_id)
    cfg = run.config_snapshot
    models: list[str] = cfg["model_aliases"]
    concurrency: int = cfg["max_concurrency"]

    cases = session.scalars(
        select(TestCase)
        .where(TestCase.dataset_version_id == run.dataset_version_id)
        .order_by(TestCase.case_key)
        .limit(cfg["max_cases"])
    ).all()
    done = {
        (r[0], r[1])
        for r in session.execute(
            select(CaseResult.test_case_id, CaseResult.model_alias).where(CaseResult.run_id == run_id)
        )
    }
    pending = deque((c, m) for c in cases for m in models if (c.id, m) not in done)

    deadline = time.monotonic() + settings.max_run_seconds
    spent: dict[str, Decimal] = defaultdict(Decimal)
    for alias, cost in session.execute(
        select(CaseResult.model_alias, func.coalesce(func.sum(CaseResult.estimated_cost_usd), 0))
        .where(CaseResult.run_id == run_id)
        .group_by(CaseResult.model_alias)
    ):
        spent[alias] = Decimal(cost)
    stop = _stop_reason(session, run_id, deadline)
    in_flight: dict[Future, tuple[TestCase, str]] = {}

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        while pending or in_flight:
            while pending and not stop and len(in_flight) < concurrency:
                case, alias = pending.popleft()
                budget = settings.live_budget_overrides.get(alias, settings.live_budget_usd_per_model)
                if budget > 0 and spent[alias] >= Decimal(str(budget)):
                    _persist(
                        session, run_id, case.id, alias,
                        Outcome(
                            "skipped", error_code="budget_exceeded", attempts=0,
                            error_message=f"model budget of ${budget} reached",
                        ),
                    )
                    continue
                fut = pool.submit(
                    call_with_retries, alias, case.case_key, case.input["messages"],
                    settings.max_retries, settings.retry_backoff_seconds,
                )
                in_flight[fut] = (case, alias)
            if not in_flight:
                break
            finished, _ = wait(in_flight, timeout=1.0, return_when=FIRST_COMPLETED)
            for fut in finished:
                case, alias = in_flight.pop(fut)
                outcome = fut.result()
                if outcome.estimated_cost_usd is not None:
                    spent[alias] += Decimal(outcome.estimated_cost_usd)
                _persist(session, run_id, case.id, alias, outcome, case)
            stop = stop or _stop_reason(session, run_id, deadline)

    for case, alias in pending:
        _persist(
            session, run_id, case.id, alias,
            Outcome("skipped", error_code=stop, error_message=f"not executed: {stop}", attempts=0),
        )
    if stop != "cancelled":
        _finalize(session, run_id)


def execute_run(session_factory: sessionmaker, run_id: UUID) -> None:
    settings = get_settings()
    extra = {"run_id": str(run_id)}
    with session_factory() as session:
        if not _claim(session, run_id, settings.stale_run_seconds):
            logger.info("run not claimable; skipping", extra=extra)
            return
        logger.info("run started", extra=extra)
        try:
            _process(session, run_id, settings)
        except Exception as exc:
            logger.exception("run crashed", extra=extra)
            session.rollback()
            run_repo.transition(
                session, run_id, {"running"}, "failed",
                completed_at=utcnow(),
                error_summary=redact(f"{type(exc).__name__}: {exc}"),
            )
        else:
            logger.info("run finished", extra=extra)
