import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Tuple

from src.churn.infrastructure.config.loader import find_project_root, load_config
from src.churn.infrastructure.logging.factory import get_logger
from src.churn.old_src.utils.file_utils import safe_remove

# ====================== КОНФИГ И ЛОГГЕР ======================
PROJECT_ROOT = find_project_root()
config = load_config(PROJECT_ROOT)
logger = get_logger(
    name=__name__,
    log_dir=PROJECT_ROOT / config["paths"]["logs"],
    log_prefix="feature_engineering_local",
    level=config["logging"]["level"]
)

# ====================== ПУТИ ======================
DATA_SOURCE = PROJECT_ROOT / config["paths"]["data_source"]
DATA_PROCESSED = PROJECT_ROOT / config["paths"]["data_processed"]
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

TRAIN_PATH = DATA_SOURCE / "Train.csv"
TEST_PATH = DATA_SOURCE / "Test.csv"
MAPS_PATH = DATA_PROCESSED / 'target_encoding_maps.json'
TRAIN_PROCESSED_PATH = DATA_PROCESSED / 'train_processed.parquet'
TEST_PROCESSED_PATH = DATA_PROCESSED / 'test_processed.parquet'


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """Создание новых признаков + максимальное логирование"""

    logger.info("Запуск create_features()")
    df = df.copy()

    try:
        df["AVG_REVENUE"] = df["REVENUE"] / (df["FREQUENCE"] + 1)
        logger.debug("Создан AVG_REVENUE")

        df["RECH_TO_DATA_RATIO"] = df["FREQUENCE_RECH"] / (df["DATA_VOLUME"] + 1)
        logger.debug("Создан RECH_TO_DATA_RATIO")

        df["REGULARITY_SCORE"] = df["REGULARITY"] / 90.0
        logger.debug("Создан REGULARITY_SCORE")

        df["HAS_TOP_PACK"] = (df["TOP_PACK"] != "missing").astype(int)
        logger.debug("Создан HAS_TOP_PACK")

        df["MISSING_ZONE"] = (df[["ZONE1", "ZONE2"]].isnull().all(axis=1)).astype(int)
        logger.debug("Создан MISSING_ZONE")

        logger.info("Создано 5 новых признаков успешно | shape = %s", df.shape)
        return df
    except Exception as e:
        logger.error("Ошибка в create_features: %s", str(e))
        logger.critical("Пайплайн прерван на этапе feature creation")
        raise


def fill_numeric_na(df: pd.DataFrame, strategy: str = "median", target: str = "CHURN") -> pd.DataFrame:
    """Заполнение числовых NA"""

    logger.info("fill_numeric_na() | strategy = %s", strategy)
    df = df.copy()

    try:
        num_cols = df.select_dtypes(include=[np.number]).columns.drop([target], errors="ignore")
        logger.debug("Числовые колонки: %s", num_cols.tolist())

        for col in num_cols:
            if strategy == "median":
                fill_value = df[col].median()
            elif strategy == "mean":
                fill_value = df[col].mean()
            else:
                logger.error("Неизвестная стратегия fillna_num: %s", strategy)
                raise ValueError(f"Недопустимая стратегия: {strategy}")

            old_na = df[col].isna().sum()
            df[col] = df[col].fillna(fill_value)
            logger.debug("Заполнено %d NA в %s → значение %.4f", old_na, col, fill_value)

        logger.info("Числовые NA заполнены | shape = %s", df.shape)
        return df
    except Exception as e:
        logger.warning("Ошибка fill_numeric_na (продолжаем с fallback): %s", str(e))
        # Fallback: заполняем 0
        for col in df.select_dtypes(include=[np.number]).columns:
            df[col] = df[col].fillna(0)
        return df


def fill_categorical_na(df: pd.DataFrame, cat_cols: list, fill_value: str = "missing") -> pd.DataFrame:
    """Заполнение категориальных NA"""

    logger.info("fill_categorical_na() | fill_value = %s", fill_value)
    df = df.copy()

    for col in cat_cols:
        if col not in df.columns:
            logger.warning("Колонка %s отсутствует в df → пропускаем", col)
            continue
        old_na = df[col].isna().sum()
        df[col] = df[col].fillna(fill_value)
        logger.debug("Заполнено %d NA в категориальной колонке %s", old_na, col)

    logger.info("Категориальные NA заполнены")
    return df


