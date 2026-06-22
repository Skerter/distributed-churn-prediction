class ChurnAppError(Exception):
    """Базовая ошибка приложения."""


class ConfigError(ChurnAppError):
    """Ошибка загрузки или валидации конфигурации."""


class RuntimeModeError(ChurnAppError):
    """Неизвестный runtime mode."""


class PipelineResolutionError(ChurnAppError):
    """Не удалось определить или собрать pipeline."""
