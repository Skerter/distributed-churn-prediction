from src.app.container import AppContainer
from src.application.dto.requests import ExecutePipelineRequest
from src.application.dto.responses import RunPipelineResponse


def execute_pipeline(
    container: AppContainer,
    request: ExecutePipelineRequest,
) -> RunPipelineResponse:
    """Непосредственно выполняет pipeline или dry-run внутри текущего процесса."""

    pipeline_path = container.get_pipeline_path()
    run_options = request.to_run_options()

    if not request.execute:
        container.logger.info(
            "Dry-run pipeline: profile=%s mode=%s pipeline=%s run_options=%s",
            request.profile,
            container.settings.runtime.mode.value,
            pipeline_path,
            run_options,
        )
        return RunPipelineResponse(
            success=True,
            profile=request.profile,
            mode=container.settings.runtime.mode.value,
            backend=container.backend.value,
            pipeline_path=pipeline_path,
            executed=False,
            message=(
                "Dry-run выполнен успешно. Pipeline не запускался. "
                "Для реального запуска используй execute=true."
            ),
            result={"run_options": run_options},
        )

    pipeline = container.build_pipeline(run_options=run_options)
    result = pipeline.run()

    return RunPipelineResponse(
        success=True,
        profile=request.profile,
        mode=container.settings.runtime.mode.value,
        backend=container.backend.value,
        pipeline_path=pipeline_path,
        executed=True,
        message="Pipeline выполнен успешно",
        result=result,
    )