def target_encode(train: pd.DataFrame, test: pd.DataFrame, cols: list, target: str, smoothing: float) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Target Encoding с логированием и защитой от неизвестных категорий"""

    logger.info("Начало Target Encoding | smoothing = %.1f | колонки: %s", smoothing, cols)
    prior = train[target].mean()
    maps = {}

    for col in cols:
        if col not in train.columns:
            logger.error("Колонка %s отсутствует в train → пропускаем", col)
            continue

        stats = train.groupby(col)[target].agg(["mean", "count"])
        smoothed = (stats["count"] * stats["mean"] + smoothing * prior) / (stats["count"] + smoothing)
        mapping = smoothed.to_dict()
        mapping["__UNKNOWN__"] = prior

        train[col] = train[col].map(mapping).fillna(prior)
        test[col] = test[col].map(mapping).fillna(prior)

        maps[col] = mapping
        logger.debug("Target Encoding завершён для %s | уникальных значений: %d", col, len(mapping))

    logger.info("Target Encoding завершён успешно")
    return train, test, maps


def save_encoding_maps(path: Path, maps: dict) -> None:
    """Сохранение маппингов с отказоустойчивостью"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(maps, f, ensure_ascii=False, indent=2)
        logger.info("Маппинги Target Encoding сохранены: %s", path)
    except Exception as e:
        logger.error("Не удалось сохранить маппинги: %s", str(e))


def validate_columns(df: pd.DataFrame, required_cols: list) -> None:
    """Валидация колонок"""
    missing = set(required_cols) - set(df.columns)
    if missing:
        logger.critical("Отсутствуют обязательные колонки: %s", missing)
        raise ValueError(f"Missing columns: {missing}")
    logger.debug("Валидация колонок пройдена")


def feature_engineering() -> None:
    """Основная функция для построения признаков на локальной машине (Pandas)"""

    logger.info("Начало локального feature engineering")

    # ====================== ЗАГРУЗКА ДАННЫХ ======================
    try:
        if not TRAIN_PATH.exists() or not TEST_PATH.exists():
            logger.critical("CSV файлы не найдены! Проверьте %s", DATA_SOURCE)
            raise FileNotFoundError("Train.csv или Test.csv отсутствуют")

        df_train = pd.read_csv(TRAIN_PATH)
        df_test = pd.read_csv(TEST_PATH)
        logger.info("Загружено: Train %s строк, Test %s строк", len(df_train), len(df_test))
    except Exception as e:
        logger.critical("КРИТИЧЕСКАЯ ОШИБКА загрузки данных: %s", str(e))
        raise

    # ====================== ПРЕДОБРАБОТКА ======================
    cat_cols = config['preprocessing']['categorical_columns']
    try:
        logger.info("Этап 1: Заполнение пропусков")
        df_train = fill_numeric_na(df_train, config["preprocessing"]["fillna_num"], "CHURN")
        df_test = fill_numeric_na(df_test, config["preprocessing"]["fillna_num"], "CHURN")

        df_train = fill_categorical_na(df_train, cat_cols, config['preprocessing']['fillna_cat'])
        df_test = fill_categorical_na(df_test, cat_cols, config['preprocessing']['fillna_cat'])
        logger.info("Пропуски заполнены успешно")
    except Exception as e:
        logger.error("Ошибка предобработки: %s (продолжаем)", str(e))

    # ====================== ВАЛИДАЦИЯ ======================
    validate_columns(df_train, cat_cols + ["CHURN"])

    # ====================== СОЗДАНИЕ ПРИЗНАКОВ ======================
    try:
        logger.info("Этап 2: Feature Engineering")
        df_train = create_features(df_train)
        df_test = create_features(df_test)
    except Exception as e:
        logger.critical("Критическая ошибка создания признаков: %s", str(e))
        raise

    # ====================== TARGET ENCODING ======================
    if config['preprocessing']['target_encoding']:
        try:
            logger.info("Этап 3: Target Encoding")
            df_train, df_test, target_enc_maps = target_encode(df_train, df_test, cat_cols,
                                                               "CHURN", config['preprocessing']['smoothing'])
            save_encoding_maps(MAPS_PATH, target_enc_maps)
        except Exception as e:
            logger.error("Target Encoding упал → используем оригинальные категории: %s", str(e))
            # Fallback: ничего не делаем, оставляем оригинальные категориальные признаки

    # ====================== СОХРАНЕНИЕ ======================
    try:
        logger.info("Этап 4: Сохранение в Parquet")
        logger.info("Удаление старых Parquet файлов из %s", DATA_PROCESSED)
        del_train_processed = safe_remove(TRAIN_PROCESSED_PATH)
        del_test_processed = safe_remove(TEST_PROCESSED_PATH)
        if not del_train_processed and not del_test_processed:
            logger.info("Старых Parquet файлов не было, или они уже были удалены")
        df_train.to_parquet(TRAIN_PROCESSED_PATH, index=False)
        df_test.to_parquet(TEST_PROCESSED_PATH, index=False)
        logger.info("Данные сохранены:")
        logger.info("  → %s", TRAIN_PROCESSED_PATH)
        logger.info("  → %s", TEST_PROCESSED_PATH)
    except Exception as e:
        logger.critical("Не удалось сохранить Parquet: %s", str(e))
        raise

    logger.info("Локальный feature engineering завершён успешно")


if __name__ == "__main__":
    try:
        feature_engineering()
    except Exception as e:
        logger.critical("КРИТИЧЕСКАЯ ОШИБКА В ПАЙПЛАЙНЕ: %s", str(e), exc_info=True)
        raise