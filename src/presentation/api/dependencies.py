from __future__ import annotations

from fastapi import Request

from src.app.container import AppContainer


def get_container(request: Request) -> AppContainer:
    """Возвращает AppContainer, созданный на старте FastAPI-приложения."""

    container = getattr(request.app.state, "container", None)

    if container is None:
        raise RuntimeError("AppContainer не инициализирован")

    return container


def get_pipeline_executor(request: Request):
    """Возвращает executor для асинхронных pipeline runs."""

    executor = getattr(request.app.state, "pipeline_executor", None)

    if executor is None:
        raise RuntimeError("Pipeline executor не инициализирован")

    return executor
