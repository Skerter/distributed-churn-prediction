from __future__ import annotations

from fastapi import APIRouter, Depends

from src.application.dto.requests import CreatePipelineRunRequest
from src.application.use_cases.create_pipeline_run import create_pipeline_run
from src.application.use_cases.get_pipeline_run import get_pipeline_run
from src.presentation.web.dependencies import get_pipeline_executor
from src.presentation.web.schemas import (
    CreatePipelineRunApiRequest,
    PipelineRunApiResponse,
)

router = APIRouter(prefix="/pipeline/runs", tags=["pipeline-runs"])


@router.post(
    "",
    response_model=PipelineRunApiResponse,
    summary="Создать pipeline run",
)
def create_pipeline_run_endpoint(
    request: CreatePipelineRunApiRequest,
    executor=Depends(get_pipeline_executor),
) -> dict:
    use_case_request = CreatePipelineRunRequest(
        execute=request.execute,
        skip_load=request.skip_load,
        skip_features=request.skip_features,
        skip_train=request.skip_train,
        skip_eval=request.skip_eval,
    )

    response = create_pipeline_run(
        executor=executor,
        request=use_case_request,
    )

    return response.to_dict()


@router.get(
    "/{run_id}",
    response_model=PipelineRunApiResponse,
    summary="Получить состояние pipeline run",
)
def get_pipeline_run_endpoint(
    run_id: str,
    executor=Depends(get_pipeline_executor),
) -> dict:
    response = get_pipeline_run(
        executor=executor,
        run_id=run_id,
    )

    return response.to_dict()