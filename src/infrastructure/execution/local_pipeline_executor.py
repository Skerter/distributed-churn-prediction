from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import uuid4

from src.app.bootstrap import bootstrap
from src.application.dto.requests import CreatePipelineRunRequest, RunPipelineRequest
from src.application.use_cases.run_pipeline import run_pipeline
from src.infrastructure.execution.dask_client import close_dask_client
from src.infrastructure.pipeline_runs.file_store import FilePipelineRunStore
from src.shared.enums import PipelineRunStatus


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _new_run_id(profile: str) -> str:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = uuid4().hex[:8]
    return f"{timestamp}-{profile.replace('_', '-')}-{suffix}"


class LocalBackgroundPipelineExecutor:
    """Запускает pipeline в background thread внутри текущего API-процесса."""

    def __init__(
        self,
        *,
        profile: str,
        store: FilePipelineRunStore,
        logger,
        max_concurrent_runs: int = 1,
    ) -> None:
        self.profile = profile
        self.store = store
        self.logger = logger
        self.max_concurrent_runs = max_concurrent_runs

    def submit(self, request: CreatePipelineRunRequest) -> dict:
        if self.max_concurrent_runs <= 1 and self.store.has_active_runs():
            raise RuntimeError("Уже есть активный pipeline run")

        run_id = _new_run_id(self.profile)
        now = _utc_now_iso()

        payload = {
            "run_id": run_id,
            "status": PipelineRunStatus.QUEUED.value,
            "profile": self.profile,
            "executor": "local_background",
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "finished_at": None,
            "request": {
                "execute": request.execute,
                "skip_load": request.skip_load,
                "skip_features": request.skip_features,
                "skip_train": request.skip_train,
                "skip_eval": request.skip_eval,
            },
            "result": None,
            "error": None,
            "metadata": {},
        }

        self.store.create(payload)

        thread = threading.Thread(
            target=self._run,
            args=(run_id, request),
            daemon=True,
            name=f"pipeline-run-{run_id}",
        )
        thread.start()

        self.logger.info("Pipeline run создан: run_id=%s", run_id)
        return payload

    def refresh(self, run_id: str) -> dict:
        return self.store.get(run_id)

    def _run(self, run_id: str, request: CreatePipelineRunRequest) -> None:
        container = None

        try:
            self.logger.info("Pipeline run стартовал: run_id=%s", run_id)
            self.store.mark_running(run_id)

            container = bootstrap(profile=self.profile, init_dask_client=True)

            use_case_request = RunPipelineRequest(
                profile=self.profile,
                execute=request.execute,
                skip_load=request.skip_load,
                skip_features=request.skip_features,
                skip_train=request.skip_train,
                skip_eval=request.skip_eval,
            )

            response = run_pipeline(container, use_case_request)
            self.store.mark_succeeded(run_id, result=response.to_dict())

            self.logger.info("Pipeline run завершён успешно: run_id=%s", run_id)

        except Exception as exc:
            self.logger.exception("Pipeline run завершился ошибкой: run_id=%s", run_id)
            self.store.mark_failed(run_id, error=str(exc))

        finally:
            if container is not None:
                close_dask_client(container.dask_client, container.logger)