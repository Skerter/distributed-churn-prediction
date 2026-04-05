from __future__ import annotations

from typing import Any

from src.churn.app.settings import Settings
from src.churn.shared.enums import RuntimeMode
from src.churn.shared.exceptions import ConfigError


def create_dask_client(settings: Settings, logger) -> Any | None:
    """Создает Dask client на основе настроек приложения.
    params:
        settings (Settings): Настройки приложения, содержащие информацию о режиме выполнения и параметрах Dask.
        logger: Логгер для записи информации о процессе создания Dask client.
    returns:
        Any | None: Экземпляр Dask client для режимов Dask или None для режима pandas.
    raises:
        ConfigError: Если настройки некорректны для выбранного режима выполнения.
    """
    mode = settings.runtime.mode

    if mode == RuntimeMode.PANDAS:
        logger.info("Режим pandas: Dask client не требуется")
        return None

    try:
        from dask.distributed import Client, LocalCluster
    except ImportError as exc:
        raise ConfigError(
            "Для Dask-режимов не установлен пакет dask.distributed"
        ) from exc

    if mode == RuntimeMode.DASK_LOCAL:
        logger.info(
            "Поднимается локальный Dask cluster: workers=%s threads_per_worker=%s",
            settings.dask.n_workers,
            settings.dask.threads_per_worker,
        )
        cluster = LocalCluster(
            n_workers=settings.dask.n_workers,
            threads_per_worker=settings.dask.threads_per_worker,
        )
        return Client(cluster)

    if mode == RuntimeMode.DASK_K8S:
        if not settings.dask.scheduler_address:
            raise ConfigError(
                "Для режима dask_k8s необходимо указать dask.scheduler_address"
            )

        logger.info(
            "Подключение к внешнему Dask scheduler: %s",
            settings.dask.scheduler_address,
        )
        return Client(settings.dask.scheduler_address)

    raise ConfigError(f"Не удалось создать Dask client для режима {mode.value}")


def close_dask_client(client: Any | None, logger) -> None:
    """Закрывает Dask client, если он был создан.
    params:
        client (Any | None): Экземпляр Dask client, который нужно закрыть, или None, если режим pandas.
        logger: Логгер для записи информации о процессе закрытия Dask client.
    """
    if client is None:
        return

    try:
        client.close()
        logger.info("Dask client закрыт")
    except Exception as exc:
        logger.warning("Не удалось корректно закрыть Dask client: %s", exc)