import kagglehub
import os
import shutil
import logging
import coloredlogs  # Для цветовой подсветки логов

from config import DATA_DIR, DATASET_PATH_FROM_KAGGLE

# Настраиваем логирование с цветами (не влияет на скорость, только визуал)
logger = logging.getLogger(__name__)
coloredlogs.install(level='INFO', logger=logger, fmt='%(asctime)s [%(levelname)s] %(message)s', 
                    level_styles={'info': {'color': 'green'}, 'error': {'color': 'red', 'bold': True}})

if not os.path.exists(DATA_DIR):
    logger.info(f'Создана папка {DATA_DIR}')
    os.makedirs(DATA_DIR)

# Ключевые файлы для проверки
required_files = ['Train.csv', 'Test.csv', 'SampleSubmission.csv']

try:
    # Проверяем, все ли требуемые файлы уже существуют
    if all(os.path.exists(os.path.join(DATA_DIR, file)) for file in required_files):
        logger.info(f"Данные уже загружены в {DATA_DIR}. Пропускаем загрузку.")
        print(f"Данные уже доступны в {DATA_DIR}")
    else:
        # Загружаем датасет (возвращает путь к директории с файлами)
        download_path = kagglehub.DATASET_PATH_FROM_KAGGLE_download(DATASET_PATH_FROM_KAGGLE)
        logger.info(f"Путь к датасету: {download_path}")

        # Проверяем, является ли путь директорией
        if not os.path.isdir(download_path):
            raise ValueError(f"Ожидалась директория, но получен файл: {download_path}")

        # Создаём целевую папку, если не существует
        os.makedirs(DATA_DIR, exist_ok=True)

        # Копируем только CSV-файлы в DATA_DIR
        copied_files = []
        for file in os.listdir(download_path):
            if file.endswith('.csv'):
                src = os.path.join(download_path, file)
                dst = os.path.join(DATA_DIR, file)
                shutil.copy(src, dst)  # Копируем, чтобы сохранить кэш
                copied_files.append(file)
        
        if not copied_files:
            logger.error("Не найдены CSV-файлы в загруженном датасете.")
            raise FileNotFoundError("Не найдены CSV-файлы в загруженном датасете.")
        
        logger.info(f"Скопированы файлы: {', '.join(copied_files)} в {DATA_DIR}")
        print(f"Датасет успешно скопирован в {DATA_DIR}")

except Exception as e:
    logger.error(f"Ошибка при загрузке датасета: {str(e)}")
    print(f"Ошибка: {str(e)}. Проверьте права доступа, аккаунт Kaggle или повторите после очистки кэша.")