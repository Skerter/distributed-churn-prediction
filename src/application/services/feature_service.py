from __future__ import annotations

import json
import shutil
from logging import Logger
from pathlib import Path
from typing import Any

import dask
import dask.dataframe as dd
import numpy as np
import pandas as pd
from dask.distributed import wait
from sklearn.model_selection import train_test_split

from src.app.settings import Settings

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


def _build_numeric_fill_values(
    train_df: pd.DataFrame, strategy: str, target_column: str
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
    df: pd.DataFrame, fill_values: dict[str, float], logger, frame_name: str
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
            logger.debug(
                "%s: числовой признак %s, заполняем %s пропусков значением %.6f",
                frame_name,
                column,
                na_count,
                fill_value,
            )
            result[column] = result[column].fillna(fill_value)

    return result


def _fill_categorical_na(
    df: pd.DataFrame, categorical_columns: list[str], fill_value: str, logger, frame_name: str
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
            logger.debug(
                "%s: категориальный признак %s, заполняем %s пропусков значением %s",
                frame_name,
                column,
                na_count,
                fill_value,
            )
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
    valid_df: pd.DataFrame,
    test_df: pd.DataFrame,
    categorical_columns: list[str],
    target_column: str,
    smoothing: float,
    logger: Logger,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Применяет target encoding к указанным категориальным колонкам.

    Args:
        train_df (pd.DataFrame): DataFrame для обучения
        valid_df (pd.DataFrame): DataFrame для валидации
        test_df (pd.DataFrame): DataFrame для тестирования
        categorical_columns (list[str]): Список категориальных колонок
        target_column (str): Название целевой колонки
        smoothing (float): Параметр сглаживания
        logger (logging.Logger): Логгер для записи информации

    Returns:
        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, dict[str, float]]]: Кортеж из обновленных DataFrame и словаря с mapping
    """
    train_result = train_df.copy()
    valid_result = valid_df.copy()
    test_result = test_df.copy()

    prior = float(train_result[target_column].mean())
    logger.debug("Target encoding prior=%.6f", prior)

    mappings: dict[str, dict[str, float]] = {}

    for column in categorical_columns:
        logger.info("Target encoding колонки %s", column)

        stats = train_result.groupby(column)[target_column].agg(["mean", "count"])

        smoothed = (stats["count"] * stats["mean"] + smoothing * prior) / (
            stats["count"] + smoothing
        )

        runtime_mapping = smoothed.to_dict()

        mappings[column] = {str(key): float(value) for key, value in runtime_mapping.items()}

        train_result[column] = (
            train_result[column].map(runtime_mapping).fillna(prior).astype("float64")
        )

        valid_result[column] = (
            valid_result[column].map(runtime_mapping).fillna(prior).astype("float64")
        )

        test_result[column] = (
            test_result[column].map(runtime_mapping).fillna(prior).astype("float64")
        )

        logger.debug(
            "Колонка %s успешно target-encoded. mapping_size=%s",
            column,
            len(runtime_mapping),
        )

    encoder_state = {
        "prior": prior,
        "target_column": target_column,
        "categorical_columns": categorical_columns,
        "mappings": mappings,
    }

    return train_result, valid_result, test_result, encoder_state


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
    processed_dir = settings.data_processed_dir

    train_path = source_dir / settings.data.train_filename
    test_path = source_dir / settings.data.test_filename

    if not train_path.exists():
        logger.error("Train CSV не найден: %s", train_path)
        raise FileNotFoundError(f"Не найден train dataset: {train_path}")

    if not test_path.exists():
        logger.error("Test CSV не найден: %s", test_path)
        raise FileNotFoundError(f"Не найден test dataset: {test_path}")

    maps_path = processed_dir / "target_encoding_maps.json"
    train_processed_path = processed_dir / "train_processed.parquet"
    valid_processed_path = processed_dir / "valid_processed.parquet"
    test_processed_path = processed_dir / "test_processed.parquet"

    logger.info("Старт feature engineering для pandas")
    logger.debug("train_path=%s", train_path)
    logger.debug("test_path=%s", test_path)
    logger.debug("train_processed_path=%s", train_processed_path)
    logger.debug("valid_processed_path=%s", valid_processed_path)
    logger.debug("test_processed_path=%s", test_processed_path)
    logger.debug("maps_path=%s", maps_path)

    raw_train_df = pd.read_csv(train_path)
    test_df = pd.read_csv(test_path)

    logger.info(
        "CSV загружены: raw_train_shape=%s, test_shape=%s",
        raw_train_df.shape,
        test_df.shape,
    )

    categorical_columns = list(settings.preprocessing.categorical_columns)
    target_column = settings.data.target_column

    _validate_columns(
        raw_train_df,
        categorical_columns + FEATURE_REQUIRED_COLUMNS + [target_column],
        "raw_train",
    )
    _validate_columns(
        test_df,
        categorical_columns + FEATURE_REQUIRED_COLUMNS,
        "test",
    )

    train_df, valid_df = train_test_split(
        raw_train_df,
        test_size=settings.model.test_size,
        stratify=raw_train_df[target_column],
        random_state=settings.model.random_state,
    )

    train_df = train_df.copy()
    valid_df = valid_df.copy()
    test_df = test_df.copy()

    logger.info(
        "Train/validation split выполнен до preprocessing: train_shape=%s, valid_shape=%s",
        train_df.shape,
        valid_df.shape,
    )

    fill_values = _build_numeric_fill_values(
        train_df=train_df,
        strategy=settings.preprocessing.fillna_num,
        target_column=target_column,
    )

    logger.debug("Fill values построены только по train-part: %s", fill_values)

    train_df = _fill_numeric_na(train_df, fill_values, logger, "train")
    valid_df = _fill_numeric_na(valid_df, fill_values, logger, "valid")
    test_df = _fill_numeric_na(test_df, fill_values, logger, "test")

    train_df = _fill_categorical_na(
        train_df,
        categorical_columns,
        settings.preprocessing.fillna_cat,
        logger,
        "train",
    )
    valid_df = _fill_categorical_na(
        valid_df,
        categorical_columns,
        settings.preprocessing.fillna_cat,
        logger,
        "valid",
    )
    test_df = _fill_categorical_na(
        test_df,
        categorical_columns,
        settings.preprocessing.fillna_cat,
        logger,
        "test",
    )

    logger.info("Заполнение пропусков завершено")

    train_df = _create_features(train_df)
    valid_df = _create_features(valid_df)
    test_df = _create_features(test_df)

    logger.info(
        "Созданы новые признаки: AVG_REVENUE, RECH_TO_DATA_RATIO, "
        "REGULARITY_SCORE, HAS_TOP_PACK, MISSING_ZONE"
    )

    if settings.preprocessing.target_encoding:
        logger.info(
            "Включён target encoding для колонок: %s",
            categorical_columns,
        )

        train_df, valid_df, test_df, encoder_state = _target_encode(
            train_df=train_df,
            valid_df=valid_df,
            test_df=test_df,
            categorical_columns=categorical_columns,
            target_column=target_column,
            smoothing=settings.preprocessing.smoothing,
            logger=logger,
        )

        _save_json(maps_path, encoder_state)
        logger.info("Маппинги target encoding сохранены: %s", maps_path)
    else:
        logger.warning("Target encoding отключён конфигом")
        encoder_state = {}

    _cleanup_output_path(train_processed_path)
    _cleanup_output_path(valid_processed_path)
    _cleanup_output_path(test_processed_path)

    train_df.to_parquet(train_processed_path, index=False)
    valid_df.to_parquet(valid_processed_path, index=False)
    test_df.to_parquet(test_processed_path, index=False)

    logger.info("Обработанные parquet сохранены")
    logger.debug("train_processed_path=%s", train_processed_path)
    logger.debug("valid_processed_path=%s", valid_processed_path)
    logger.debug("test_processed_path=%s", test_processed_path)

    return {
        "train_shape": list(train_df.shape),
        "valid_shape": list(valid_df.shape),
        "test_shape": list(test_df.shape),
        "artifacts": {
            "train_processed_path": str(train_processed_path),
            "valid_processed_path": str(valid_processed_path),
            "test_processed_path": str(test_processed_path),
            "encoding_maps_path": str(maps_path) if encoder_state else None,
        },
        "split": {
            "test_size": float(settings.model.test_size),
            "random_state": int(settings.model.random_state),
            "stratified_by": target_column,
            "leakage_safe": True,
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


def _validate_columns_by_names(
    columns: list[str], required_columns: list[str], frame_name: str
) -> None:
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


def _build_dask_numeric_fill_values(
    train_ddf: dd.DataFrame, strategy: str, target_column: str, logger: Logger
) -> dict[str, float]:
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
    numeric_columns = [
        column
        for column, dtype in train_ddf.dtypes.items()
        if pd.api.types.is_numeric_dtype(dtype) and column != target_column
    ]

    if strategy not in {"mean", "median"}:
        raise ValueError(
            f"Неизвестная стратегия fillna_num={strategy}. " "Поддерживаются только mean и median."
        )

    tasks = dict()
    for column in numeric_columns:
        if strategy == "mean":
            tasks[column] = train_ddf[column].mean()
        elif strategy == "median":
            # quantile(0.5) возвращает Scalar совместимый с dask.compute();
            # median() требует полной сортировки и не поддерживает lazy-паттерн.
            # T-Digest аппроксимация достаточна для ML-препроцессинга.
            logger.debug("fillna_num=median: используется quantile(0.5) с T-Digest аппроксимацией")
            tasks[column] = train_ddf[column].quantile(0.5)

    fill_values = dask.compute(tasks)[0]
    for column, value in fill_values.items():
        fill_values[column] = float(value)

    logger.debug("Dask fill values рассчитаны: %s", fill_values)
    return fill_values


def _fill_dask_numeric_na(
    ddf: dd.DataFrame, fill_values: dict[str, float], logger: Logger, frame_name: str
) -> dd.DataFrame:
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

        logger.debug(
            "%s: числовой признак %s будет заполнен значением %.6f", frame_name, column, fill_value
        )
        result[column] = result[column].fillna(fill_value)

    return result


def _fill_dask_categorical_na(
    ddf: dd.DataFrame,
    categorical_columns: list[str],
    fill_value: str,
    logger: Logger,
    frame_name: str,
) -> dd.DataFrame:
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
        logger.debug(
            "%s: категориальный признак %s будет заполнен значением %s",
            frame_name,
            column,
            fill_value,
        )
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
    result["RECH_TO_DATA_RATIO"] = result["FREQUENCE_RECH"] / (result["DATA_VOLUME"] + 1)
    result["REGULARITY_SCORE"] = result["REGULARITY"] / 90.0
    result["HAS_TOP_PACK"] = (result["TOP_PACK"] != "missing").astype("int8")
    result["MISSING_ZONE"] = (result["ZONE1"].isna() & result["ZONE2"].isna()).astype("int8")

    return result


def _split_dask_train_valid_by_target(
    ddf: dd.DataFrame,
    target_column: str,
    test_size: float,
    random_state: int,
    logger: Logger,
) -> tuple[dd.DataFrame, dd.DataFrame]:
    """Делит Dask DataFrame на train/validation до preprocessing.

    Dask DataFrame не имеет полного аналога sklearn train_test_split(..., stratify=...),
    поэтому здесь используется class-wise split:
    1. отдельно берём строки каждого класса target;
    2. отдельно делим каждый класс через random_split;
    3. собираем train и validation обратно через dd.concat.

    Args:
        ddf (dd.DataFrame): Входной Dask DataFrame.
        target_column (str): Название целевой колонки для стратификации.
        test_size (float): Доля validation части от общего количества строк.
        random_state (int): Фиксированное значение для генератора случайных чисел
            для воспроизводимости.
        logger (Logger): Логгер для диагностических сообщений.

    Returns:
        tuple[dd.DataFrame, dd.DataFrame]: Кортеж из train и validation Dask DataFrame.
    """
    class_values = ddf[target_column].dropna().unique().compute().tolist()

    if not class_values:
        raise ValueError(f"Не найдены классы в target_column={target_column}")

    logger.info(
        "Dask class-wise split до preprocessing: target_column=%s classes=%s test_size=%.3f",
        target_column,
        class_values,
        test_size,
    )

    train_parts = []
    valid_parts = []

    for class_value in sorted(class_values):
        class_ddf = ddf[ddf[target_column] == class_value]

        class_train_ddf, class_valid_ddf = class_ddf.random_split(
            [1.0 - test_size, test_size],
            random_state=random_state,
        )

        train_parts.append(class_train_ddf)
        valid_parts.append(class_valid_ddf)

        logger.debug("Класс %s добавлен в Dask split", class_value)

    train_ddf = dd.concat(train_parts, interleave_partitions=True)
    valid_ddf = dd.concat(valid_parts, interleave_partitions=True)

    return train_ddf, valid_ddf


def _target_encode_dask(
    train_ddf: dd.DataFrame,
    valid_ddf: dd.DataFrame,
    test_ddf: dd.DataFrame,
    categorical_columns: list[str],
    target_column: str,
    smoothing: float,
    logger: Logger,
) -> tuple[dd.DataFrame, dd.DataFrame, dd.DataFrame, dict[str, Any]]:
    """Выполняет target encoding для Dask DataFrame.

    Важно:
    - статистики target encoding считаются только по train_ddf;
    - один и тот же mapping применяется к train_ddf, valid_ddf и test_ddf;
    - valid_ddf и test_ddf не участвуют в построении mapping.

    Args:
        train_ddf (dd.DataFrame): Train-датасет.
        valid_ddf (dd.DataFrame): Validation-датасет.
        test_ddf (dd.DataFrame): Test-датасет.
        categorical_columns (list[str]): Колонки для target encoding.
        target_column (str): Название целевой колонки.
        smoothing (float): Коэффициент сглаживания.
        logger: Логгер для диагностических сообщений.

    Returns:
        tuple[dd.DataFrame, dd.DataFrame, dd.DataFrame, dict[str, dict[str, float]]]:
            Обновлённые train/valid/test Dask DataFrame и словарь mapping-ов
            для последующего сохранения в JSON.
    """
    train_result = train_ddf
    valid_result = valid_ddf
    test_result = test_ddf

    prior = float(train_result[target_column].mean().compute())
    logger.debug("Dask target encoding prior=%.6f", prior)

    mappings: dict[str, dict[str, float]] = {}

    for column in categorical_columns:
        logger.info("Dask target encoding колонки %s", column)

        stats = train_result.groupby(column)[target_column].agg(["mean", "count"]).compute()

        smoothed = (stats["count"] * stats["mean"] + smoothing * prior) / (
            stats["count"] + smoothing
        )

        runtime_mapping = smoothed.to_dict()

        mappings[column] = {str(key): float(value) for key, value in runtime_mapping.items()}

        train_result[column] = train_result[column].map_partitions(
            lambda series, mapping=runtime_mapping, default_value=prior: (
                series.map(mapping).fillna(default_value).astype("float64")
            ),
            meta=(column, "float64"),
        )

        valid_result[column] = valid_result[column].map_partitions(
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

        logger.debug(
            "Колонка %s успешно target-encoded. mapping_size=%s",
            column,
            len(runtime_mapping),
        )

    encoder_state = {
        "prior": prior,
        "target_column": target_column,
        "categorical_columns": categorical_columns,
        "mappings": mappings,
    }

    return train_result, valid_result, test_result, encoder_state


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
    valid_processed_path = processed_dir / "valid_processed.parquet"
    test_processed_path = processed_dir / "test_processed.parquet"
    maps_path = processed_dir / "target_encoding_maps.json"

    logger.info("Старт feature engineering для dask_local")
    logger.debug("train_path=%s", train_path)
    logger.debug("test_path=%s", test_path)
    logger.debug("train_processed_path=%s", train_processed_path)
    logger.debug("valid_processed_path=%s", valid_processed_path)
    logger.debug("test_processed_path=%s", test_processed_path)
    logger.debug("maps_path=%s", maps_path)

    raw_train_ddf = dd.read_csv(train_path, assume_missing=True, blocksize="64MB")
    test_ddf = dd.read_csv(test_path, assume_missing=True, blocksize="64MB")

    logger.info(
        "CSV открыты через Dask: raw_train_partitions=%s, test_partitions=%s",
        raw_train_ddf.npartitions,
        test_ddf.npartitions,
    )

    categorical_columns = list(settings.preprocessing.categorical_columns)
    target_column = settings.data.target_column

    _validate_columns_by_names(
        list(raw_train_ddf.columns),
        categorical_columns + FEATURE_REQUIRED_COLUMNS + [target_column],
        "raw_train",
    )
    _validate_columns_by_names(
        list(test_ddf.columns),
        categorical_columns + FEATURE_REQUIRED_COLUMNS,
        "test",
    )

    train_ddf, valid_ddf = _split_dask_train_valid_by_target(
        ddf=raw_train_ddf,
        target_column=target_column,
        test_size=settings.model.test_size,
        random_state=settings.model.random_state,
        logger=logger,
    )

    logger.info(
        "Dask train/validation split выполнен до preprocessing: train_partitions=%s, valid_partitions=%s",
        train_ddf.npartitions,
        valid_ddf.npartitions,
    )

    fill_values = _build_dask_numeric_fill_values(
        train_ddf=train_ddf,
        strategy=settings.preprocessing.fillna_num,
        target_column=target_column,
        logger=logger,
    )

    logger.debug("Dask fill values построены только по train-part: %s", fill_values)

    train_ddf = _fill_dask_numeric_na(train_ddf, fill_values, logger, "train")
    valid_ddf = _fill_dask_numeric_na(valid_ddf, fill_values, logger, "valid")
    test_ddf = _fill_dask_numeric_na(test_ddf, fill_values, logger, "test")

    train_ddf = _fill_dask_categorical_na(
        train_ddf,
        categorical_columns,
        settings.preprocessing.fillna_cat,
        logger,
        "train",
    )
    valid_ddf = _fill_dask_categorical_na(
        valid_ddf,
        categorical_columns,
        settings.preprocessing.fillna_cat,
        logger,
        "valid",
    )
    test_ddf = _fill_dask_categorical_na(
        test_ddf,
        categorical_columns,
        settings.preprocessing.fillna_cat,
        logger,
        "test",
    )

    logger.info("Dask заполнение пропусков завершено")

    train_ddf = _create_dask_features(train_ddf)
    valid_ddf = _create_dask_features(valid_ddf)
    test_ddf = _create_dask_features(test_ddf)

    logger.info(
        "Созданы новые признаки: AVG_REVENUE, RECH_TO_DATA_RATIO, "
        "REGULARITY_SCORE, HAS_TOP_PACK, MISSING_ZONE"
    )

    if settings.preprocessing.target_encoding:
        logger.info(
            "Включён Dask target encoding для колонок: %s",
            categorical_columns,
        )

        train_ddf, valid_ddf, test_ddf, encoder_state = _target_encode_dask(
            train_ddf=train_ddf,
            valid_ddf=valid_ddf,
            test_ddf=test_ddf,
            categorical_columns=categorical_columns,
            target_column=target_column,
            smoothing=settings.preprocessing.smoothing,
            logger=logger,
        )

        _save_json(maps_path, encoder_state)
        logger.info("Маппинги Dask target encoding сохранены: %s", maps_path)
    else:
        logger.warning("Target encoding отключён конфигом")
        encoder_state = {}

    logger.info("Persist графа feature engineering в памяти кластера")
    train_ddf, valid_ddf, test_ddf = client.persist([train_ddf, valid_ddf, test_ddf])
    wait([train_ddf, valid_ddf, test_ddf])

    _cleanup_output_path(train_processed_path)
    _cleanup_output_path(valid_processed_path)
    _cleanup_output_path(test_processed_path)

    logger.info("Сохранение Dask parquet datasets")
    train_ddf.to_parquet(train_processed_path, write_index=False)
    valid_ddf.to_parquet(valid_processed_path, write_index=False)
    test_ddf.to_parquet(test_processed_path, write_index=False)

    train_rows = _count_dask_rows(train_ddf)
    valid_rows = _count_dask_rows(valid_ddf)
    test_rows = _count_dask_rows(test_ddf)

    logger.info(
        "Dask feature engineering завершён успешно: train_rows=%s, valid_rows=%s, test_rows=%s",
        train_rows,
        valid_rows,
        test_rows,
    )

    logger.debug("Освобождаем persisted Dask feature engineering collections")
    client.cancel([train_ddf, valid_ddf, test_ddf], force=True)

    logger.info(
        "Dask feature engineering завершён успешно: train_rows=%s, valid_rows=%s, test_rows=%s",
        train_rows,
        valid_rows,
        test_rows,
    )

    return {
        "train_shape": [int(train_rows), len(train_ddf.columns)],
        "valid_shape": [int(valid_rows), len(valid_ddf.columns)],
        "test_shape": [int(test_rows), len(test_ddf.columns)],
        "partitions": {
            "train": int(train_ddf.npartitions),
            "valid": int(valid_ddf.npartitions),
            "test": int(test_ddf.npartitions),
        },
        "artifacts": {
            "train_processed_path": str(train_processed_path),
            "valid_processed_path": str(valid_processed_path),
            "test_processed_path": str(test_processed_path),
            "encoding_maps_path": str(maps_path) if encoder_state else None,
        },
        "split": {
            "test_size": float(settings.model.test_size),
            "random_state": int(settings.model.random_state),
            "stratified_by": target_column,
            "strategy": "dask_class_wise_random_split",
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
