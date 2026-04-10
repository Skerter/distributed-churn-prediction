from __future__ import annotations

from src.churn.application.services.dataset_service import ensure_source_dataset
from src.churn.application.services.evaluate_service import evaluate_pandas_model
from src.churn.application.services.feature_service import run_pandas_feature_engineering
from src.churn.application.services.train_service import train_pandas_model

from .base import BasePipeline


class PandasPipeline(BasePipeline):
    def _run_impl(self) -> dict[str, object]:
        """Реализует выполнение пайплайна в режиме pandas, последовательно выполняя шаги загрузки данных, обработки признаков, обучения модели и оценки модели, при этом учитывая опции пропуска шагов и логируя процесс выполнения.

        Returns:
            dict[str, object]: Результат выполнения пайплайна, содержащий информацию о выполненных и пропущенных шагах, а также артефакты, полученные на каждом этапе. 
        """
        self.logger.info("Запущен реальный Pandas pipeline")

        if self.client is not None:
            self.logger.warning("Для PandasPipeline был передан client=%s, хотя он не требуется", type(self.client).__name__)

        if self.run_options["skip_features"] and (not self.run_options["skip_train"] or not self.run_options["skip_eval"]):
            self.logger.warning("Пропущен шаг features. Ожидается, что parquet-артефакты уже существуют.")

        if self.run_options["skip_train"] and not self.run_options["skip_eval"]:
            self.logger.warning("Пропущен шаг train. Ожидается, что обученная модель уже существует.")

        executed_steps: list[str] = []
        skipped_steps: list[str] = []
        artifacts: dict[str, object] = {}

        if self.run_options["skip_load"]:
            self.logger.warning("Шаг load пропущен")
            skipped_steps.append("load")
        else:
            self.logger.info("Шаг 1/4: load dataset")
            artifacts["load"] = ensure_source_dataset(
                settings=self.config,
                logger=self.logger.getChild("dataset"),
            )
            executed_steps.append("load")

        if self.run_options["skip_features"]:
            self.logger.warning("Шаг features пропущен")
            skipped_steps.append("features")
        else:
            self.logger.info("Шаг 2/4: feature engineering")
            artifacts["features"] = run_pandas_feature_engineering(
                settings=self.config,
                logger=self.logger.getChild("features"),
            )
            executed_steps.append("features")

        if self.run_options["skip_train"]:
            self.logger.warning("Шаг train пропущен")
            skipped_steps.append("train")
        else:
            self.logger.info("Шаг 3/4: train model")
            artifacts["train"] = train_pandas_model(
                settings=self.config,
                logger=self.logger.getChild("train"),
            )
            executed_steps.append("train")

        if self.run_options["skip_eval"]:
            self.logger.warning("Шаг eval пропущен")
            skipped_steps.append("eval")
        else:
            self.logger.info("Шаг 4/4: evaluate model")
            artifacts["eval"] = evaluate_pandas_model(
                settings=self.config,
                logger=self.logger.getChild("eval"),
            )
            executed_steps.append("eval")

        result = {
            "message": "Pandas pipeline выполнен",
            "executed_steps": executed_steps,
            "skipped_steps": skipped_steps,
            "run_options": self.run_options,
            "artifacts": artifacts,
        }

        return result