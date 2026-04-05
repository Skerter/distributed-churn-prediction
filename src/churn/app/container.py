from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Any

from src.churn.app.settings import Settings
from src.churn.shared.enums import BackendKind
from src.churn.shared.exceptions import PipelineResolutionError


@dataclass(slots=True)
class AppContainer:
    '''Контейнер приложения, который инкапсулирует все зависимости и настройки, необходимые для работы приложения.
    attrs:
        settings (Settings): Настройки приложения, включая пути, параметры логирования и режим выполнения.
        logger (logging.Logger): Логгер для записи информации о работе приложения.
        backend (BackendKind): Тип бэкенда для выполнения (локальный или Dask).
        dask_client (Any | None): Экземпляр Dask client для режимов Dask или None для режима pandas.
        pipeline_registry (dict[str, str]): Реестр, сопоставляющий режимы выполнения с путями к классам pipeline.
    '''
    settings: Settings
    logger: logging.Logger
    backend: BackendKind
    dask_client: Any | None
    pipeline_registry: dict[str, str]

    def get_pipeline_path(self) -> str:
        """Получает путь к классу pipeline на основе текущего режима выполнения.
        returns:
            str: Дот-нотация пути к классу pipeline, например "src.churn.pipelines.pandas.PandasPipeline".
        raises:
            PipelineResolutionError: Если для текущего режима выполнения не зарегистрирован pipeline.
        """
        mode = self.settings.runtime.mode.value

        try:
            return self.pipeline_registry[mode]
        except KeyError as exc:
            raise PipelineResolutionError(
                f"Для режима {mode} не зарегистрирован pipeline"
            ) from exc

    def build_pipeline(self, run_options: dict[str, Any] | None = None) -> Any:
        """Строит экземпляр pipeline на основе текущего режима выполнения и предоставленных опций запуска.

        Args:
            run_options (dict[str, Any] | None, optional): Опции пропуска этапов, флаги исполнения и профиль выполнения. По умолчанию None.

        Raises:
            PipelineResolutionError: Если не удалось импортировать или создать экземпляр pipeline на основе зарегистрированного пути.
            PipelineResolutionError: Если не удалось создать экземпляр pipeline на основе зарегистрированного пути.

        Returns:
            Any: Экземпляр класса pipeline, соответствующий текущему режиму выполнения.
        """
        dotted_path = self.get_pipeline_path()

        try:
            module_path, class_name = dotted_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            pipeline_cls = getattr(module, class_name)
        except Exception as exc:
            raise PipelineResolutionError(
                f"Не удалось импортировать pipeline {dotted_path}"
            ) from exc

        try:
            return pipeline_cls(
                config=self.settings,
                logger=self.logger,
                client=self.dask_client,
                run_options=run_options,
            )
        except Exception as exc:
            raise PipelineResolutionError(
                f"Не удалось создать экземпляр pipeline {dotted_path}"
            ) from exc