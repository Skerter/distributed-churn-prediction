from __future__ import annotations

from src.application.services.dataset_service import ensure_source_dataset
from src.application.services.evaluate_service import evaluate_dask_model
from src.application.services.feature_service import run_dask_feature_engineering
from src.application.services.train_service import train_dask_model

from .base import BasePipeline


class DaskLocalPipeline(BasePipeline):
    """Локальный distributed pipeline на базе Dask LocalCluster.

    Pipeline повторяет контракт pandas-версии:
    1. Проверка/загрузка исходного датасета
    2. Feature engineering в Dask DataFrame
    3. Обучение XGBoost через xgboost.dask
    4. Оценка модели и сохранение метрик

    Для выполнения требуется активный Dask client.
    """

    def _run_impl(self) -> dict[str, object]:
        """Выполняет dask_local pipeline с поддержкой skip-флагов.

        Returns:
            dict[str, object]: Сводка по выполненным этапам и артефактам.

        Raises:
            RuntimeError: Если pipeline запущен без активного Dask client.
        """
        self.logger.info("Запущен Dask Local pipeline")

        if self.client is None:
            self.logger.error("DaskLocalPipeline ожидает активный Dask client, но client=None")
            raise RuntimeError("DaskLocalPipeline не может работать без Dask client")

        self.logger.info("Dask client успешно передан в pipeline")
        self.logger.debug("client_type=%s", type(self.client).__name__)

        dashboard_link = None
        try:
            dashboard_link = getattr(self.client, "dashboard_link", None)
            if dashboard_link:
                self.logger.info("Dask dashboard: %s", dashboard_link)
            else:
                self.logger.warning("У Dask client не найден dashboard_link")
        except Exception as exc:
            self.logger.warning("Не удалось получить dashboard_link: %s", exc)

        if self.run_options["skip_features"] and (
            not self.run_options["skip_train"] or not self.run_options["skip_eval"]
        ):
            self.logger.warning(
                "Пропущен шаг features. Ожидается, что parquet-артефакты уже существуют."
            )

        if self.run_options["skip_train"] and not self.run_options["skip_eval"]:
            self.logger.warning(
                "Пропущен шаг train. Ожидается, что обученная модель уже существует."
            )

        executed_steps = []
        skipped_steps = []
        artifacts = {
            "dask": {
                "n_workers": self.config.dask.n_workers,
                "threads_per_worker": self.config.dask.threads_per_worker,
                "dashboard_link": dashboard_link,
            }
        }

        self.logger.info("Проверка конфигурации пайпайна")

        if self.config.runtime.mode.value != "dask_local":
            self.logger.warning(
                "DaskLocalPipeline ожидает runtime.mode='dask_local', но получено %s",
                self.config.runtime.mode.value,
            )
            raise RuntimeError(
                f"DaskLocalPipeline ожидает runtime.mode='dask_local', но получено '{self.config.runtime.mode.value}'"
            )

        if not self.config.dask.n_workers or not self.config.dask.threads_per_worker:
            self.logger.warning(
                "DaskLocalPipeline запущен с неполной Dask-конфигурацией: n_workers=%s, threads_per_worker=%s",
                self.config.dask.n_workers,
                self.config.dask.threads_per_worker,
            )
            raise RuntimeError(
                "DaskLocalPipeline требует указания n_workers и threads_per_worker в конфигурации dask"
            )

        self.logger.debug("n_workers=%s", self.config.dask.n_workers)
        self.logger.debug("threads_per_worker=%s", self.config.dask.threads_per_worker)

        if self.run_options["skip_load"]:
            self.logger.warning("Пропущен шаг load.")
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
            artifacts["features"] = run_dask_feature_engineering(
                settings=self.config,
                logger=self.logger.getChild("features"),
                client=self.client,
            )
            executed_steps.append("features")

        if self.run_options["skip_train"]:
            self.logger.warning("Шаг train пропущен")
            skipped_steps.append("train")
        else:
            self.logger.info("Шаг 3/4: dask local train")
            artifacts["train"] = train_dask_model(
                settings=self.config,
                logger=self.logger.getChild("train"),
                client=self.client,
            )
            executed_steps.append("train")

        if self.run_options["skip_eval"]:
            self.logger.warning("Шаг eval пропущен")
            skipped_steps.append("eval")
        else:
            self.logger.info("Шаг 4/4: Dask evaluate model")
            artifacts["eval"] = evaluate_dask_model(
                settings=self.config,
                logger=self.logger.getChild("eval"),
                client=self.client,
            )
            executed_steps.append("eval")

        self.logger.info("DaskLocalPipeline отработал успешно")

        return {
            "message": "Dask local pipeline выполнен",
            "executed_steps": executed_steps,
            "skipped_steps": skipped_steps,
            "run_options": self.run_options,
            "artifacts": artifacts,
        }
