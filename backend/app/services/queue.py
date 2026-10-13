import logging
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import redis
from rq import Queue

from app.core.config import get_settings

QUEUE_NAME = "evaluations"
logger = logging.getLogger(__name__)

_executor: ThreadPoolExecutor | None = None


def _inline_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=get_settings().inline_worker_threads, thread_name_prefix="inline-run"
        )
    return _executor


def _run_inline(run_id: UUID) -> None:
    # Imported here so the API process only loads the evaluator stack when it is used.
    from app.db.database import SessionLocal
    from app.evaluation.orchestrator import execute_run

    try:
        execute_run(SessionLocal, run_id)
    except Exception:
        logger.exception("inline run crashed", extra={"run_id": str(run_id)})


def enqueue_run(run_id: UUID) -> None:
    settings = get_settings()
    if settings.run_worker_inline:
        _inline_executor().submit(_run_inline, run_id)
        return
    queue = Queue(QUEUE_NAME, connection=redis.Redis.from_url(settings.redis_url))
    queue.enqueue(
        "app.worker.tasks.run_evaluation",
        str(run_id),
        job_id=f"run-{run_id}",
        job_timeout=settings.max_run_seconds + 120,
        result_ttl=3600,
        failure_ttl=86400,
    )
