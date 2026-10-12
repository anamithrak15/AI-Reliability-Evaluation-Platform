import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.api import catalog, datasets, health, runs
from app.core.config import get_settings
from app.core.errors import error_body, register_error_handlers
from app.core.logging import configure_logging
from app.core.rate_limit import get_limiter
from app.core.request_context import request_id_var
from app.db.seed import seed_demo_dataset

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

# Client-supplied IDs are only echoed when they are short and plain, which keeps logs injection-safe.
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_QUIET_PATHS = {"/health", "/ready"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.demo_mode:
        try:
            seed_demo_dataset(settings.demo_dataset_path)
        except Exception:
            logger.exception("demo dataset seeding failed")
    yield


app = FastAPI(title="AI Reliability & Evaluation Platform", version="0.1.0", lifespan=lifespan)
register_error_handlers(app)


def _retry_after_if_limited(request: Request) -> int | None:
    path = request.url.path
    if not settings.rate_limit_enabled or not path.startswith("/api/"):
        return None
    client = request.client.host if request.client else "unknown"
    limiter = get_limiter()
    checks = [("api", settings.rate_limit_per_window)]
    if request.method == "POST" and path == "/api/v1/runs":
        checks.append(("run_create", settings.rate_limit_run_creates_per_window))
    for bucket, limit in checks:
        allowed, retry_after = limiter.check(bucket, client, limit)
        if not allowed:
            return retry_after
    return None


async def _early_rejection(request: Request) -> JSONResponse | None:
    retry_after = await run_in_threadpool(_retry_after_if_limited, request)
    if retry_after is not None:
        return JSONResponse(
            status_code=429,
            content=error_body("rate_limited", "Too many requests; slow down and retry shortly"),
            headers={"Retry-After": str(retry_after)},
        )
    # Chunked uploads carry no declared size, so the size cap below could not apply to them.
    if "chunked" in request.headers.get("transfer-encoding", "").lower():
        return JSONResponse(
            status_code=411,
            content=error_body("length_required", "Content-Length is required"),
        )
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.max_request_bytes:
        return JSONResponse(
            status_code=413,
            content=error_body("payload_too_large", "Request body is too large"),
        )
    return None


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    supplied = request.headers.get("x-request-id", "")
    request_id = supplied if _REQUEST_ID.match(supplied) else str(uuid.uuid4())
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    status = 500
    try:
        response = await _early_rejection(request) or await call_next(request)
        status = response.status_code
        response.headers["x-request-id"] = request_id
        response.headers["x-content-type-options"] = "nosniff"
        return response
    finally:
        level = logging.DEBUG if request.url.path in _QUIET_PATHS else logging.INFO
        logger.log(
            level,
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        request_id_var.reset(token)


# Added last so CORS is outermost and error responses (413/429) still carry CORS headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["x-request-id", "retry-after"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": "internal_error", "message": "Internal server error"},
    )


app.include_router(health.router)
app.include_router(datasets.router)
app.include_router(runs.router)
app.include_router(catalog.router)
