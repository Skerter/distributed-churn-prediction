import logging
from pathlib import Path
from datetime import datetime
import coloredlogs


def get_logger(name: str, log_dir: Path, log_prefix: str = "app", level: str = "INFO") -> logging.Logger:
    '''Универсальный настраиваемый логгер с цветами и файловым выводом
    params:
        name: имя логгера (обычно __name__)
        log_dir: папка для логов
        log_prefix: префикс для имени файла лога (например "build_features")
        level: уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    returns:
        настроенный логгер для конкретного модуля
        '''

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{log_prefix}_{datetime.now():%Y%m%d_%H%M%S}.log"

    coloredlogs.install(
        level=level,
        logger=logger,
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s"))
    logger.addHandler(file_handler)
    
    logger.info('Логгер %s инициализирован', name)
    logger.debug("Уровень: %s. Логи сохраняются в: %s. ", level, log_file)

    return logger