from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.churn.app.settings import Settings


FEATURE_REQUIRED_COLUMNS = [
    "REVENUE",
    "FREQUENCE",
    "FREQUENCE_RECH",
    "DATA_VOLUME",
    "REGULARITY",
    "TOP_PACK",
    "ZONE1",
    "ZONE2",
]


def _validate_columns(
    df: pd.DataFrame,
    required_columns: list[str],
    frame_name: str,
) -> None:
    """Проверяет наличие обязательных колонок в DataFrame.

    Args:
        df (pd.DataFrame): DataFrame для проверки
        required_columns (list[str]): Список обязательных колонок
        frame_name (str): Имя DataFrame для логирования

    Raises:
        ValueError: если какие-либо обязательные колонки отсутствуют
    """
    missing = sorted(set(required_columns) - set(df.columns))
    if missing:
        raise ValueError(f"В {frame_name} отсутствуют обязательные колонки: {missing}")


def _build_numeric_fill_values(
    train_df: pd.DataFrame,
    strategy: str,
    target_column: str,
) -> dict[str, float]:
    """Строит значения для заполнения пропусков в числовых колонках.

    Args:
        train_df (pd.DataFrame): DataFrame для построения значений
        strategy (str): Стратегия заполнения (mean или median)
        target_column (str): Название целевой колонки

    Raises:
        ValueError: если стратегия заполнения неизвестна

    Returns:
        dict[str, float]: Словарь со значениями для заполнения пропусков
    """
    numeric_columns = train_df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_columns = [col for col in numeric_columns if col != target_column]

    fill_values: dict[str, float] = {}

    for column in numeric_columns:
        if strategy == "median":
            fill_values[column] = float(train_df[column].median())
        elif strategy == "mean":
            fill_values[column] = float(train_df[column].mean())
        else:
            raise ValueError(
                f"Неизвестная стратегия fillna_num={strategy}. "
                "Поддерживаются только mean и median."
            )

    return fill_values


def _fill_numeric_na(
    df: pd.DataFrame,
    fill_values: dict[str, float],
    logger,
    frame_name: str,
) -> pd.DataFrame:
    """Заполняет пропуски в числовых колонках DataFrame.

    Args:
        df (pd.DataFrame): DataFrame для заполнения
        fill_values (dict[str, float]): Словарь со значениями для заполнения
        logger (logging.Logger): Логгер для записи информации
        frame_name (str): Имя DataFrame для логирования

    Returns:
        pd.DataFrame: DataFrame с заполненными пропусками
    """
    result = df.copy()

    for column, fill_value in fill_values.items():
        if column not in result.columns:
            continue

        na_count = int(result[column].isna().sum())
        if na_count > 0:
            logger.debug("%s: числовой признак %s, заполняем %s пропусков значением %.6f",
                         frame_name, column, na_count, fill_value)
            result[column] = result[column].fillna(fill_value)

    return result


def _fill_categorical_na(
    df: pd.DataFrame,
    categorical_columns: list[str],
    fill_value: str,
    logger,
    frame_name: str,
) -> pd.DataFrame:
    """Заполняет пропуски в категориальных колонках DataFrame.

    Args:
        df (pd.DataFrame): DataFrame для заполнения
        categorical_columns (list[str]): Список категориальных колонок
        fill_value (str): Значение для заполнения пропусков
        logger (logging.Logger): Логгер для записи информации
        frame_name (str): Имя DataFrame для логирования

    Returns:
        pd.DataFrame: DataFrame с заполненными пропусками
    """
    result = df.copy()

    for column in categorical_columns:
        na_count = int(result[column].isna().sum())
        if na_count > 0:
            logger.debug("%s: категориальный признак %s, заполняем %s пропусков значением %s",
                         frame_name, column, na_count, fill_value)
        result[column] = result[column].fillna(fill_value)

    return result


def _create_features(df: pd.DataFrame) -> pd.DataFrame:
    """Создаёт новые признаки на основе существующих.

    Args:
        df (pd.DataFrame): DataFrame для создания признаков

    Returns:
        pd.DataFrame: DataFrame с созданными признаками
    """
    result = df.copy()

    result["AVG_REVENUE"] = result["REVENUE"] / (result["FREQUENCE"] + 1)
    result["RECH_TO_DATA_RATIO"] = result["FREQUENCE_RECH"] / (result["DATA_VOLUME"] + 1)
    result["REGULARITY_SCORE"] = result["REGULARITY"] / 90.0
    result["HAS_TOP_PACK"] = (result["TOP_PACK"] != "missing").astype(int)
    result["MISSING_ZONE"] = (result[["ZONE1", "ZONE2"]].isnull().all(axis=1)).astype(int)

    return result


