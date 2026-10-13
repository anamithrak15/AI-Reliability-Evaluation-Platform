import logging
from datetime import timedelta

from sqlalchemy import select, update

from app.core.config import get_settings
from app.db.database import SessionLocal
from app.models import EvaluationRun
from app.models.entities import utcnow
from app.services.queue import enqueue_run

logger = logging.getLogger(__name__)


def resume_incomplete_runs() -> int:
    """Restart runs that were queued or in flight when an inline-worker process stopped.

    Only valid for a single API instance: any run still marked running belonged to the
    process that just died, so it is made immediately claimable and handed back out.
    """
    stale_before = utcnow() - timedelta(seconds=get_settings().stale_run_seconds + 1)
    with SessionLocal() as session:
        ids = list(
            session.scalars(
                select(EvaluationRun.id).where(EvaluationRun.status.in_(["queued", "running"]))
            )
        )
        if ids:
            session.execute(
                update(EvaluationRun)
                .where(EvaluationRun.id.in_(ids), EvaluationRun.status == "running")
                .values(started_at=stale_before)
            )
            session.commit()
    for run_id in ids:
        enqueue_run(run_id)
    if ids:
        logger.info("resumed %d incomplete runs", len(ids))
    return len(ids)
