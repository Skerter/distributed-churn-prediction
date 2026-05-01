from __future__ import annotations

from app.settings import Settings


def ensure_project_dirs(settings: Settings) -> None:
    """Обеспечивает существование необходимых директорий для проекта.

    Args:
        settings (Settings): Настройки приложения, содержащие пути к директориям.
    """
    settings.data_source_dir.mkdir(parents=True, exist_ok=True)
    settings.data_processed_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)