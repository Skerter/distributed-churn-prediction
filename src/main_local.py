import argparse
from datetime import datetime

from src.data.download_dataset import download_dataset
from src.features.feature_engineering_local import feature_engineering
from src.models.train_local import train_model
from src.evaluation.evaluate import evaluate_model

from src.utils.config import find_project_root, load_config
from src.utils.logger import get_logger


# ====================== КОНФИГ И ЛОГГЕР ======================
PROJECT_ROOT = find_project_root()
config = load_config(PROJECT_ROOT)
logger = get_logger(
    name=__name__,
    log_dir=PROJECT_ROOT / config["paths"]["logs"],
    log_prefix="main_local",
    level=config["logging"]["level"]
)

# ====================== ОСНОВНАЯ ЛОГИКА ======================
def run_pipeline(args):
    start_time = datetime.now()
    logger.info("Запуск локального пайплайна (end-to-end)")

    if not args.skip_load:
        logger.info("Шаг 1: Загрузка данных")
        download_dataset()

    if not args.skip_features:
        logger.info("Шаг 2: Feature Engineering")
        feature_engineering()

    if not args.skip_train:
        logger.info("Шаг 3: Обучение модели")
        train_model()

    if not args.skip_eval:
        logger.info("Шаг 4: Оценка модели")
        evaluate_model()

    end_time = datetime.now()
    runtime = end_time - start_time
    logger.info("Пайплайн завершён успешно. Время выполнения: %s", runtime)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Локальный end-to-end ML-пайплайн для churn prediction")
    parser.add_argument("--skip-load", action="store_true", help="Пропустить загрузку данных")
    parser.add_argument("--skip-features", action="store_true", help="Пропустить feature engineering")
    parser.add_argument("--skip-train", action="store_true", help="Пропустить обучение модели")
    parser.add_argument("--skip-eval", action="store_true", help="Пропустить оценку модели")

    args = parser.parse_args()

    try:
        run_pipeline(args)
    except Exception as e:
        logger.error("Ошибка в пайплайне: %s", str(e))
        raise