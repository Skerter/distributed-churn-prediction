from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Any

from app.settings import Settings
from shared.enums import BackendKind
from shared.exceptions import PipelineResolutionError


@dataclass(slots=True)
class AppContainer:
    """Контейнер приложения, который управляет зависимостями и конфигурацией для построения и выполнения pipeline.

    Raises:
        PipelineResolutionError: Не удалось импортировать или создать экземпляр pipeline на основе зарегистрированного пути.
        PipelineResolutionError: Не удалось создать экземпляр pipeline на основе зарегистрированного пути.

    Returns:
        Any: Экземпляр класса pipeline, соответствующий текущему режиму выполнения.
    """
    settings: Settings
    logger: logging.Logger
    backend: BackendKind #TODO: бесполезно, нужно удалить и юзать только runtime.mode
    dask_client: Any | None
    pipeline_registry: dict[str, str]

    def get_pipeline_path(self) -> str:
        """Возвращает путь к pipeline на основе текущего режима выполнения.

        Raises:
            PipelineResolutionError: Если не удалось разрешить путь к pipeline на основе текущего режима выполнения.

        Returns:
            str: Путь к классу pipeline, зарегистрированному для текущего режима выполнения.
        """
        mode = self.settings.runtime.mode.value

        try:
            return self.pipeline_registry[mode]
        except KeyError as exc:
            raise PipelineResolutionError(f"Для режима {mode} не зарегистрирован pipeline") from exc

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