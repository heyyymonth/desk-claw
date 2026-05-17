from fastapi import Request
from fastapi.responses import JSONResponse


class ServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 503, ai_trace: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.ai_trace = ai_trace or {}
        super().__init__(message)


async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
    content = {"error": {"code": exc.code, "message": exc.message}}
    if exc.ai_trace:
        content["error"]["details"] = exc.ai_trace
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
    )
