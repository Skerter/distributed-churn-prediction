from __future__ import annotations

from src.app.container import AppContainer
from src.app.settings import Settings
from src.infrastructure.config.loader import find_project_root, load_settings_dict
from src.infrastructure.execution.backend import resolve_backend  # TODO: Нахуй не нужен, можно юзать только runtime.mode
from src.infrastructure.execution.dask_client import create_dask_client
from src.infrastructure.logging.factory import build_logger
from src.infrastructure.storage.paths import ensure_project_dirs


def bootstrap(profile: str = "pandas", init_dask_client: bool = True) -> AppContainer:
    """Инициализирует и настраивает контейнер приложения, который управляет зависимостями и конфигурацией для построения и выполнения pipeline.

    Args:
        profile (str, optional): Профиль конфигурации, определяющий набор настроек для приложения. По умолчанию "pandas".
        init_dask_client (bool, optional): Флаг, указывающий, нужно ли инициализировать Dask клиент. По умолчанию True.

    Returns:
        AppContainer: Контейнер, содержащий все инициализированные компоненты приложения, такие как настройки, логгер, бэкенд и Dask клиент.
    """
    project_root = find_project_root()
    settings_dict = load_settings_dict(project_root=project_root, profile=profile)
    settings = Settings.from_dict(settings_dict, project_root=project_root)

    ensure_project_dirs(settings)
    logger = build_logger(settings)
    backend = resolve_backend(settings.runtime.mode) # TODO Тут тож убрать потом

    if init_dask_client:
        dask_client = create_dask_client(settings, logger)
    else:
        logger.info(
            "Инициализация Dask client пропущена: profile=%s mode=%s",
            profile,
            settings.runtime.mode.value,
        )
        dask_client = None

    pipeline_registry = {
        "pandas": "src.orchestration.pipelines.pandas.PandasPipeline",
        "dask_local": "src.orchestration.pipelines.dask_local.DaskLocalPipeline",
        "dask_k8s": "src.orchestration.pipelines.dask_k8s.DaskK8sPipeline",
    }

    logger.info(
        "Bootstrap завершён: profile=%s mode=%s backend=%s",
        profile,
        settings.runtime.mode.value,
        backend.value,
    )

    return AppContainer(
        settings=settings,
        logger=logger,
        backend=backend,
        dask_client=dask_client,
        pipeline_registry=pipeline_registry,
    )