from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from src.app.bootstrap import bootstrap
from src.infrastructure.execution.dask_client import close_dask_client
from src.presentation.api.exception_handlers import register_exception_handlers
from src.presentation.api.routes.config import router as config_router
from src.presentation.api.routes.health import router as health_router
from src.presentation.api.routes.model import router as model_router
from src.presentation.api.routes.pipeline import router as pipeline_router
from src.presentation.api.routes.profiles import router as profiles_router


@asynccontextmanager
async def lifespan(api_app: FastAPI) -> AsyncIterator[None]:
    profile = os.getenv("DCP_PROFILE", "pandas")

    container = bootstrap(profile=profile)
    api_app.state.container = container

    container.logger.info(
        "Web API запущен: profile=%s mode=%s",
        profile,
        container.settings.runtime.mode.value,
    )

    try:
        yield
    finally:
        close_dask_client(container.dask_client, container.logger)
        container.logger.info("Web API остановлен")


def create_app() -> FastAPI:
    """Создаёт FastAPI-приложение для HTTP-интерфейса проекта."""

    api_app = FastAPI(
        title="Distributed Churn Prediction API",
        description=(
            "HTTP-адаптер над application layer проекта "
            "distributed-churn-prediction."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    register_exception_handlers(api_app)

    api_app.include_router(health_router)
    api_app.include_router(profiles_router)
    api_app.include_router(config_router)
    api_app.include_router(model_router)
    api_app.include_router(pipeline_router)

    return api_app


app = create_app()