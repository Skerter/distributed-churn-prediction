from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.app.bootstrap import bootstrap
from src.application.dto.requests import RunPipelineRequest
from src.application.use_cases.run_pipeline import run_pipeline
from src.infrastructure.execution.dask_client import close_dask_client
from src.presentation.api.schemas import (
    RunPipelineApiRequest,
    RunPipelineApiResponse,
)
from src.shared.exceptions import ChurnAppError

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post(
    "/run",
    response_model=RunPipelineApiResponse,
    summary="Запустить ML pipeline",
)
def run_pipeline_endpoint(request: RunPipelineApiRequest) -> dict:
    container = None

    try:
        container = bootstrap(profile=request.profile)

        use_case_request = RunPipelineRequest(
            profile=request.profile,
            execute=request.execute,
            skip_load=request.skip_load,
            skip_features=request.skip_features,
            skip_train=request.skip_train,
            skip_eval=request.skip_eval,
        )

        response = run_pipeline(container, use_case_request)
        return response.to_dict()

    except ChurnAppError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка API: {exc}",
        ) from exc

    finally:
        if container is not None:
            close_dask_client(container.dask_client, container.logger)