from __future__ import annotations

from .base import BasePipeline


class DaskLocalPipeline(BasePipeline):
    """Stub-версия локального Dask pipeline."""

    def _run_impl(self) -> dict[str, object]:
        self.logger.info("Запущен Dask Local pipeline")
        self.logger.debug("Начало stub-логики DaskLocalPipeline")

        if self.client is None:
            self.logger.error(
                "DaskLocalPipeline ожидает активный Dask client, но client=None"
            )
            raise RuntimeError(
                "DaskLocalPipeline не может работать без Dask client"
            )

        self.logger.info("Dask client успешно передан в pipeline")
        self.logger.debug("client_type=%s", type(self.client).__name__)

        self.logger.info("Шаг 1/4: проверка конфигурации runtime")
        if self.config.runtime.mode.value != "dask_local":
            self.logger.warning(
                "DaskLocalPipeline запущен с runtime.mode=%s",
                self.config.runtime.mode.value,
            )

        self.logger.info("Шаг 2/4: проверка Dask-конфигурации")
        self.logger.debug("n_workers=%s", self.config.dask.n_workers)
        self.logger.debug("threads_per_worker=%s", self.config.dask.threads_per_worker)

        self.logger.info("Шаг 3/4: stub distributed feature engineering")
        self.logger.debug("Реальная распределённая обработка будет подключена далее")

        self.logger.info("Шаг 4/4: stub distributed training")
        self.logger.debug("Реальное distributed обучение пока не подключено")

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
            "message": "Dask local pipeline stub выполнен",
            "dask": {
                "n_workers": self.config.dask.n_workers,
                "threads_per_worker": self.config.dask.threads_per_worker,
                "dashboard_link": dashboard_link,
            },
        }

        self.logger.info("DaskLocalPipeline stub отработал успешно")
        return result