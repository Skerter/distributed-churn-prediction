import json
import dask.dataframe as dd
import pandas as pd
import shutil
import os

from src.utils.config import find_project_root, load_config
from src.utils.logger import get_logger
from src.utils.file_utils import safe_remove


# ====================== КОНФИГ И ЛОГГЕР ======================
PROJECT_ROOT = find_project_root()
config = load_config(PROJECT_ROOT)
logger = get_logger(
    name=__name__,
    log_dir=PROJECT_ROOT / config["paths"]["logs"],
    log_prefix="feature_engineering_dask",
    level=config["logging"]["level"]
)


# ====================== ПУТИ ======================
DATA_SOURCE = PROJECT_ROOT / config["paths"]["data_source"]
DATA_PROCESSED = PROJECT_ROOT / config["paths"]["data_processed"]

DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

TRAIN_PATH = DATA_SOURCE / "Train.csv"
TEST_PATH = DATA_SOURCE / "Test.csv"
TRAIN_PROCESSED_PATH = DATA_PROCESSED / "train_processed.parquet"
TEST_PROCESSED_PATH = DATA_PROCESSED / "test_processed.parquet"
MAPS_PATH = DATA_PROCESSED / "target_encoding_maps.json"


# ====================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======================
def fill_numeric_na_dask(df: dd.DataFrame, strategy: str = "median", target: str = "CHURN") -> dd.DataFrame:
    """Заполняем пропуски в числовых колонках"""
    # Определяем числовые колонки (метаданные, без compute)
    num_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df.dtypes[col]) and col != target]

    logger.debug("Числовые колонки для fillna: %s", num_cols)

    if strategy == 'median':
        values  = df[num_cols].quantile(0.5).compute()
        
    elif strategy == 'mean':
        values  = df[num_cols].mean().compute()

    for col in num_cols:
        if strategy == "median":
            fill_value = values[col]
            logger.debug("Заполняем %s медианой: %s", col, fill_value)
        elif strategy == "mean":
            fill_value = values[col]
            logger.debug("Заполняем %s средним: %s", col, fill_value)
        else:
            logger.error("Неизвестная стратегия fillna_num: %s", strategy)
            raise ValueError(f"Только median/mean поддерживаются, получено: {strategy}")

        df[col] = df[col].fillna(fill_value)

    return df


def fill_categorical_na_dask(df: dd.DataFrame, cat_cols: list, fill_value: str = "missing") -> dd.DataFrame:
    """Заполняем пропуски в категориальных колонках"""
    for col in cat_cols:
        # если categorical — добавляем новую категорию
        if str(df[col].dtype) == "category":
            df[col] = df[col].cat.add_categories([fill_value])
        df[col] = df[col].fillna(fill_value)
        logger.debug("Заполняем %s значением '%s'", col, fill_value)
    return df


def create_features_dask(df: dd.DataFrame) -> dd.DataFrame:
    """Создаём новые признаки на Dask"""
    df = df.assign(
        AVG_REVENUE=lambda x: x["REVENUE"] / (x["FREQUENCE"] + 1),
        RECH_TO_DATA_RATIO=lambda x: x["FREQUENCE_RECH"] / (x["DATA_VOLUME"] + 1),
        REGULARITY_SCORE=lambda x: x["REGULARITY"] / 90.0,
        HAS_TOP_PACK=lambda x: (x["TOP_PACK"] != "missing").astype(int),
        MISSING_ZONE=lambda x: (x[["ZONE1", "ZONE2"]].isnull().all(axis=1)).astype(int)
    )
    logger.debug("Созданы признаки: AVG_REVENUE, RECH_TO_DATA_RATIO, REGULARITY_SCORE, HAS_TOP_PACK, MISSING_ZONE")
    return df


def target_encode_dask(train: dd.DataFrame, test: dd.DataFrame, cols: list, target: str, smoothing: float) -> tuple[dd.DataFrame, dd.DataFrame, dict]:
    """Target Encoding на Dask с учётом сглаживания и сохранением маппингов"""
    logger.info("Запуск Target Encoding для колонок: %s", cols)
    prior = train[target].mean().compute()  # глобальный prior
    maps = {}

    for col in cols:
        # Вычисляем статистику (groupby на train)
        stats = train.groupby(col)[target].agg(["mean", "count"]).compute()
        smoothed = (stats["count"] * stats["mean"] + smoothing * prior) / (stats["count"] + smoothing)
        mapping = smoothed.to_dict()
        mapping["__UNKNOWN__"] = prior

        # Применяем маппинг (lazy)
        train[col] = (
            train[col]
            .astype("object")
            .map(mapping, meta=(col, "float64"))
            .fillna(prior)
        )

        test[col] = (
            test[col]
            .astype("object")
            .map(mapping, meta=(col, "float64"))
            .fillna(prior)
        )

        maps[col] = mapping
        logger.debug("Target Encoding для %s завершён (prior = %.4f)", col, prior)

    return train, test, maps


