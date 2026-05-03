from src.app.container import AppContainer
from src.application.dto.responses import ConfigSummaryResponse


def get_config_summary(container: AppContainer) -> ConfigSummaryResponse:
    """Возвращает безопасную сводку конфигурации для Web API."""

    settings = container.settings

    return ConfigSummaryResponse(
        app={
            "name": settings.app.name,
            "version": settings.app.version,
        },
        runtime={
            "mode": settings.runtime.mode.value,
        },
        backend=container.backend.value,
        model={
            "name": settings.model.name,
            "version": settings.model.version,
            "random_state": settings.model.random_state,
            "test_size": settings.model.test_size,
            "cv_folds": settings.model.cv_folds,
        },
        data={
            "dataset_slug": settings.data.dataset_slug,
            "train_filename": settings.data.train_filename,
            "test_filename": settings.data.test_filename,
            "target_column": settings.data.target_column,
        },
        dask={
            "scheduler_address": settings.dask.scheduler_address,
            "n_workers": settings.dask.n_workers,
            "threads_per_worker": settings.dask.threads_per_worker,
        },
        pipeline={
            "default_execute": settings.pipeline.default_execute,
        },
        paths={
            "data_source": settings.paths.data_source,
            "data_processed": settings.paths.data_processed,
            "models": settings.paths.models,
            "logs": settings.paths.logs,
            "notebooks": settings.paths.notebooks,
        },
    )