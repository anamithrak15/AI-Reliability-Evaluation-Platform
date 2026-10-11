from uuid import UUID

import redis
from rq import Queue

from app.core.config import get_settings

QUEUE_NAME = "evaluations"


def enqueue_run(run_id: UUID) -> None:
    settings = get_settings()
    queue = Queue(QUEUE_NAME, connection=redis.Redis.from_url(settings.redis_url))
    queue.enqueue(
        "app.worker.tasks.run_evaluation",
        str(run_id),
        job_id=f"run-{run_id}",
        job_timeout=settings.max_run_seconds + 120,
        result_ttl=3600,
        failure_ttl=86400,
    )
