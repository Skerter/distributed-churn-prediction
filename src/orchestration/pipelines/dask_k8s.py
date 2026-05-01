from __future__ import annotations

from src.application.services.dataset_service import ensure_source_dataset
from src.application.services.evaluate_service import evaluate_dask_model
from src.application.services.feature_service import run_dask_feature_engineering
from src.application.services.train_service import train_dask_model

from .base import BasePipeline


class DaskK8sPipeline(BasePipeline):
    """Dask pipeline для Kubernetes-режима.

    В отличие от DaskLocalPipeline, этот pipeline не поднимает кластер сам.
    Kubernetes-кластер Dask должен быть создан заранее через dask-operator
    или YAML-манифесты, а bootstrap подключает client к внешнему scheduler
    по адресу из configs/dask_k8s.yaml.

    Pipeline переиспользует общие Dask-сервисы:
    1. проверка/загрузка исходного датасета;
    2. distributed feature engineering;
    3. distributed training через xgboost.dask;
    4. distributed evaluation.
    """

    def _run_impl(self) -> dict[str, object]:
        """Выполняет Kubernetes Dask pipeline с поддержкой skip-флагов.

        Returns:
            dict[str, object]: Сводка по выполненным шагам, пропущенным шагам
            и созданным артефактам.

        Raises:
            RuntimeError: Если pipeline запущен без Dask client, с неверным
            runtime.mode или без scheduler address.
        """
        self.logger.info("Запущен Dask K8s pipeline")

        # Client создаётся в bootstrap через Client(scheduler_address).
        # Здесь мы только проверяем, что подключение действительно передано
        # в pipeline и может использоваться Dask-сервисами.
        if self.client is None:
            self.logger.error(
                "DaskK8sPipeline ожидает внешний Dask client, но client=None"
            )
            raise RuntimeError("DaskK8sPipeline не может работать без Dask client")

        self.logger.info("Dask client успешно передан в Kubernetes pipeline")
        self.logger.debug("client_type=%s", type(self.client).__name__)

        scheduler_address = self.config.dask.scheduler_address
        dashboard_link = self._resolve_dashboard_link()

        artifacts: dict[str, object] = {
            "dask": {
                "scheduler_address": scheduler_address,
                "dashboard_link": dashboard_link,
            }
        }
        executed_steps: list[str] = []
        skipped_steps: list[str] = []

        self.logger.info("Проверка конфигурации DaskK8sPipeline")
        self._validate_runtime_config(scheduler_address=scheduler_address)
        self._log_skip_warnings()

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
            self.logger.info("Шаг 2/4: distributed feature engineering on Kubernetes")
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
            self.logger.info("Шаг 3/4: distributed train on Kubernetes")
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
            self.logger.info("Шаг 4/4: distributed evaluate on Kubernetes")
            artifacts["eval"] = evaluate_dask_model(
                settings=self.config,
                logger=self.logger.getChild("eval"),
                client=self.client,
            )
            executed_steps.append("eval")

        self.logger.info("DaskK8sPipeline отработал успешно")

        return {
            "message": "Dask k8s pipeline выполнен",
            "executed_steps": executed_steps,
            "skipped_steps": skipped_steps,
            "run_options": self.run_options,
            "artifacts": artifacts,
        }

    def _validate_runtime_config(self, scheduler_address: str | None) -> None:
        """Проверяет runtime-конфигурацию Kubernetes-пайплайна.
        
        Args:
            scheduler_address (str | None): Адрес Dask scheduler из конфига.
        Raises:
            RuntimeError: Если runtime.mode не 'dask_k8s' или если отсутствует
            scheduler_address.
        """
        runtime_mode = self.config.runtime.mode.value

        if runtime_mode != "dask_k8s":
            self.logger.error(
                "DaskK8sPipeline ожидает runtime.mode='dask_k8s', но получено %s",
                runtime_mode,
            )
            raise RuntimeError(
                "DaskK8sPipeline ожидает runtime.mode='dask_k8s', "
                f"но получено '{runtime_mode}'"
            )

        if not scheduler_address:
            self.logger.error("В конфиге отсутствует dask.scheduler_address")
            raise RuntimeError("Для DaskK8sPipeline требуется scheduler_address")

        self.logger.debug("runtime.mode=%s", runtime_mode)
        self.logger.debug("scheduler_address=%s", scheduler_address)
        self.logger.debug("data_source_dir=%s", self.config.data_source_dir)
        self.logger.debug("data_processed_dir=%s", self.config.data_processed_dir)
        self.logger.debug("models_dir=%s", self.config.models_dir)

    def _resolve_dashboard_link(self) -> str | None:
        """Пытается получить ссылку на Dask dashboard у client."""
        try:
            dashboard_link = getattr(self.client, "dashboard_link", None)
        except Exception as exc:
            self.logger.warning("Не удалось получить dashboard_link: %s", exc)
            return None

        if dashboard_link:
            self.logger.info("Dask dashboard: %s", dashboard_link)
        else:
            self.logger.warning("У Dask client не найден dashboard_link")

        return dashboard_link

    def _log_skip_warnings(self) -> None:
        """Логирует потенциально опасные комбинации skip-флагов."""
        if self.run_options["skip_features"] and (
            not self.run_options["skip_train"] or not self.run_options["skip_eval"]
        ):
            self.logger.warning(
                "Пропущен шаг features. Ожидается, что train/valid/test parquet "
                "уже существуют в общем хранилище, доступном Kubernetes pod'ам."
            )

        if self.run_options["skip_train"] and not self.run_options["skip_eval"]:
            self.logger.warning(
                "Пропущен шаг train. Ожидается, что обученная модель уже существует "
                "в models_dir и доступна Kubernetes pod'ам."
            )