from __future__ import annotations

from fastapi import APIRouter

from src.application.use_cases.list_profiles import list_profiles
from src.presentation.api.schemas import ProfilesApiResponse

router = APIRouter(tags=["profiles"])


@router.get(
    "/profiles",
    response_model=ProfilesApiResponse,
    summary="Получить список runtime-профилей",
)
def profiles() -> dict:
    response = list_profiles()
    return response.to_dict()