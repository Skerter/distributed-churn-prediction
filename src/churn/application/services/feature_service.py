from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from logging import Logger

import dask
import dask.dataframe as dd
import numpy as np
import pandas as pd
from dask.distributed import wait

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


def _validate_columns(df: pd.DataFrame, required_columns: list[str], frame_name: str) -> None:
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


def _build_numeric_fill_values(train_df: pd.DataFrame, strategy: str, target_column: str) -> dict[str, float]:
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
            raise ValueError(f"Неизвестная стратегия fillna_num={strategy}. "
                             "Поддерживаются только mean и median.")

    return fill_values


def _fill_numeric_na(df: pd.DataFrame, fill_values: dict[str, float], logger, frame_name: str) -> pd.DataFrame:
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


def _fill_categorical_na(df: pd.DataFrame, categorical_columns: list[str],
                         fill_value: str, logger, frame_name: str) -> pd.DataFrame:
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


def _target_encode(train_df: pd.DataFrame, test_df: pd.DataFrame,categorical_columns: list[str],
                   target_column: str, smoothing: float, logger) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, float]]]:
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


def run_pandas_feature_engineering(settings: Settings, logger: Logger) -> dict[str, Any]:
    """Выполняет полный цикл feature engineering для pandas.

    Args:
        settings (Settings): Настройки для feature engineering
        logger (logging.Logger): Логгер для записи информации

    Raises:
        FileNotFoundError: если исходные CSV файлы не найдены

    Returns:
        dict[str, Any]: Словарь с результатами feature engineering
    """
    logger.debug("Сборка путей к данным для pandas feature engineering")

    source_dir = settings.data_source_dir
    train_path = source_dir / settings.data.train_filename
    test_path = source_dir / settings.data.test_filename
    
    if not train_path.exists():
        logger.error("Train CSV не найден: %s", train_path)
        raise FileNotFoundError(f"Не найден train dataset: {train_path}")

    if not test_path.exists():
        logger.error("Test CSV не найден: %s", test_path)
        raise FileNotFoundError(f"Не найден test dataset: {test_path}")
    
    processed_dir = settings.data_processed_dir
    maps_path = processed_dir / "target_encoding_maps.json"
    train_processed_path = processed_dir / "train_processed.parquet"
    test_processed_path = processed_dir / "test_processed.parquet"

    logger.info("Старт feature engineering для pandas")
    logger.debug("train_path=%s", train_path)
    logger.debug("test_path=%s", test_path)
    logger.debug("train_processed_path=%s", train_processed_path)
    logger.debug("test_processed_path=%s", test_processed_path)
    logger.debug("maps_path=%s", maps_path)

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


def _validate_columns_by_names(columns: list[str], required_columns: list[str], frame_name: str) -> None:
    """Проверяет наличие обязательных колонок в Dask DataFrame по списку имён.

    Args:
        columns (list[str]): Фактические имена колонок входного набора данных.
        required_columns (list[str]): Список обязательных колонок.
        frame_name (str): Имя набора данных для текста ошибки.

    Raises:
        ValueError: Если в наборе данных отсутствуют обязательные колонки.
    """
    missing = sorted(set(required_columns) - set(columns))
    if missing:
        raise ValueError(f"В {frame_name} отсутствуют обязательные колонки: {missing}")


def _cleanup_output_path(path: Path) -> None:
    """Удаляет существующий файл или директорию перед записью артефакта.

    Для pandas parquet обычно сохраняется как одиночный файл, а для Dask
    to_parquet() чаще создаёт parquet-dataset, то есть директорию с набором
    part-файлов. Поэтому здесь нужна универсальная очистка и файла, и папки.

    Args:
        path (Path): Путь к артефакту, который будет перезаписан.
    """
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _count_dask_rows(ddf: dd.DataFrame) -> int:
    """Подсчитывает количество строк в Dask DataFrame.

    Args:
        ddf (dd.DataFrame): Dask DataFrame для подсчёта строк.

    Returns:
        int: Количество строк.
    """
    return int(ddf.map_partitions(len).sum().compute())


