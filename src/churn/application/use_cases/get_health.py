from src.churn.application.dto.responses import HealthResponse
from src.churn.app.container import AppContainer


def get_health(container: AppContainer) -> HealthResponse:
    """Возвращает информацию о состоянии приложения, включая имя, версию, профиль, бэкенд и корневой каталог проекта.
    params:
        container (AppContainer): Контейнер приложения, содержащий настройки и другие компоненты.
    returns:
        HealthResponse: DTO, содержащий информацию о состоянии приложения.
    """
    return HealthResponse(
        app_name=container.settings.app.name,
        app_version=container.settings.app.version,
        profile_mode=container.settings.runtime.mode.value,
        backend=container.backend.value,
        project_root=str(container.settings.project_root),
    )