from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.shared.exceptions import ChurnAppError


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
            },
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Регистрирует единый формат ошибок для Web API.
    Args:
        app: FastAPI-приложение, для которого регистрируются обработчики ошибок.
"""

    @app.exception_handler(ChurnAppError)
    async def churn_app_error_handler(
        request: Request,
        exc: ChurnAppError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=exc.__class__.__name__,
            message=str(exc),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message=str(exc),
        )


    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(
        request: Request,
        exc: FileNotFoundError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=str(exc),
        )


    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        container = getattr(request.app.state, "container", None)

        if container is not None:
            container.logger.exception("Необработанная ошибка Web API: %s", exc)

        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
            message="Внутренняя ошибка API",
        )
