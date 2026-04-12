from __future__ import annotations

from logging import Logger
from typing import Any

import joblib
import pandas as pd
import dask.dataframe as dd
from dask.distributed import wait
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from xgboost import XGBClassifier
from xgboost.dask import DaskXGBClassifier

from src.churn.app.settings import Settings


def prepare_features_target(
    df: pd.DataFrame,
    settings: Settings,
    logger: Logger,
) -> tuple[pd.DataFrame, pd.Series]:
    """Подготавливает признаки и целевую переменную для обучения и оценки.

    Функция удаляет служебные колонки, проверяет наличие target-поля
    и формирует матрицу признаков X и вектор целевой переменной y.

    Args:
        df (pd.DataFrame): DataFrame с обработанными данными.
        settings (Settings): Настройки приложения.
        logger (Logger): Логгер для записи этапов подготовки данных.

    Raises:
        ValueError: Если в DataFrame отсутствует целевая колонка.

    Returns:
        tuple[pd.DataFrame, pd.Series]: Признаки X и целевая переменная y.
    """
    result = df.copy()
    target_column = settings.data.target_column

    drop_columns = list(settings.preprocessing.drop_columns)
    columns_to_drop = [column for column in drop_columns if column in result.columns]
    if columns_to_drop:
        logger.debug(
            "Удаляем служебные колонки из frame: %s",
            columns_to_drop,
        )
        result = result.drop(columns=columns_to_drop)

    if target_column not in result.columns:
        logger.error(
            "Целевая колонка %s отсутствует в frame",
            target_column,
        )
        raise ValueError(f"В dataframe отсутствует колонка {target_column}")

    X = result.drop(columns=[target_column])
    y = result[target_column].astype(int)

    logger.debug("Подготовлены X/y: X_shape=%s, y_shape=%s", X.shape, y.shape)
    return X, y


def prepare_dask_features_target(
    ddf: dd.DataFrame,
    settings: Settings,
    logger: Logger,
) -> tuple[dd.DataFrame, dd.Series]:
    """Подготавливает признаки и целевую переменную для Dask local обучения.

    Функция удаляет служебные колонки, проверяет наличие target-поля
    и формирует матрицу признаков X и вектор целевой переменной y.

    Args:
        ddf (dd.DataFrame): Dask DataFrame с обработанными данными.
        settings (Settings): Настройки приложения.
        logger (Logger): Логгер для записи этапов подготовки данных.

    Raises:
        ValueError: Если в Dask DataFrame отсутствует целевая колонка.

    Returns:
        tuple[dd.DataFrame, dd.Series]: Признаки X и целевая переменная y.
    """
    result = ddf
    target_column = settings.data.target_column

    drop_columns = list(settings.preprocessing.drop_columns)
    columns_to_drop = [column for column in drop_columns if column in result.columns]
    if columns_to_drop:
        logger.debug("Удаляем служебные колонки из Dask frame: %s", columns_to_drop)
        result = result.drop(columns=columns_to_drop)

    if target_column not in result.columns:
        logger.error("Целевая колонка %s отсутствует в Dask frame", target_column)
        raise ValueError(f"В Dask dataframe отсутствует колонка {target_column}")

    X = result.drop(columns=[target_column])
    y = result[target_column].astype("int64")

    logger.debug("Подготовлены Dask X/y: columns=%s partitions=%s", list(X.columns), X.npartitions)
    return X, y


def _build_xgb_common_params(settings: Settings) -> dict[str, Any]:
    """Собирает общие параметры XGBoost из настроек проекта.

    Эти параметры одинаково используются и для CV-модели,
    и для финальной модели.

    Args:
        settings (Settings): Настройки приложения.

    Returns:
        dict[str, Any]: Общие параметры XGBoost.
    """
    return {
        "objective": settings.training.objective,
        "eval_metric": settings.training.eval_metric,
        "max_depth": settings.training.max_depth,
        "learning_rate": settings.training.learning_rate,
        "n_estimators": settings.training.n_estimators,
        "subsample": settings.training.subsample,
        "colsample_bytree": settings.training.colsample_bytree,
        "random_state": settings.model.random_state,
        "n_jobs": settings.training.n_jobs,
    }


