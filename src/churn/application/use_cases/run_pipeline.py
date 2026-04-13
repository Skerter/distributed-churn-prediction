from src.churn.app.container import AppContainer
from src.churn.application.dto.requests import RunPipelineRequest
from src.churn.application.dto.responses import RunPipelineResponse


def run_pipeline(container: AppContainer, request: RunPipelineRequest) -> RunPipelineResponse:
    """Запускает pipeline на основе предоставленного запроса и контейнера приложения, который содержит все необходимые зависимости и настройки. Функция поддерживает режим dry-run, при котором pipeline не выполняется, а только логируется информация о том, какой pipeline был бы запущен с какими опциями.

    Args:
        container (AppContainer): Контейнер приложения, содержащий зависимости и настройки для выполнения pipeline.
        request (RunPipelineRequest): Запрос, содержащий информацию о профиле, флаге исполнения и опциях запуска pipeline.

    Returns:
        RunPipelineResponse: DTO, содержащий результат выполнения pipeline и информацию о нем.
    """
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
                "Для реального запуска используй флаг --execute."
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