def _build_dask_numeric_fill_values(train_ddf: dd.DataFrame, strategy: str,
                                    target_column: str, logger: Logger) -> dict[str, float]:
    """Строит значения для заполнения пропусков в числовых колонках Dask DataFrame.

    Args:
        train_ddf (dd.DataFrame): Train-датасет в формате Dask DataFrame.
        strategy (str): Стратегия заполнения, поддерживаются `mean` и `median`.
        target_column (str): Имя целевой колонки, которую не нужно включать
            в вычисление fill values.
        logger (Logger): Логгер для диагностических сообщений.

    Raises:
        ValueError: Передана неподдерживаемая стратегия заполнения.

    Returns:
        dict[str, float]: Словарь вида {column_name: fill_value}.
    """
    numeric_columns = [column for column, dtype in train_ddf.dtypes.items()
                       if pd.api.types.is_numeric_dtype(dtype) and column != target_column]

    if strategy not in {"mean", "median"}:
        raise ValueError(f"Неизвестная стратегия fillna_num={strategy}. "
                         "Поддерживаются только mean и median.")
    
    tasks = dict()
    for column in numeric_columns:
        if strategy == "mean":
            tasks[column] = train_ddf[column].mean()
        elif strategy == "median":
            tasks[column] = train_ddf[column].median()
            
    fill_values = dask.compute(tasks)[0]
    for column, value in fill_values.items():
        fill_values[column] = float(value)
    
    logger.debug("Dask fill values рассчитаны: %s", fill_values)
    return fill_values


def _fill_dask_numeric_na(ddf: dd.DataFrame, fill_values: dict[str, float],
                          logger: Logger, frame_name: str) -> dd.DataFrame:
    """Заполняет пропуски в числовых колонках Dask DataFrame.

    Args:
        ddf (dd.DataFrame): Входной Dask DataFrame.
        fill_values (dict[str, float]): Словарь со значениями заполнения.
        logger: Логгер для диагностических сообщений.
        frame_name (str): Имя набора данных для логирования.

    Returns:
        dd.DataFrame: Новый Dask DataFrame с заполненными числовыми пропусками.
    """
    result = ddf

    for column, fill_value in fill_values.items():
        if column not in result.columns:
            continue

        logger.debug("%s: числовой признак %s будет заполнен значением %.6f",
                     frame_name, column, fill_value)
        result[column] = result[column].fillna(fill_value)

    return result


def _fill_dask_categorical_na(ddf: dd.DataFrame, categorical_columns: list[str],
                              fill_value: str, logger: Logger, frame_name: str) -> dd.DataFrame:
    """Заполняет пропуски в категориальных колонках Dask DataFrame.

    Args:
        ddf (dd.DataFrame): Входной Dask DataFrame.
        categorical_columns (list[str]): Список категориальных колонок.
        fill_value (str): Значение, которым заполняются пропуски.
        logger: Логгер для диагностических сообщений.
        frame_name (str): Имя набора данных для логирования.

    Returns:
        dd.DataFrame: Новый Dask DataFrame с заполненными категориальными пропусками.
    """
    result = ddf

    for column in categorical_columns:
        logger.debug("%s: категориальный признак %s будет заполнен значением %s",
                     frame_name, column, fill_value)
        result[column] = result[column].fillna(fill_value)

    return result


def _create_dask_features(ddf: dd.DataFrame) -> dd.DataFrame:
    """Создаёт новые признаки в Dask DataFrame.

    Args:
        ddf (dd.DataFrame): Входной Dask DataFrame.

    Returns:
        dd.DataFrame: Dask DataFrame с новыми признаками.
    """
    result = ddf.copy()

    result["AVG_REVENUE"] = result["REVENUE"] / (result["FREQUENCE"] + 1)
    result["RECH_TO_DATA_RATIO"] = (result["FREQUENCE_RECH"] / (result["DATA_VOLUME"] + 1))
    result["REGULARITY_SCORE"] = result["REGULARITY"] / 90.0
    result["HAS_TOP_PACK"] = (result["TOP_PACK"] != "missing").astype("int8")
    result["MISSING_ZONE"] = (result["ZONE1"].isna() & result["ZONE2"].isna()).astype("int8")

    return result