def _run_pandas_cross_validation(
    X: pd.DataFrame,
    y: pd.Series,
    settings: Settings,
    logger: Logger,
) -> dict[str, float]:
    """Запускает кросс-валидацию для pandas-модели.

    Здесь намеренно не используется early stopping, потому что
    `cross_val_score()` не передаёт validation set внутрь `fit()`.

    Args:
        X (pd.DataFrame): Матрица признаков.
        y (pd.Series): Целевая переменная.
        settings (Settings): Настройки приложения.
        logger (Logger): Логгер для записи этапов кросс-валидации.

    Returns:
        dict[str, float]: Среднее и стандартное отклонение ROC-AUC по CV.
    """
    logger.info("Запуск кросс-валидации: cv_folds=%s", settings.model.cv_folds)

    cv = StratifiedKFold(
        n_splits=settings.model.cv_folds,
        shuffle=True,
        random_state=settings.model.random_state,
    )

    model_cv = XGBClassifier(**_build_xgb_common_params(settings))

    cv_scores = cross_val_score(
        model_cv,
        X,
        y,
        cv=cv,
        scoring="roc_auc",
        n_jobs=1,
        error_score="raise",
    )

    cv_result = {
        "cv_roc_auc_mean": float(cv_scores.mean()),
        "cv_roc_auc_std": float(cv_scores.std()),
    }

    logger.info(
        "CV ROC-AUC: mean=%.4f std=%.4f",
        cv_result["cv_roc_auc_mean"],
        cv_result["cv_roc_auc_std"],
    )
    return cv_result


def _fit_pandas_final_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    settings: Settings,
    logger: Logger,
) -> XGBClassifier:
    """Обучает финальную pandas-модель с early stopping.

    Args:
        X_train (pd.DataFrame): Признаки train-части.
        y_train (pd.Series): Целевая переменная train-части.
        X_val (pd.DataFrame): Признаки validation-части.
        y_val (pd.Series): Целевая переменная validation-части.
        settings (Settings): Настройки приложения.
        logger (Logger): Логгер для записи этапов обучения.

    Returns:
        XGBClassifier: Обученная финальная модель.
    """
    logger.info("Запуск финального обучения с early stopping")

    model = XGBClassifier(
        **_build_xgb_common_params(settings),
        early_stopping_rounds=settings.model.early_stopping_rounds,
    )

    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    logger.info("Финальное обучение завершено")
    logger.info("Лучшая итерация: %s", getattr(model, "best_iteration", None))
    return model


def train_pandas_model(settings: Settings, logger: Logger) -> dict[str, object]:
    """Выполняет полный сценарий обучения pandas-модели.

    Сценарий шага:
    1. Загружаем обработанный parquet
    2. Подготавливаем X/y
    3. Считаем CV
    4. Делаем train/validation split
    5. Обучаем финальную модель
    6. Сохраняем модель
    7. Возвращаем summary по обучению

    Args:
        settings (Settings): Настройки приложения.
        logger (Logger): Логгер для записи этапов обучения.

    Raises:
        FileNotFoundError: Если parquet для обучения не найден.

    Returns:
        dict[str, object]: Сводка по обучению модели.
    """
    train_processed_path = settings.data_processed_dir / "train_processed.parquet"
    model_path = settings.models_dir / f"{settings.model.name}_{settings.model.version}.pkl"

    logger.info("Старт pandas-обучения")
    logger.debug("train_processed_path=%s", train_processed_path)
    logger.debug("model_path=%s", model_path)

    if not train_processed_path.exists():
        logger.error("Не найден parquet для обучения: %s", train_processed_path)
        raise FileNotFoundError(f"Не найден parquet для обучения: {train_processed_path}")

    df = pd.read_parquet(train_processed_path)
    logger.info("Данные загружены: rows=%s cols=%s", df.shape[0], df.shape[1])

    X, y = prepare_features_target(df, settings, logger)

    logger.debug("Матрица признаков: rows=%s cols=%s", X.shape[0], X.shape[1])
    logger.debug("Доля положительного класса: %.6f", y.mean())

    cv_result = _run_pandas_cross_validation(X, y, settings, logger)

    logger.info("Подготовка финального train/validation split: test_size=%.3f", settings.model.test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=settings.model.test_size,
        stratify=y,
        random_state=settings.model.random_state,
    )

    logger.info(
        "Split завершён: X_train=%s X_val=%s y_train=%s y_val=%s",
        X_train.shape,
        X_val.shape,
        y_train.shape,
        y_val.shape,
    )

    model = _fit_pandas_final_model(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        settings=settings,
        logger=logger,
    )

    settings.models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    logger.info("Модель сохранена: %s", model_path)

    best_iteration = getattr(model, "best_iteration", None)

    return {
        "model_path": str(model_path),
        "train_rows": int(X_train.shape[0]),
        "val_rows": int(X_val.shape[0]),
        "cv_roc_auc_mean": cv_result["cv_roc_auc_mean"],
        "cv_roc_auc_std": cv_result["cv_roc_auc_std"],
        "best_iteration": int(best_iteration) if best_iteration is not None else None,
    }


