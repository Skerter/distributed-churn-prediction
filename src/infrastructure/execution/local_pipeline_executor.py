from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import uuid4

from src.app.bootstrap import bootstrap
from src.application.dto.requests import CreatePipelineRunRequest, ExecutePipelineRequest
from src.application.use_cases.execute_pipeline import execute_pipeline
from src.infrastructure.execution.dask_client import close_dask_client
from src.infrastructure.pipeline_runs.file_store import FilePipelineRunStore
from src.shared.enums import PipelineExecutorKind, PipelineRunStatus


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _new_run_id(profile: str) -> str:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = uuid4().hex[:8]
    normalized_profile = profile.replace("_", "-")

    return f"{timestamp}-{normalized_profile}-{suffix}"


def _build_initial_payload(
    *,
    run_id: str,
    profile: str,
    executor: str,
    request: CreatePipelineRunRequest,
) -> dict:
    now = _utc_now_iso()

    return {
        "run_id": run_id,
        "status": PipelineRunStatus.QUEUED.value,
        "profile": profile,
        "executor": executor,
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


def _execute_pipeline_run(
    *,
    run_id: str,
    profile: str,
    request: CreatePipelineRunRequest,
    store: FilePipelineRunStore,
    logger,
) -> dict:
    container = None

    try:
        logger.info("Pipeline run стартовал: run_id=%s", run_id)
        store.mark_running(run_id)

        container = bootstrap(
            profile=profile,
            init_dask_client=True,
        )

        execute_request = ExecutePipelineRequest(
            profile=profile,
            execute=request.execute,
            skip_load=request.skip_load,
            skip_features=request.skip_features,
            skip_train=request.skip_train,
            skip_eval=request.skip_eval,
        )

        response = execute_pipeline(container, execute_request)

        result = store.mark_succeeded(
            run_id,
            result=response.to_dict(),
        )

        logger.info("Pipeline run завершён успешно: run_id=%s", run_id)
        return result

    except Exception as exc:
        logger.exception(
            "Pipeline run завершился ошибкой: run_id=%s",
            run_id,
        )
        return store.mark_failed(run_id, error=str(exc))

    finally:
        if container is not None:
            close_dask_client(container.dask_client, container.logger)


class CliPipelineExecutor:
    """Синхронно запускает pipeline для CLI.

    CLI-процесс ждёт завершения pipeline и возвращает финальный статус run.
    """

    def __init__(
        self,
        *,
        profile: str,
        store: FilePipelineRunStore,
        logger,
    ) -> None:
        self.profile = profile
        self.store = store
        self.logger = logger

    def submit(self, request: CreatePipelineRunRequest) -> dict:
        run_id = _new_run_id(self.profile)

        payload = _build_initial_payload(
            run_id=run_id,
            profile=self.profile,
            executor=PipelineExecutorKind.CLI.value,
            request=request,
        )

        self.store.create(payload)

        return _execute_pipeline_run(
            run_id=run_id,
            profile=self.profile,
            request=request,
            store=self.store,
            logger=self.logger,
        )

    def refresh(self, run_id: str) -> dict:
        return self.store.get(run_id)


class WebPipelineExecutor:
    """Запускает pipeline в background thread для Web API.

    HTTP-запрос быстро получает run_id, а pipeline выполняется отдельно
    внутри текущего API-процесса.
    """

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

        payload = _build_initial_payload(
            run_id=run_id,
            profile=self.profile,
            executor=PipelineExecutorKind.WEB.value,
            request=request,
        )

        self.store.create(payload)

        thread = threading.Thread(
            target=_execute_pipeline_run,
            kwargs={
                "run_id": run_id,
                "profile": self.profile,
                "request": request,
                "store": self.store,
                "logger": self.logger,
            },
            daemon=True,
            name=f"pipeline-run-{run_id}",
        )
        thread.start()

        self.logger.info("Pipeline run создан: run_id=%s", run_id)

        return payload

    def refresh(self, run_id: str) -> dict:
        return self.store.get(run_id)