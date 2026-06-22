from __future__ import annotations

from src.application.dto.responses import PipelineRunResponse


def get_pipeline_run(
    *,
    executor,
    run_id: str,
) -> PipelineRunResponse:
    """Возвращает актуальное состояние pipeline run."""

    payload = executor.refresh(run_id)

    return PipelineRunResponse(
        run_id=payload["run_id"],
        status=payload["status"],
        profile=payload["profile"],
        executor=payload["executor"],
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
        started_at=payload.get("started_at"),
        finished_at=payload.get("finished_at"),
        request=payload["request"],
        result=payload.get("result"),
        error=payload.get("error"),
        metadata=payload.get("metadata"),
    )
