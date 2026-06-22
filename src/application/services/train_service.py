from __future__ import annotations

from logging import Logger
from typing import Any

import dask.dataframe as dd
import joblib
import mlflow
import pandas as pd
from dask.distributed import wait
from sklearn.model_selection import StratifiedKFold, cross_val_score
from xgboost import XGBClassifier
from xgboost.dask import DaskXGBClassifier

from src.app.settings import Settings


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
    CV здесь намеренно не запускается, потому что обычная CV поверх заранее
    target-encoded train-part всё ещё даёт оптимистичную оценку.

    Args:
        settings (Settings): Настройки приложения.
        logger (Logger): Логгер для записи этапов обучения.

    Raises:
        FileNotFoundError: Если parquet для обучения не найден.

    Returns:
        dict[str, object]: Сводка по обучению модели.
    """
    train_processed_path = settings.data_processed_dir / "train_processed.parquet"
    valid_processed_path = settings.data_processed_dir / "valid_processed.parquet"
    model_path = settings.models_dir / f"{settings.model.name}_{settings.model.version}.pkl"

    logger.info("Старт pandas-обучения на split")
    logger.debug("train_processed_path=%s", train_processed_path)
    logger.debug("valid_processed_path=%s", valid_processed_path)
    logger.debug("model_path=%s", model_path)

    if not train_processed_path.exists():
        logger.error("Не найден train parquet для обучения: %s", train_processed_path)
        raise FileNotFoundError(
            f"Не найден train parquet для обучения: {train_processed_path}"
        )

    if not valid_processed_path.exists():
        logger.error("Не найден valid parquet для early stopping: %s", valid_processed_path)
        raise FileNotFoundError(
            f"Не найден valid parquet для early stopping: {valid_processed_path}"
        )

    train_df = pd.read_parquet(train_processed_path)
    valid_df = pd.read_parquet(valid_processed_path)

    logger.info(
        "Данные загружены: train_shape=%s, valid_shape=%s",
        train_df.shape,
        valid_df.shape,
    )

    X_train, y_train = prepare_features_target(train_df, settings, logger)
    X_val, y_val = prepare_features_target(valid_df, settings, logger)

    logger.debug("X_train_shape=%s, y_train_shape=%s", X_train.shape, y_train.shape)
    logger.debug("X_val_shape=%s, y_val_shape=%s", X_val.shape, y_val.shape)
    logger.debug("train target rate=%.6f", y_train.mean())
    logger.debug("valid target rate=%.6f", y_val.mean())

    logger.warning(
        "Pandas CV отключена: обычная CV после target encoding может давать leakage. "
        "Основная честная метрика считается на valid_processed.parquet."
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

    try:
        mlflow.set_experiment("churn-prediction")
        with mlflow.start_run():
            mlflow.log_param("runtime_mode", "pandas")
            mlflow.log_param("model_name", settings.model.name)
            mlflow.log_param("model_version", settings.model.version)
            mlflow.log_params(_build_xgb_common_params(settings))
            mlflow.log_metrics({
                "train_rows": X_train.shape[0],
                "val_rows": X_val.shape[0],
                "train_target_rate": float(y_train.mean()),
                "val_target_rate": float(y_val.mean()),
            })
            if best_iteration is not None:
                mlflow.log_metric("best_iteration", float(best_iteration))
    except Exception as exc:
        logger.warning("MLFlow logging failed (non-critical): %s", exc)

    return {
        "model_path": str(model_path),
        "train_rows": int(X_train.shape[0]),
        "val_rows": int(X_val.shape[0]),
        "train_target_rate": float(y_train.mean()),
        "val_target_rate": float(y_val.mean()),
        "cv_roc_auc_mean": None,
        "cv_roc_auc_std": None,
        "cv_note": (
            "CV disabled because target encoding was fitted before CV folds. "
            "Use validation metrics from valid_processed.parquet."
        ),
        "best_iteration": int(best_iteration) if best_iteration is not None else None,
        "validation_source": str(valid_processed_path),
    }


def train_dask_model(
    settings: Settings,
    logger: Logger,
    client,
) -> dict[str, object]:
    """Выполняет полный сценарий обучения модели в режиме dask_local.

    Сценарий шага:
    1. Загружаем train/validation parquet через Dask
    2. Materialize цельные train/validation DataFrame в памяти кластера
    3. Подготавливаем Dask X/y из materialized DataFrame
    4. Обучаем DaskXGBClassifier с early stopping
    5. Сохраняем booster-модель
    6. Возвращаем summary по distributed обучению

    Args:
        settings (Settings): Настройки приложения.
        logger (Logger): Логгер для записи этапов обучения.
        client: Активный Dask client.

    Raises:
        RuntimeError: Если обучение вызвано без Dask client.
        FileNotFoundError: Если parquet для обучения или валидации не найден.

    Returns:
        dict[str, object]: Сводка по distributed обучению модели.
    """
    if client is None:
        logger.error("train_dask_local_model вызван без Dask client")
        raise RuntimeError("Для Dask local training требуется активный Dask client")

    train_processed_path = settings.data_processed_dir / "train_processed.parquet"
    valid_processed_path = settings.data_processed_dir / "valid_processed.parquet"
    model_path = settings.models_dir / f"{settings.model.name}_{settings.model.version}.json"

    logger.info("Старт Dask local обучения на leakage-safe split")
    logger.debug("train_processed_path=%s", train_processed_path)
    logger.debug("valid_processed_path=%s", valid_processed_path)
    logger.debug("model_path=%s", model_path)

    if not train_processed_path.exists():
        logger.error("Не найден train parquet для обучения: %s", train_processed_path)
        raise FileNotFoundError(
            f"Не найден train parquet для обучения: {train_processed_path}"
        )

    if not valid_processed_path.exists():
        logger.error("Не найден valid parquet для early stopping: %s", valid_processed_path)
        raise FileNotFoundError(
            f"Не найден valid parquet для early stopping: {valid_processed_path}"
        )

    train_ddf = dd.read_parquet(train_processed_path)
    valid_ddf = dd.read_parquet(valid_processed_path)

    logger.info(
        "Dask parquet загружены: train_partitions=%s valid_partitions=%s",
        train_ddf.npartitions,
        valid_ddf.npartitions,
    )
    logger.debug("train_columns=%s", list(train_ddf.columns))
    logger.debug("valid_columns=%s", list(valid_ddf.columns))

    logger.info("Materialize цельных train/validation DataFrame перед XGBoost")
    train_ddf, valid_ddf = client.persist([train_ddf, valid_ddf])
    wait([train_ddf, valid_ddf])

    X_train, y_train = prepare_dask_features_target(train_ddf, settings, logger)
    X_val, y_val = prepare_dask_features_target(valid_ddf, settings, logger)

    logger.info(
        "Dask X/y подготовлены: X_train_partitions=%s y_train_partitions=%s "
        "X_val_partitions=%s y_val_partitions=%s",
        X_train.npartitions,
        y_train.npartitions,
        X_val.npartitions,
        y_val.npartitions,
    )

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
        logger.debug("valid target rate=%.6f", val_target_rate)
    except Exception:
        logger.warning("Не удалось вычислить valid target rate")
        val_target_rate = None

    logger.info(
        "Leakage-safe split готов: train_rows=%s val_rows=%s",
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

    logger.debug("Освобождаем persisted train/validation DataFrame")
    client.cancel([train_ddf, valid_ddf], force=True)

    try:
        mlflow.set_experiment("churn-prediction")
        with mlflow.start_run():
            mlflow.log_param("runtime_mode", "dask_local")
            mlflow.log_param("model_name", settings.model.name)
            mlflow.log_param("model_version", settings.model.version)
            mlflow.log_params(_build_xgb_common_params(settings))
            mlflow.log_metrics({
                "train_rows": train_rows,
                "val_rows": val_rows,
                "train_target_rate": train_target_rate or 0.0,
                "val_target_rate": val_target_rate or 0.0,
            })
            if best_iteration is not None:
                mlflow.log_metric("best_iteration", float(best_iteration))
    except Exception as exc:
        logger.warning("MLFlow logging failed (non-critical): %s", exc)

    return {
        "model_path": str(model_path),
        "train_rows": int(train_rows),
        "val_rows": int(val_rows),
        "train_partitions": int(X_train.npartitions),
        "val_partitions": int(X_val.npartitions),
        "train_target_rate": train_target_rate,
        "val_target_rate": val_target_rate,
        "best_iteration": int(best_iteration) if best_iteration is not None else None,
        "validation_source": str(valid_processed_path),
    }
