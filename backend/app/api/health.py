import logging

import redis
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.db.database import engine

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> JSONResponse:
    checks: dict[str, str] = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.exception("database readiness check failed")
        checks["database"] = "unavailable"
    try:
        redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=2).ping()
        checks["redis"] = "ok"
    except Exception:
        logger.exception("redis readiness check failed")
        checks["redis"] = "unavailable"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
    )
