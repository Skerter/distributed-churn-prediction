import kagglehub
import os
import shutil
import logging
import coloredlogs  # Для цветовой подсветки логов

# Настраиваем логирование с цветами (не влияет на скорость, только визуал)
logger = logging.getLogger(__name__)
coloredlogs.install(level='INFO', logger=logger, fmt='%(asctime)s [%(levelname)s] %(message)s', 
                    level_styles={'info': {'color': 'green'}, 'error': {'color': 'red', 'bold': True}})

# Определяем пути
data_dir = r'C:\vs_code_projects\distributed-churn-prediction\data'
dataset = 'hamzaghanmi/expresso-churn-prediction-challenge'

if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# Ключевые файлы для проверки
required_files = ['Train.csv', 'Test.csv', 'SampleSubmission.csv']

try:
    # Проверяем, все ли требуемые файлы уже существуют
    if all(os.path.exists(os.path.join(data_dir, file)) for file in required_files):
        logger.info(f"Данные уже загружены в {data_dir}. Пропускаем загрузку.")
        print(f"Данные уже доступны в {data_dir}")
    else:
        # Загружаем датасет (возвращает путь к директории с файлами)
        download_path = kagglehub.dataset_download(dataset)
        logger.info(f"Путь к датасету: {download_path}")

        # Проверяем, является ли путь директорией
        if not os.path.isdir(download_path):
            raise ValueError(f"Ожидалась директория, но получен файл: {download_path}")

        # Создаём целевую папку, если не существует
        os.makedirs(data_dir, exist_ok=True)

        # Копируем только CSV-файлы в data_dir
        copied_files = []
        for file in os.listdir(download_path):
            if file.endswith('.csv'):
                src = os.path.join(download_path, file)
                dst = os.path.join(data_dir, file)
                shutil.copy(src, dst)  # Копируем, чтобы сохранить кэш
                copied_files.append(file)
        
        if not copied_files:
            raise FileNotFoundError("Не найдены CSV-файлы в загруженном датасете.")
        
        logger.info(f"Скопированы файлы: {', '.join(copied_files)} в {data_dir}")
        print(f"Датасет успешно скопирован в {data_dir}")

except Exception as e:
    logger.error(f"Ошибка при загрузке датасета: {str(e)}")
    print(f"Ошибка: {str(e)}. Проверьте права доступа, аккаунт Kaggle или повторите после очистки кэша.")