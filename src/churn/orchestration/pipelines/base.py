from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class BasePipeline(ABC):
    """Базовый шаблон пайплайна.

    Все конкретные пайплайны должны реализовать только _run_impl().
    Общая обвязка: логирование, замер времени, обработка ошибок — живёт здесь.
    """

    def __init__(self, config, logger, client=None, run_options: dict[str, Any] | None = None) -> None:
        self.config = config
        self.logger = logger
        self.client = client
        self.run_options = {
            "skip_load": False,
            "skip_features": False,
            "skip_train": False,
            "skip_eval": False,
        }
        if run_options:
            self.run_options.update(
                {key: bool(value) for key, value in run_options.items()}
            )

        self.logger.debug(
            "Инициализирован %s: mode=%s, has_client=%s, run_options=%s",
            self.__class__.__name__,
            getattr(self.config.runtime.mode, "value", self.config.runtime.mode),
            self.client is not None,
            self.run_options,
        )

    @property
    def pipeline_name(self) -> str:
        return self.__class__.__name__

    def run(self) -> dict[str, Any]:
        started_at = datetime.now()

        self.logger.info("=== Старт pipeline: %s ===", self.pipeline_name)
        self.logger.debug("project_root=%s", self.config.project_root)
        self.logger.debug("data_source_dir=%s", self.config.data_source_dir)
        self.logger.debug("data_processed_dir=%s", self.config.data_processed_dir)
        self.logger.debug("models_dir=%s", self.config.models_dir)
        self.logger.debug("logs_dir=%s", self.config.logs_dir)
        self.logger.debug("runtime_mode=%s", self.config.runtime.mode.value)
        self.logger.debug("run_options=%s", self.run_options)

        if self.client is None:
            self.logger.info("Dask client отсутствует: pipeline работает без distributed client")
        else:
            self.logger.info("Dask client доступен и будет использоваться pipeline")
            self.logger.debug("client_type=%s", type(self.client).__name__)

        try:
            self.logger.debug("Переход в _run_impl() для %s", self.pipeline_name)
            result = self._run_impl()

            finished_at = datetime.now()
            duration = finished_at - started_at

            self.logger.info(
                "=== Pipeline %s завершён успешно за %s ===",
                self.pipeline_name,
                duration,
            )
            self.logger.debug("Результат pipeline %s: %s", self.pipeline_name, result)

            return {
                "status": "success",
                "pipeline": self.pipeline_name,
                "mode": self.config.runtime.mode.value,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": duration.total_seconds(),
                "payload": result,
            }

        except NotImplementedError:
            self.logger.error(
                "Pipeline %s не реализован: _run_impl() должен быть переопределён",
                self.pipeline_name,
            )
            raise

        except Exception as exc:
            finished_at = datetime.now()
            duration = finished_at - started_at

            self.logger.exception(
                "Pipeline %s завершился с ошибкой после %s: %s",
                self.pipeline_name,
                duration,
                exc,
            )
            raise

    @abstractmethod
    def _run_impl(self) -> dict[str, Any]:
        """Основная логика конкретного пайплайна."""
        raise NotImplementedError