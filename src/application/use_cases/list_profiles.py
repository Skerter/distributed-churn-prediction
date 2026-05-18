from src.application.dto.responses import ProfileInfo, ProfilesResponse
from src.shared.enums import RuntimeMode


def list_profiles() -> ProfilesResponse:
    """Возвращает список runtime-профилей, которые может показать web-интерфейс."""

    profiles = [
        ProfileInfo(
            name="pandas",
            runtime_mode=RuntimeMode.PANDAS.value,
            web_enabled=True,
            description=(
                "Локальный pandas-режим. Подходит для быстрой проверки API, "
                "dry-run и обычного локального запуска pipeline."
            ),
        ),
        ProfileInfo(
            name="dask_local",
            runtime_mode=RuntimeMode.DASK_LOCAL.value,
            web_enabled=True,
            description=(
                "Локальный Dask-режим. Поднимает LocalCluster на машине, "
                "где запущен сервер."
            ),
        ),
        ProfileInfo(
            name="dask_k8s",
            runtime_mode=RuntimeMode.DASK_K8S.value,
            web_enabled=False,
            description=(
                "Kubernetes-режим для запуска через внешний Dask scheduler "
                "и Kubernetes-инфраструктуру."
            ),
            warning=(
                "Пока не рекомендуется запускать dask_k8s напрямую из Web API. "
                "Для Kubernetes позже лучше сделать отдельный механизм через Job."
            ),
        ),
    ]

    return ProfilesResponse(
        default_profile=RuntimeMode.PANDAS.value,
        profiles=profiles,
    )