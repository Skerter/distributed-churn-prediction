from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from src.app.bootstrap import bootstrap
from src.application.use_cases.get_health import get_health
from src.infrastructure.execution.dask_client import close_dask_client
from src.presentation.api.schemas import HealthApiResponse
from src.shared.exceptions import ChurnAppError

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthApiResponse,
    summary="Проверить состояние приложения",
)
def health(
    profile: str = Query(
        default="pandas",
        description="Runtime profile: pandas, dask_local или dask_k8s.",
    ),
) -> dict:
    container = None

    try:
        container = bootstrap(profile=profile)
        response = get_health(container)
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