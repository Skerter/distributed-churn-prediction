import argparse
from datetime import datetime

from src.data.download_dataset import download_dataset
from src.features.feature_engineering_dask import feature_engineering_dask
from src.models.train_dask import train_model_dask
from src.evaluation.evaluate_dask import evaluate_model_dask

from src.utils.config import find_project_root, load_config
from src.utils.logger import get_logger


# ====================== КОНФИГ И ЛОГГЕР ======================
PROJECT_ROOT = find_project_root()
config = load_config(PROJECT_ROOT)
logger = get_logger(
    name=__name__,
    log_dir=PROJECT_ROOT / config["paths"]["logs"],
    log_prefix="main_dask",
    level=config["logging"]["level"]
)

# ====================== ОСНОВНАЯ ЛОГИКА ======================
def run_pipeline(args):
    start_time = datetime.now()
    logger.info("Запуск DISTRIBUTED пайплайна (Dask end-to-end)")

    if not args.skip_load:
        logger.info("Шаг 1: Скачивание датасета с помощью kagglehub")
        download_dataset()

    if not args.skip_features:
        logger.info("Шаг 2: Feature Engineering (Dask DataFrame + Target Encoding)")
        feature_engineering_dask()

    if not args.skip_train:
        logger.info("Шаг 3: Обучение DaskXGBClassifier (distributed)")
        train_model_dask()

    if not args.skip_eval:
        logger.info("Шаг 4: Оценка модели (Dask + метрики + графики)")
        evaluate_model_dask()

    end_time = datetime.now()
    runtime = end_time - start_time
    logger.info("Dask-пайплайн завершён успешно. Время выполнения: %s", runtime)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DISTRIBUTED end-to-end ML-пайплайн для churn prediction (Dask)")
    parser.add_argument("--skip-load",    action="store_true", help="Пропустить загрузку данных")
    parser.add_argument("--skip-features", action="store_true", help="Пропустить feature engineering")
    parser.add_argument("--skip-train",   action="store_true", help="Пропустить обучение модели")
    parser.add_argument("--skip-eval",    action="store_true", help="Пропустить оценку модели")

    args = parser.parse_args()

    try:
        logger.info("Dask Dashboard: http://localhost:8787) - для мониторинга распределённых задач")
        logger.debug('Аргументы командной строки: %s', args)
        run_pipeline(args)
    except Exception as e:
        logger.error(f"Ошибка в Dask-пайплайне: {e}")
        raise