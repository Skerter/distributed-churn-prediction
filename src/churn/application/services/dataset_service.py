from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from src.churn.app.settings import Settings


def _find_file(root: Path, filename: str) -> Path:
    """Поиск файла с именем filename в директории root и её поддиректориях. Если найдено несколько, возвращает первый по алфавиту.

    Args:
        root (Path): директория для поиска
        filename (str): имя файла для поиска

    Raises:
        FileNotFoundError: если файл не найден

    Returns:
        Path: путь к найденному файлу
    """
    matches = sorted(root.rglob(filename))
    if not matches:
        raise FileNotFoundError(
            f"Файл {filename} не найден в директории скачанного датасета {root}"
        )
    return matches[0]


def ensure_source_dataset(settings: Settings, logger) -> dict[str, Any]:
    """Проверяет наличие исходного датасета и скачивает его при необходимости.

    Args:
        settings (Settings): Настройки приложения
        logger (logging.Logger): Логгер для записи информации

    Raises:
        FileNotFoundError: если исходные CSV файлы не найдены и dataset_slug не задан
        RuntimeError: если не удалось скачать датасет

    Returns:
        dict[str, Any]: Словарь с информацией о состоянии датасета
    """
    source_dir = settings.data_source_dir
    source_dir.mkdir(parents=True, exist_ok=True)

    train_path = source_dir / settings.data.train_filename
    test_path = source_dir / settings.data.test_filename

    logger.info("Проверка исходного датасета в %s", source_dir)
    logger.debug("Ожидаемый train path: %s", train_path)
    logger.debug("Ожидаемый test path: %s", test_path)

    if train_path.exists() and test_path.exists():
        logger.info("Исходные CSV уже доступны, скачивание не требуется")
        return {
            "downloaded": False,
            "train_path": str(train_path),
            "test_path": str(test_path),
        }

    missing_files = [path.name for path in (train_path, test_path) if not path.exists()]
    logger.warning("Часть исходных CSV отсутствует: %s", missing_files)

    if not settings.data.dataset_slug:
        logger.error("dataset_slug не задан, автоскачивание невозможно")
        raise FileNotFoundError("Исходные CSV не найдены и dataset_slug не задан в конфиге")

    try:
        import kagglehub
    except ImportError as exc:
        logger.exception("Не удалось импортировать kagglehub")
        raise RuntimeError("Для автозагрузки датасета требуется установленный kagglehub") from exc

    logger.info("Пробуем скачать/взять из кеша датасет KaggleHub: %s",settings.data.dataset_slug)
    downloaded_root = Path(kagglehub.dataset_download(settings.data.dataset_slug))
    logger.info("KaggleHub вернул директорию: %s", downloaded_root)

    if not train_path.exists():
        source_train = _find_file(downloaded_root, settings.data.train_filename)
        shutil.copy2(source_train, train_path)
        logger.info("Train.csv скопирован: %s -> %s", source_train, train_path)

    if not test_path.exists():
        source_test = _find_file(downloaded_root, settings.data.test_filename)
        shutil.copy2(source_test, test_path)
        logger.info("Test.csv скопирован: %s -> %s", source_test, test_path)

    return {
        "downloaded": True,
        "download_root": str(downloaded_root),
        "train_path": str(train_path),
        "test_path": str(test_path),
    }