def _target_encode_dask(train_ddf: dd.DataFrame, test_ddf: dd.DataFrame, categorical_columns: list[str], target_column: str,
                        smoothing: float, logger: Logger) -> tuple[dd.DataFrame, dd.DataFrame, dict[str, dict[str, float]]]:
    """Выполняет target encoding для Dask DataFrame.

    Архитектурно здесь важно следующее:
    1. статистики считаются только по train;
    2. mapping строится централизованно;
    3. затем mapping распределённо применяется к train и test через partitions.

    Args:
        train_ddf (dd.DataFrame): Train-датасет.
        test_ddf (dd.DataFrame): Test-датасет.
        categorical_columns (list[str]): Колонки для target encoding.
        target_column (str): Название целевой колонки.
        smoothing (float): Коэффициент сглаживания.
        logger: Логгер для диагностических сообщений.

    Returns:
        tuple[dd.DataFrame, dd.DataFrame, dict[str, dict[str, float]]]:
            Обновлённые train/test Dask DataFrame и словарь mapping-ов
            для последующего сохранения в JSON.
    """
    train_result = train_ddf
    test_result = test_ddf

    prior = float(train_result[target_column].mean().compute())
    logger.debug("Dask target encoding prior=%.6f", prior)

    serializable_mappings: dict[str, dict[str, float]] = {}

    for column in categorical_columns:
        logger.info("Dask target encoding колонки %s", column)

        stats = train_result.groupby(column)[target_column].agg(["mean", "count"]).compute()

        smoothed = (stats["count"] * stats["mean"] + smoothing * prior) / (stats["count"] + smoothing)

        runtime_mapping = smoothed.to_dict()
        json_mapping = {str(key): float(value) for key, value in runtime_mapping.items()}
        serializable_mappings[column] = json_mapping

        train_result[column] = train_result[column].map_partitions(
            lambda series, mapping=runtime_mapping, default_value=prior: (
                series.map(mapping).fillna(default_value).astype("float64")
            ),
            meta=(column, "float64"),
        )

        test_result[column] = test_result[column].map_partitions(
            lambda series, mapping=runtime_mapping, default_value=prior: (
                series.map(mapping).fillna(default_value).astype("float64")
            ),
            meta=(column, "float64"),
        )

        logger.debug("Колонка %s успешно target-encoded. Уникальных значений=%s",
                     column, len(runtime_mapping))

    return train_result, test_result, serializable_mappings


