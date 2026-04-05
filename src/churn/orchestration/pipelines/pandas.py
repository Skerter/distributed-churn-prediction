from __future__ import annotations

from .base import BasePipeline


class PandasPipeline(BasePipeline):
    """Stub-версия локального pandas pipeline.

    Здесь пока нет реального ML-кода.
    Нужен для проверки архитектуры, CLI и end-to-end запуска.
    
    TODO: Написать реальный ML-код вместо stub-версии
    """

    def _run_impl(self) -> dict[str, object]:
        self.logger.info("Запущен Pandas pipeline")
        self.logger.debug("Начало stub-логики Pandas pipeline")

        if self.client is not None:
            self.logger.warning(
                "Для PandasPipeline был передан client=%s, хотя он не требуется",
                type(self.client).__name__,
            )

        self.logger.info("Шаг 1/4: подготовка входных путей")
        self.logger.debug("source=%s", self.config.data_source_dir)
        self.logger.debug("processed=%s", self.config.data_processed_dir)

        self.logger.info("Шаг 2/4: проверка конфигурации runtime")
        if self.config.runtime.mode.value != "pandas":
            self.logger.warning(
                "PandasPipeline запущен с нестандартным runtime.mode=%s",
                self.config.runtime.mode.value,
            )

        self.logger.info("Шаг 3/4: stub feature engineering")
        self.logger.debug("Реальный feature engineering будет подключён на следующем этапе")

        self.logger.info("Шаг 4/4: stub training/evaluation")
        self.logger.debug("Реальное обучение и оценка пока не подключены")

        result = {
            "message": "Pandas pipeline stub выполнен",
            "artifacts": {
                "data_source_dir": str(self.config.data_source_dir),
                "data_processed_dir": str(self.config.data_processed_dir),
                "models_dir": str(self.config.models_dir),
            },
        }

        self.logger.info("Pandas pipeline stub отработал успешно")
        return result