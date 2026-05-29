from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from src.app.bootstrap import bootstrap
from src.infrastructure.execution.dask_client import close_dask_client
from src.infrastructure.execution.pipeline_executor_factory import build_pipeline_executor
from src.infrastructure.pipeline_runs.file_store import FilePipelineRunStore
from src.presentation.web.exception_handlers import register_exception_handlers
from src.presentation.web.routes.config import router as config_router
from src.presentation.web.routes.health import router as health_router
from src.presentation.web.routes.model import router as model_router
from src.presentation.web.routes.profiles import router as profiles_router
from src.presentation.web.routes.pipeline_runs import router as pipeline_runs_router


@asynccontextmanager
async def lifespan(api_app: FastAPI) -> AsyncIterator[None]:
    profile = os.getenv("DCP_PROFILE", "pandas")

    container = bootstrap(profile=profile, init_dask_client=False)
    api_app.state.container = container
    
    run_store = FilePipelineRunStore(
        root_dir=container.settings.logs_dir / "pipeline_runs",
    )
    pipeline_executor = build_pipeline_executor(
        container=container,
        store=run_store,
    )

    api_app.state.pipeline_run_store = run_store
    api_app.state.pipeline_executor = pipeline_executor

    container.logger.info(
        "Web API запущен: profile=%s mode=%s executor=%s",
        profile,
        container.settings.runtime.mode.value,
        container.settings.api.pipeline_executor.value,
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
        version="0.4.0",
        lifespan=lifespan,
    )

    register_exception_handlers(api_app)

    api_app.include_router(health_router)
    api_app.include_router(profiles_router)
    api_app.include_router(config_router)
    api_app.include_router(model_router)
    api_app.include_router(pipeline_runs_router)
    return api_app


app = create_app()