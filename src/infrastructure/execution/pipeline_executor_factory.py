from __future__ import annotations

from src.app.container import AppContainer
from src.infrastructure.execution.kubernetes_pipeline_executor import (
    KubernetesJobPipelineExecutor,
)
from src.infrastructure.execution.local_pipeline_executor import (
    BotPipelineExecutor,
    CliPipelineExecutor,
    WebPipelineExecutor,
)
from src.infrastructure.pipeline_runs.file_store import FilePipelineRunStore
from src.shared.enums import PipelineExecutorKind


def build_pipeline_executor(
    *,
    container: AppContainer,
    store: FilePipelineRunStore,
):
    settings = container.settings

    if settings.api.pipeline_executor == PipelineExecutorKind.CLI:
        return CliPipelineExecutor(
            profile=settings.runtime.mode.value,
            store=store,
            logger=container.logger,
        )

    if settings.api.pipeline_executor == PipelineExecutorKind.WEB:
        return WebPipelineExecutor(
            profile=settings.runtime.mode.value,
            store=store,
            logger=container.logger,
            max_concurrent_runs=settings.api.max_concurrent_pipeline_runs,
        )

    if settings.api.pipeline_executor == PipelineExecutorKind.KUBERNETES_JOB:
        return KubernetesJobPipelineExecutor(
            settings=settings,
            store=store,
            logger=container.logger,
            max_concurrent_runs=settings.api.max_concurrent_pipeline_runs,
        )

    raise RuntimeError(
        f"Неизвестный pipeline executor: {settings.api.pipeline_executor.value}"
    )


def build_bot_pipeline_executor(
    *,
    container: AppContainer,
    store: FilePipelineRunStore,
) -> BotPipelineExecutor:
    """Создаёт executor для Telegram-бота.

    В отличие от build_pipeline_executor, всегда возвращает BotPipelineExecutor
    и передаёт готовый AppContainer без повторного bootstrap.
    """
    return BotPipelineExecutor(
        container=container,
        store=store,
        logger=container.logger,
        max_concurrent_runs=container.settings.api.max_concurrent_pipeline_runs,
    )