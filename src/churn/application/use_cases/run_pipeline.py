from src.churn.app.container import AppContainer
from src.churn.application.dto.requests import RunPipelineRequest
from src.churn.application.dto.responses import RunPipelineResponse


def run_pipeline(
    container: AppContainer,
    request: RunPipelineRequest,
) -> RunPipelineResponse:
    """Запускает ML pipeline на основе предоставленного запроса и контейнера приложения.
    params:
        container (AppContainer): Контейнер приложения, содержащий настройки и компоненты.
        request (RunPipelineRequest): DTO, содержащий профиль и флаг выполнения.
    returns:
        RunPipelineResponse: DTO, содержащий результат выполнения pipeline и информацию о нем.
    """
    pipeline_path = container.get_pipeline_path()

    if not request.execute:
        container.logger.info(
            "Dry-run pipeline: profile=%s mode=%s pipeline=%s",
            request.profile,
            container.settings.runtime.mode.value,
            pipeline_path,
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
            result=None,
        )

    pipeline = container.build_pipeline()
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