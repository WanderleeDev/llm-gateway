from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas import ErrorBody, ErrorResponse


class APIError(Exception):
    """Error returned to the client in OpenAI's {"error": {...}} format."""

    def __init__(
        self,
        status_code: int,
        message: str,
        error_type: str = "api_error",
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_type = error_type
        self.code = code


def error_response(
    status_code: int,
    message: str,
    error_type: str,
    code: str | None = None,
    param: str | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(message=message, type=error_type, param=param, code=code)
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def handle_api_error(_: Request, exc: APIError) -> JSONResponse:
        return error_response(exc.status_code, exc.message, exc.error_type, exc.code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"] if part != "body")
        message = f"{location}: {first['msg']}" if location else first["msg"]
        return error_response(400, message, "invalid_request_error", "invalid_request")

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        error_type = "invalid_request_error" if exc.status_code < 500 else "api_error"
        return error_response(exc.status_code, str(exc.detail), error_type)
