from __future__ import annotations

from fastapi import FastAPI

from src.presentation.api.routes.health import router as health_router
from src.presentation.api.routes.pipeline import router as pipeline_router


def create_app() -> FastAPI:
    """Создаёт FastAPI-приложение для HTTP-интерфейса проекта."""
    api_app = FastAPI(
        title="Distributed Churn Prediction API",
        description=(
            "HTTP-адаптер над application layer проекта "
            "distributed-churn-prediction."
        ),
        version="0.1.0",
    )

    api_app.include_router(health_router)
    api_app.include_router(pipeline_router)

    return api_app


app = create_app()