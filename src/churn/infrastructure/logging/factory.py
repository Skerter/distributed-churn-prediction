import logging
import sys
from pathlib import Path
from datetime import datetime
import coloredlogs
import os


def get_logger(name: str, log_dir: Path, log_prefix: str = "app", level: str = "INFO") -> logging.Logger:
    '''Универсальный настраиваемый логгер с цветами и файловым выводом, адаптированный для работы в Kubernetes и локально
    params:
        name: имя логгера (обычно __name__)
        log_dir: папка для логов
        log_prefix: префикс для имени файла лога (например "build_features")
        level: уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    returns:
        Настроенный логгер для конкретного модуля, который пишет в stdout (для K8s) и в файл (локально)
        '''
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level))

    # 👉 всегда stdout (K8s must-have)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    ))
    logger.addHandler(stream_handler)

    # 👉 включаем файл ТОЛЬКО локально
    if os.getenv("KUBERNETES_SERVICE_HOST") is None:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{log_prefix}_{datetime.now():%Y%m%d_%H%M%S}.log"

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        ))
        logger.addHandler(file_handler)

    coloredlogs.install(
        level=level,
        logger=logger,
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    )

    logger.info("Logger initialized: %s", name)

    return logger