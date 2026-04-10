from __future__ import annotations

import logging
import sys

import coloredlogs

from src.churn.app.settings import Settings


def build_logger(settings: Settings, name: str | None = None) -> logging.Logger:
    """Создает и настраивает логгер на основе переданных настроек.

    Args:
        settings (Settings): Настройки приложения, содержащие параметры для конфигурации логгера.
        name (str | None, optional): Имя логгера. Если не указано, будет использовано имя из настроек приложения. По умолчанию None.

    Returns:
        logging.Logger: Настроенный логгер, готовый к использованию в приложении.
    """
    logger_name = name or settings.app.name
    logger = logging.getLogger(logger_name)

    if logger.handlers:
        return logger

    level = getattr(logging, settings.logging.level.upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    logger.addHandler(stream_handler)

    if settings.logging.use_coloredlogs:
        coloredlogs.install(
            level=level,
            logger=logger,
            fmt=settings.logging.fmt,
            stream=sys.stdout,
            isatty=True,
            reconfigure=False,
        )
    else:
        stream_handler.setFormatter(logging.Formatter(settings.logging.fmt))

    if settings.logging.log_to_file:
        file_handler = logging.FileHandler(
            settings.logs_dir / "app.log",
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(settings.logging.fmt))
        logger.addHandler(file_handler)

    logger.debug("Логгер инициализирован")
    return logger