import shutil
import os
from pathlib import Path
from typing import Union

from src.utils.config import find_project_root, load_config
from src.utils.logger import get_logger

# ====================== КОНФИГ И ЛОГГЕР ======================
PROJECT_ROOT = find_project_root()
config = load_config(PROJECT_ROOT)
logger = get_logger(
    name=__name__,
    log_dir=PROJECT_ROOT / config["paths"]["logs"],
    log_prefix="file_utils",
    level=config["logging"]["level"]
)
    
def safe_remove(path: Union[str, Path]) -> bool:
    """
    Безопасно удаляет файл или директорию.
    Возвращает True, если что-то было удалено.
    Полностью защищён от PermissionError / WinError 5.
    """
    path = Path(path).resolve()

    if not path.exists():
        logger.info("safe_remove: ничего не найдено → %s", path)
        return False

    try:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=False)
            logger.warning("Удалена директория: %s", path)
        else:
            path.unlink()
            logger.warning("Удалён файл: %s", path)
        return True

    except PermissionError:
        logger.error("PermissionError (WinError 5) при удалении: %s", path)
        logger.critical("Решение: закройте файл в VS Code / Jupyter / Excel и запустите от администратора")
        return False
    except Exception as e:
        logger.error("Неожиданная ошибка при удалении %s: %s", path, e)
        return False
