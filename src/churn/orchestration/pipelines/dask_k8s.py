from __future__ import annotations

from .base import BasePipeline


class DaskK8sPipeline(BasePipeline):
    """Stub-версия Dask pipeline для Kubernetes."""

    def _run_impl(self) -> dict[str, object]:
        self.logger.info("Запущен Dask K8s pipeline")
        self.logger.debug("Начало stub-логики DaskK8sPipeline")

        if self.client is None:
            self.logger.error(
                "DaskK8sPipeline ожидает внешний Dask client, но client=None"
            )
            raise RuntimeError(
                "DaskK8sPipeline не может работать без Dask client"
            )

        self.logger.info("Подключение к удалённому Dask cluster подтверждено")
        self.logger.debug("client_type=%s", type(self.client).__name__)

        self.logger.info("Шаг 1/4: проверка конфигурации runtime")
        if self.config.runtime.mode.value != "dask_k8s":
            self.logger.warning(
                "DaskK8sPipeline запущен с runtime.mode=%s",
                self.config.runtime.mode.value,
            )

        self.logger.info("Шаг 2/4: проверка scheduler address")
        scheduler_address = self.config.dask.scheduler_address
        if not scheduler_address:
            self.logger.error("В конфиге отсутствует dask.scheduler_address")
            raise RuntimeError(
                "Для DaskK8sPipeline требуется scheduler_address"
            )
        self.logger.debug("scheduler_address=%s", scheduler_address)

        self.logger.info("Шаг 3/4: stub distributed feature engineering на K8s")
        self.logger.debug("Реальная логика работы с удалённым кластером будет добавлена позже")

        self.logger.info("Шаг 4/4: stub distributed training на K8s")
        self.logger.debug("Реальное распределённое обучение пока не подключено")

        dashboard_link = None
        try:
            dashboard_link = getattr(self.client, "dashboard_link", None)
            if dashboard_link:
                self.logger.info("Dask dashboard: %s", dashboard_link)
            else:
                self.logger.warning("У Dask client не найден dashboard_link")
        except Exception as exc:
            self.logger.warning("Не удалось получить dashboard_link: %s", exc)

        result = {
            "message": "Dask k8s pipeline stub выполнен",
            "dask": {
                "scheduler_address": scheduler_address,
                "dashboard_link": dashboard_link,
            },
        }

        self.logger.info("DaskK8sPipeline stub отработал успешно")
        return result