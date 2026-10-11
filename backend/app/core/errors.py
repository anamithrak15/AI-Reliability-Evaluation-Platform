from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_STATUS_CODES = {404: "not_found", 405: "method_not_allowed", 429: "rate_limited"}


class AppError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: list[dict[str, Any]] | None = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    return body


def _validation_details(exc: RequestValidationError) -> list[dict[str, str]]:
    details = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"] if p != "body")
        message = str(err["msg"]).removeprefix("Value error, ")
        details.append({"loc": loc, "message": message})
    return details


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details)
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Details deliberately omit the offending input to avoid echoing prompt content.
        return JSONResponse(
            status_code=400,
            content=error_body("validation_error", "Request validation failed", _validation_details(exc)),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        return JSONResponse(status_code=exc.status_code, content=error_body(code, str(exc.detail)))
