from __future__ import annotations

from fastapi import APIRouter, Depends

from src.app.container import AppContainer
from src.application.use_cases.get_model_info import get_model_info
from src.presentation.web.dependencies import get_container
from src.presentation.web.schemas import ModelInfoApiResponse

router = APIRouter(prefix="/model", tags=["model"])


@router.get(
    "/info",
    response_model=ModelInfoApiResponse,
    summary="Получить информацию о модели",
)
def model_info(
    container: AppContainer = Depends(get_container),
) -> dict:
    profile = container.settings.runtime.mode.value
    response = get_model_info(container, profile=profile)
    return response.to_dict()