def save_encoding_maps(path: str, maps: dict) -> None:
    """Сохраняем маппинги в JSON"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(maps, f, ensure_ascii=False, indent=2)
    logger.info("Маппинги Target Encoding сохранены: %s", path)


# ====================== ОСНОВНАЯ ЛОГИКА ======================
def feature_engineering_dask() -> None:
    """Главная функция для построения признаков на Dask"""
    logger.info("Начало feature engineering на Dask")

    # Типы данных для эффективности (из датасета Expresso)
    dtypes = {
        'user_id': 'object',
        'REGION': 'category',
        'TENURE': 'category',
        'MONTANT': 'float64',
        'FREQUENCE_RECH': 'float64',
        'REVENUE': 'float64',
        'ARPU_SEGMENT': 'float64',
        'FREQUENCE': 'float64',
        'DATA_VOLUME': 'float64',
        'ON_NET': 'float64',
        'ORANGE': 'float64',
        'TIGO': 'float64',
        'ZONE1': 'float64',
        'ZONE2': 'float64',
        'MRG': 'object',
        'REGULARITY': 'int64',
        'TOP_PACK': 'category',
        'FREQ_TOP_PACK': 'float64',
        'CHURN': 'int8'
    }

    train_df = dd.read_csv(TRAIN_PATH, dtype=dtypes, blocksize="64MB")
    test_df = dd.read_csv(TEST_PATH, dtype=dtypes, blocksize="64MB")  # CHURN отсутствует
    test_df = test_df.repartition(npartitions=train_df.npartitions)

    logger.info(f"Загружено: Train = {train_df.npartitions} partitions, Test = {test_df.npartitions} partitions")
    
    # Persist для ускорения
    train_df = train_df.persist()
    test_df = test_df.persist()

    cat_cols = config["preprocessing"]["categorical_columns"]
    smoothing = config["preprocessing"]["smoothing"]

    logger.info("Заполнение пропусков...")
    train_df = fill_numeric_na_dask(train_df, config["preprocessing"]["fillna_num"], "CHURN")
    test_df = fill_numeric_na_dask(test_df, config["preprocessing"]["fillna_num"], "CHURN")
    train_df = fill_categorical_na_dask(train_df, cat_cols, config["preprocessing"]["fillna_cat"])
    test_df = fill_categorical_na_dask(test_df, cat_cols, config["preprocessing"]["fillna_cat"])

    logger.info("Создание новых признаков...")
    train_df = create_features_dask(train_df)
    test_df = create_features_dask(test_df)

    if config["preprocessing"]["target_encoding"]:
        train_df, test_df, target_enc_maps = target_encode_dask(
            train_df, test_df, cat_cols, target="CHURN", smoothing=smoothing
        )
        save_encoding_maps(MAPS_PATH, target_enc_maps)

    logger.info("Удаление старых Parquet файлов из %s", DATA_PROCESSED)
    del_train_processed = safe_remove(TRAIN_PROCESSED_PATH)
    del_test_processed = safe_remove(TEST_PROCESSED_PATH)
    if not del_train_processed and not del_test_processed:
        logger.info("Старых Parquet файлов не было, или они уже были удалены")

    train_df.to_parquet(TRAIN_PROCESSED_PATH, engine="pyarrow", write_index=False)
    test_df.to_parquet(TEST_PROCESSED_PATH, engine="pyarrow", write_index=False)

    logger.info("Данные сохранены:")
    logger.info("  - %s", TRAIN_PROCESSED_PATH)
    logger.info("  - %s", TEST_PROCESSED_PATH)
    logger.info("Feature engineering на Dask завершён успешно")


if __name__ == "__main__":
    from dask.distributed import Client

    with Client(n_workers=4, threads_per_worker=1, memory_limit="4GB") as client:
        logger.info(f"Dask Client запущен: {client}")
        try:
            feature_engineering_dask()
        except Exception as e:
            logger.error(f"Ошибка в feature engineering на Dask: {e}")
            raise