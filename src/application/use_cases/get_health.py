from src.application.dto.responses import HealthResponse
from src.app.container import AppContainer


def get_health(container: AppContainer) -> HealthResponse:
    """Проверяет состояние приложения и возвращает информацию о его здоровье, включая имя приложения, версию, режим профиля, бэкенд и корневой путь проекта. Эта функция может использоваться для мониторинга состояния приложения и диагностики проблем.

    Args:
        container (AppContainer): Контейнер приложения, содержащий настройки и зависимости, необходимые для получения информации о состоянии приложения.

    Returns:
        HealthResponse: Экземпляр класса HealthResponse, содержащий информацию о состоянии здоровья приложения.
    """
    return HealthResponse(
        app_name=container.settings.app.name,
        app_version=container.settings.app.version,
        profile_mode=container.settings.runtime.mode.value,
        project_root=str(container.settings.project_root),
    )