def _target_encode(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    categorical_columns: list[str],
    target_column: str,
    smoothing: float,
    logger,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, float]]]:
    """Применяет target encoding к указанным категориальным колонкам.

    Args:
        train_df (pd.DataFrame): DataFrame для обучения
        test_df (pd.DataFrame): DataFrame для тестирования
        categorical_columns (list[str]): Список категориальных колонок
        target_column (str): Название целевой колонки
        smoothing (float): Параметр сглаживания
        logger (logging.Logger): Логгер для записи информации

    Returns:
        tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, float]]]: Кортеж из обновленных DataFrame и словаря с mapping
    """
    train_result = train_df.copy()
    test_result = test_df.copy()

    prior = float(train_result[target_column].mean())
    logger.debug("Target encoding prior=%.6f", prior)

    mappings: dict[str, dict[str, float]] = {}

    for column in categorical_columns:
        logger.info("Target encoding колонки %s", column)

        stats = train_result.groupby(column)[target_column].agg(["mean", "count"])
        smoothed = (stats["count"] * stats["mean"] + smoothing * prior) / (stats["count"] + smoothing)

        mapping = {str(key): float(value) for key, value in smoothed.to_dict().items()}
        mappings[column] = mapping

        train_result[column] = train_result[column].map(smoothed).fillna(prior)
        test_result[column] = test_result[column].map(smoothed).fillna(prior)

        logger.debug("Колонка %s успешно target-encoded. Уникальных значений=%s",
                     column, len(mapping))

    return train_result, test_result, mappings


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    """Сохраняет словарь в JSON файл.

    Args:
        path (Path): Путь для сохранения JSON файла
        payload (dict[str, Any]): Словарь для сохранения
    """
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def run_pandas_feature_engineering(settings: Settings, logger) -> dict[str, Any]:
    """Выполняет полный цикл feature engineering для pandas.

    Args:
        settings (Settings): Настройки для feature engineering
        logger (_type_): Логгер для записи информации

    Raises:
        FileNotFoundError: если исходные CSV файлы не найдены

    Returns:
        dict[str, Any]: Словарь с результатами feature engineering
    """
    source_dir = settings.data_source_dir
    processed_dir = settings.data_processed_dir
    processed_dir.mkdir(parents=True, exist_ok=True)

    train_path = source_dir / settings.data.train_filename
    test_path = source_dir / settings.data.test_filename
    maps_path = processed_dir / "target_encoding_maps.json"
    train_processed_path = processed_dir / "train_processed.parquet"
    test_processed_path = processed_dir / "test_processed.parquet"

    logger.info("Старт feature engineering для pandas")
    logger.debug("train_path=%s", train_path)
    logger.debug("test_path=%s", test_path)

    if not train_path.exists():
        logger.error("Train CSV не найден: %s", train_path)
        raise FileNotFoundError(f"Не найден train dataset: {train_path}")

    if not test_path.exists():
        logger.error("Test CSV не найден: %s", test_path)
        raise FileNotFoundError(f"Не найден test dataset: {test_path}")

    df_train = pd.read_csv(train_path)
    df_test = pd.read_csv(test_path)

    logger.info("CSV загружены: train_shape=%s, test_shape=%s", df_train.shape, df_test.shape)

    categorical_columns = list(settings.preprocessing.categorical_columns)
    target_column = settings.data.target_column

    _validate_columns(df_train, categorical_columns + FEATURE_REQUIRED_COLUMNS + [target_column], "train")
    _validate_columns(df_test, categorical_columns + FEATURE_REQUIRED_COLUMNS, "test")

    fill_values = _build_numeric_fill_values(train_df=df_train, strategy=settings.preprocessing.fillna_num,
                                             target_column=target_column)
    logger.debug("Сформированы fill values для числовых колонок: %s", fill_values)

    df_train = _fill_numeric_na(df_train, fill_values, logger, "train")
    df_test = _fill_numeric_na(df_test, fill_values, logger, "test")

    df_train = _fill_categorical_na(df_train, categorical_columns,
                                    settings.preprocessing.fillna_cat, logger, "train")
    df_test = _fill_categorical_na(df_test, categorical_columns, 
                                   settings.preprocessing.fillna_cat, logger, "test")

    logger.info("Заполнение пропусков завершено")

    df_train = _create_features(df_train)
    df_test = _create_features(df_test)
    logger.info("Созданы новые признаки: AVG_REVENUE, RECH_TO_DATA_RATIO, "
                "REGULARITY_SCORE, HAS_TOP_PACK, MISSING_ZONE")

    if settings.preprocessing.target_encoding:
        logger.info("Включён target encoding для колонок: %s", categorical_columns)
        df_train, df_test, mappings = _target_encode(
            train_df=df_train,
            test_df=df_test,
            categorical_columns=categorical_columns,
            target_column=target_column,
            smoothing=settings.preprocessing.smoothing,
            logger=logger,
        )
        _save_json(maps_path, mappings)
        logger.info("Маппинги target encoding сохранены: %s", maps_path)
    else:
        logger.warning("Target encoding отключён конфигом")
        mappings = {}

    df_train.to_parquet(train_processed_path, index=False)
    df_test.to_parquet(test_processed_path, index=False)

    logger.info("Обработанные parquet сохранены")
    logger.debug("train_processed_path=%s", train_processed_path)
    logger.debug("test_processed_path=%s", test_processed_path)

    return {
        "train_shape": list(df_train.shape),
        "test_shape": list(df_test.shape),
        "artifacts": {
            "train_processed_path": str(train_processed_path),
            "test_processed_path": str(test_processed_path),
            "encoding_maps_path": str(maps_path) if mappings else None,
        },
        "feature_flags": {
            "target_encoding": settings.preprocessing.target_encoding,
            "created_features": [
                "AVG_REVENUE",
                "RECH_TO_DATA_RATIO",
                "REGULARITY_SCORE",
                "HAS_TOP_PACK",
                "MISSING_ZONE",
            ],
        },
    }