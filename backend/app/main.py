import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import datasets, health
from app.core.config import get_settings
from app.core.errors import error_body, register_error_handlers
from app.core.logging import configure_logging
from app.db.seed import seed_demo_dataset

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.max_request_bytes:
        return JSONResponse(
            status_code=413,
            content=error_body("payload_too_large", "Request body is too large"),
        )
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": "internal_error", "message": "Internal server error"},
    )


app.include_router(health.router)
app.include_router(datasets.router)