def run_dask_feature_engineering(settings: Settings, logger: Logger, client) -> dict[str, Any]:
    """Выполняет feature engineering в режиме dask_local.

    Эта функция является Dask-эквивалентом `run_pandas_feature_engineering`,
    но использует ленивые и параллельные вычисления Dask. Она отвечает
    только за реализацию одного шага pipeline и не содержит orchestration-логики.

    Args:
        settings (Settings): Настройки приложения.
        logger: Логгер для записи этапов работы.
        client: Активный Dask client, через который выполняются распределённые
            вычисления и persist операций.

    Raises:
        RuntimeError: Если функция вызвана без активного Dask client.
        FileNotFoundError: Если не найдены исходные CSV-файлы.
        ValueError: Если отсутствуют обязательные колонки или передана
            некорректная стратегия заполнения.

    Returns:
        dict[str, Any]: Словарь с метаданными feature engineering и путями
        к созданным артефактам.
    """
    if client is None:
        logger.error("run_dask_feature_engineering вызван без Dask client")
        raise RuntimeError("Для Dask feature engineering требуется активный Dask client")

    logger.debug("Сборка путей к данным для dask_local feature engineering")

    source_dir = settings.data_source_dir
    processed_dir = settings.data_processed_dir

    train_path = source_dir / settings.data.train_filename
    test_path = source_dir / settings.data.test_filename

    if not train_path.exists():
        logger.error("Train CSV не найден: %s", train_path)
        raise FileNotFoundError(f"Не найден train dataset: {train_path}")

    if not test_path.exists():
        logger.error("Test CSV не найден: %s", test_path)
        raise FileNotFoundError(f"Не найден test dataset: {test_path}")

    train_processed_path = processed_dir / "train_processed.parquet"
    test_processed_path = processed_dir / "test_processed.parquet"
    maps_path = processed_dir / "target_encoding_maps.json"

    logger.info("Старт feature engineering для dask_local")
    logger.debug("train_path=%s", train_path)
    logger.debug("test_path=%s", test_path)
    logger.debug("train_processed_path=%s", train_processed_path)
    logger.debug("test_processed_path=%s", test_processed_path)
    logger.debug("maps_path=%s", maps_path)
    
    train_ddf = dd.read_csv(train_path, assume_missing=True, blocksize="64MB")
    test_ddf = dd.read_csv(test_path, assume_missing=True, blocksize="64MB")
    
    logger.info("CSV открыты через Dask: train_partitions=%s, test_partitions=%s",
                train_ddf.npartitions, test_ddf.npartitions)

    categorical_columns = list(settings.preprocessing.categorical_columns)
    target_column = settings.data.target_column
    
    _validate_columns_by_names(
        list(train_ddf.columns),
        categorical_columns + FEATURE_REQUIRED_COLUMNS + [target_column],
        "train",
    )
    _validate_columns_by_names(
        list(test_ddf.columns),
        categorical_columns + FEATURE_REQUIRED_COLUMNS,
        "test",
    )
    
    fill_values = _build_dask_numeric_fill_values(
        train_ddf=train_ddf,
        strategy=settings.preprocessing.fillna_num,
        target_column=target_column,
        logger=logger
    )
    
    train_ddf = _fill_dask_numeric_na(train_ddf, fill_values, logger, "train")
    test_ddf = _fill_dask_numeric_na(test_ddf, fill_values, logger, "test")
    
    train_ddf = _fill_dask_categorical_na(train_ddf, categorical_columns,
                                          settings.preprocessing.fillna_cat, logger, "train")
    test_ddf = _fill_dask_categorical_na(test_ddf, categorical_columns,
                                         settings.preprocessing.fillna_cat, logger, "test")
    
    logger.info("Заполнение пропусков завершено")
    
    train_ddf = _create_dask_features(train_ddf)
    test_ddf = _create_dask_features(test_ddf)
    
    logger.info("Созданы новые признаки: AVG_REVENUE, RECH_TO_DATA_RATIO, "
                "REGULARITY_SCORE, HAS_TOP_PACK, MISSING_ZONE")
    
    if settings.preprocessing.target_encoding:
        logger.info("Включён Dask target encoding для колонок: %s", categorical_columns)

        train_ddf, test_ddf, mappings = _target_encode_dask(
            train_ddf=train_ddf,
            test_ddf=test_ddf,
            categorical_columns=categorical_columns,
            target_column=target_column,
            smoothing=settings.preprocessing.smoothing,
            logger=logger,
        )

        _save_json(maps_path, mappings)
        logger.info("Маппинги Dask target encoding сохранены: %s", maps_path)
    else:
        logger.warning("Target encoding отключён конфигом")
        mappings = {}
    
    logger.info("Persist графа feature engineering в памяти кластера")
    train_ddf = client.persist(train_ddf)
    test_ddf = client.persist(test_ddf)
    wait([train_ddf, test_ddf])
    
    _cleanup_output_path(train_processed_path)
    _cleanup_output_path(test_processed_path)

    logger.info("Сохранение Dask parquet datasets")
    train_ddf.to_parquet(train_processed_path, write_index=False)
    test_ddf.to_parquet(test_processed_path, write_index=False)
    
    train_rows = _count_dask_rows(train_ddf)
    test_rows = _count_dask_rows(test_ddf)
    
    logger.info("Dask feature engineering завершён успешно: train_rows=%s, test_rows=%s",
                train_rows, test_rows)
    
    return {
        "train_shape": [int(train_rows), len(train_ddf.columns)],
        "test_shape": [int(test_rows), len(test_ddf.columns)],
        "partitions": {
            "train": int(train_ddf.npartitions),
            "test": int(test_ddf.npartitions),
        },
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