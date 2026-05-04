from __future__ import annotations

from src.app.container import AppContainer
from src.infrastructure.execution.kubernetes_pipeline_executor import (
    KubernetesJobPipelineExecutor,
)
from src.infrastructure.execution.local_pipeline_executor import (
    LocalBackgroundPipelineExecutor,
)
from src.infrastructure.pipeline_runs.file_store import FilePipelineRunStore
from src.shared.enums import PipelineExecutorKind


def build_pipeline_executor(
    *,
    container: AppContainer,
    store: FilePipelineRunStore,
):
    settings = container.settings

    if settings.api.pipeline_executor == PipelineExecutorKind.LOCAL_BACKGROUND:
        return LocalBackgroundPipelineExecutor(
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