def train_dask_local_model(settings: Settings, logger: Logger, client) -> dict[str, object]:
    """Временная заглушка для Dask local training.

    Функция оставлена в модуле, чтобы не ломать импорт в DaskLocalPipeline
    до реализации полноценного distributed обучения.

    Args:
        settings (Settings): Настройки приложения.
        logger (Logger): Логгер для записи информации.
        client: Активный Dask client.

    Raises:
        NotImplementedError: Dask local training пока не реализован.

    Returns:
        dict[str, object]: Эта функция не возвращает результат в текущей версии.
    """
    logger.error("train_dask_local_model пока не реализован")
    raise NotImplementedError("Dask local training пока не реализован")


def train_dask_local_model(
    settings: Settings,
    logger: Logger,
    client,
) -> dict[str, object]:
    """Выполняет полный сценарий обучения модели в режиме dask_local.

    Сценарий шага:
    1. Загружаем обработанный parquet через Dask
    2. Делаем distributed split через random_split
    3. Подготавливаем Dask X/y
    4. Materialize train/validation в памяти кластера через persist
    5. Обучаем DaskXGBClassifier с early stopping
    6. Сохраняем booster-модель
    7. Возвращаем summary по обучению

    Args:
        settings (Settings): Настройки приложения.
        logger (Logger): Логгер для записи этапов обучения.
        client: Активный Dask client.

    Raises:
        RuntimeError: Если обучение вызвано без Dask client.
        FileNotFoundError: Если parquet для обучения не найден.

    Returns:
        dict[str, object]: Сводка по distributed обучению модели.
    """
    if client is None:
        logger.error("train_dask_local_model вызван без Dask client")
        raise RuntimeError("Для Dask local training требуется активный Dask client")

    train_processed_path = settings.data_processed_dir / "train_processed.parquet"
    model_path = settings.models_dir / f"{settings.model.name}_{settings.model.version}.json"

    logger.info("Старт Dask local обучения")
    logger.debug("train_processed_path=%s", train_processed_path)
    logger.debug("model_path=%s", model_path)

    if not train_processed_path.exists():
        logger.error("Не найден parquet для обучения: %s", train_processed_path)
        raise FileNotFoundError(f"Не найден parquet для обучения: {train_processed_path}")

    ddf = dd.read_parquet(train_processed_path)
    logger.info(
        "Dask parquet загружен: partitions=%s columns=%s",
        ddf.npartitions,
        list(ddf.columns),
    )

    total_rows = int(ddf.map_partitions(len).sum().compute())
    logger.info("Размер набора до split: rows=%s", total_rows)

    logger.info(
        "Подготовка distributed split: train_size=%.3f val_size=%.3f",
        1.0 - settings.model.test_size,
        settings.model.test_size,
    )
    train_ddf, val_ddf = ddf.random_split(
        [1.0 - settings.model.test_size, settings.model.test_size],
        random_state=settings.model.random_state,
    )

    X_train, y_train = prepare_dask_features_target(train_ddf, settings, logger)
    X_val, y_val = prepare_dask_features_target(val_ddf, settings, logger)

    logger.info("Persist train/validation наборов в памяти кластера")
    X_train, y_train, X_val, y_val = client.persist([X_train, y_train, X_val, y_val])
    wait([X_train, y_train, X_val, y_val])

    train_rows = int(y_train.map_partitions(len).sum().compute())
    val_rows = int(y_val.map_partitions(len).sum().compute())

    try:
        train_target_rate = float(y_train.mean().compute())
        logger.debug("train target rate=%.6f", train_target_rate)
    except Exception:
        logger.warning("Не удалось вычислить train target rate")
        train_target_rate = None

    try:
        val_target_rate = float(y_val.mean().compute())
        logger.debug("val target rate=%.6f", val_target_rate)
    except Exception:
        logger.warning("Не удалось вычислить val target rate")
        val_target_rate = None

    logger.info(
        "Split materialized: train_rows=%s val_rows=%s",
        train_rows,
        val_rows,
    )

    model = DaskXGBClassifier(
        **_build_xgb_common_params(settings),
        early_stopping_rounds=settings.model.early_stopping_rounds,
        tree_method="hist",
    )
    model.client = client

    logger.info("Запуск distributed fit DaskXGBClassifier")
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    best_iteration = getattr(model, "best_iteration", None)
    logger.info("Dask local обучение завершено. Лучшая итерация: %s", best_iteration)

    settings.models_dir.mkdir(parents=True, exist_ok=True)
    booster = model.get_booster()
    booster.save_model(model_path)
    logger.info("Booster сохранён: %s", model_path)

    return {
        "model_path": str(model_path),
        "train_rows": int(train_rows),
        "val_rows": int(val_rows),
        "train_partitions": int(X_train.npartitions),
        "val_partitions": int(X_val.npartitions),
        "train_target_rate": train_target_rate,
        "val_target_rate": val_target_rate,
        "best_iteration": int(best_iteration) if best_iteration is not None else None,
    }