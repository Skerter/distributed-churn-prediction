from __future__ import annotations

from fastapi import APIRouter, Depends

from src.app.container import AppContainer
from src.application.dto.requests import RunPipelineRequest
from src.application.use_cases.run_pipeline import run_pipeline
from src.presentation.api.dependencies import get_container
from src.presentation.api.schemas import (
    RunPipelineApiRequest,
    RunPipelineApiResponse,
)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post(
    "/run",
    response_model=RunPipelineApiResponse,
    summary="Запустить ML pipeline",
)
def run_pipeline_endpoint(
    request: RunPipelineApiRequest,
    container: AppContainer = Depends(get_container),
) -> dict:
    profile = container.settings.runtime.mode.value

    use_case_request = RunPipelineRequest(
        profile=profile,
        execute=request.execute,
        skip_load=request.skip_load,
        skip_features=request.skip_features,
        skip_train=request.skip_train,
        skip_eval=request.skip_eval,
    )

    response = run_pipeline(container, use_case_request)
    return response.to_dict()