import os
import shutil
from pathlib import Path
import kagglehub

from src.churn.infrastructure.config.loader import find_project_root, load_config
from src.churn.infrastructure.logging.factory import get_logger


# ====================== КОНФИГ И ЛОГГЕР ======================
PROJECT_ROOT = find_project_root()
config = load_config(PROJECT_ROOT)
logger = get_logger(
    name=__name__,
    log_dir=PROJECT_ROOT / config["paths"]["logs"],
    log_prefix="load_data",
    level=config["logging"]["level"]
)

# ====================== ПУТИ ======================
DATA_SOURCE = Path(config["paths"]["data_source"])
DATASET_SLUG = config["data"]["dataset_slug"]


# ====================== ОСНОВНАЯ ЛОГИКА ======================
def download_dataset() -> None:
    """Скачивает датасет через kagglehub и копирует CSV в data/source/"""
    DATA_SOURCE.mkdir(parents=True, exist_ok=True)

    required_files = ['Train.csv', 'Test.csv', 'SampleSubmission.csv']

    # Проверяем, всё ли уже есть
    if all((DATA_SOURCE / file).exists() for file in required_files):
        logger.info("Все файлы уже существуют в %s. Загрузка пропущена.", DATA_SOURCE)
        return

    logger.info("Скачиваем датасет: %s", DATASET_SLUG)
    
    # Скачиваем (kagglehub кэширует автоматически)
    download_path = kagglehub.dataset_download(DATASET_SLUG)
    logger.info("Датасет скачан в: %s", download_path)

    if not os.path.isdir(download_path):
        logger.error("Ожидалась директория, получено: %s", download_path)
        raise ValueError(f"Ожидалась директория, получено: {download_path}")

    # Копируем только CSV
    copied = []
    for file in os.listdir(download_path):
        if file.endswith('.csv'):
            src = Path(download_path) / file
            dst = DATA_SOURCE / file
            shutil.copy(src, dst)
            copied.append(file)

    if not copied:
        logger.error("CSV-файлы не найдены!")
        raise FileNotFoundError("Не найдены CSV в датасете")

    logger.info("Успешно скопированы: %s", ", ".join(copied))
    print(f"Датасет успешно загружен в {DATA_SOURCE}")


if __name__ == "__main__":
    try:
        download_dataset()
    except Exception as e:
        logger.error("Ошибка загрузки: %s", str(e))
        print(f"Ошибка: {e}\nПроверь аккаунт Kaggle или удали кэш ~/.cache/kagglehub/")