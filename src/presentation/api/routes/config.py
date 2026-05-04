from __future__ import annotations
import sys

from fastapi import APIRouter, HTTPException, Query, status

from src.app.bootstrap import bootstrap
from src.application.use_cases.get_config_summary import get_config_summary
from src.infrastructure.execution.dask_client import close_dask_client
from src.presentation.api.schemas import ConfigSummaryApiResponse
from src.shared.exceptions import ChurnAppError

router = APIRouter(prefix="/config", tags=["config"])


@router.get(
    "/summary",
    response_model=ConfigSummaryApiResponse,
    summary="Получить безопасную сводку конфигурации",
)
def config_summary(
    profile: str = Query(
        default="pandas",
        description="Runtime profile: pandas, dask_local или dask_k8s.",
    ),
) -> dict:
    container = None

    try:
        init_dask_client = True

        if profile == "dask_k8s":
            print("[WARNING] Инициализация Dask client пропущена для профиля dask_k8s, так как он требует специфической настройки Kubernetes кластера. Пожалуйста, убедитесь, что ваш кластер настроен и доступен для использования Dask.",
                  file=sys.stderr)
            init_dask_client = False
    
        container = bootstrap(profile=profile, init_dask_client=init_dask_client)
        response = get_config_summary(container)
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