from __future__ import annotations

from fastapi import APIRouter, Depends

from src.app.container import AppContainer
from src.application.use_cases.get_health import get_health
from src.presentation.api.dependencies import get_container
from src.presentation.api.schemas import HealthApiResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthApiResponse,
    summary="Проверить состояние приложения",
)
def health(
    container: AppContainer = Depends(get_container),
) -> dict:
    response = get_health(container)
    return response.to_dict()