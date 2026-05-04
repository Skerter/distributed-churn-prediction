from __future__ import annotations

from fastapi import APIRouter, Depends

from src.app.container import AppContainer
from src.application.use_cases.get_config_summary import get_config_summary
from src.presentation.api.dependencies import get_container
from src.presentation.api.schemas import ConfigSummaryApiResponse

router = APIRouter(prefix="/config", tags=["config"])


@router.get(
    "/summary",
    response_model=ConfigSummaryApiResponse,
    summary="Получить безопасную сводку конфигурации",
)
def config_summary(
    container: AppContainer = Depends(get_container),
) -> dict:
    response = get_config_summary(container)
    return response.to_dict()