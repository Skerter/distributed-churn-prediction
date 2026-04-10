from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from xgboost import XGBClassifier

from src.churn.app.settings import Settings


def prepare_features_target(df: pd.DataFrame, settings: Settings, logger) -> tuple[pd.DataFrame, pd.Series]:
    """Подготовка признаков и целевой переменной для обучения модели.

    Args:
        df (pd.DataFrame): DataFrame с обработанными данными для обучения.
        settings (Settings): Настройки для подготовки данных.
        logger (logging.Logger): Логгер для записи информации.

    Raises:
        ValueError: Отсутствует целевая колонка в DataFrame.

    Returns:
        tuple[pd.DataFrame, pd.Series]: X (признаки) и y (целевая переменная) для обучения модели.
    """
    result = df.copy()
    target_column = settings.data.target_column

    drop_columns = list(settings.preprocessing.drop_columns)
    columns_to_drop = [column for column in drop_columns if column in result.columns]
    if columns_to_drop:
        logger.debug("Удаляем служебные колонки из train frame: %s", columns_to_drop)
        result = result.drop(columns=columns_to_drop)

    if target_column not in result.columns:
        logger.error("Целевая колонка %s отсутствует в train frame", target_column)
        raise ValueError(f"В train dataframe отсутствует колонка {target_column}")

    X = result.drop(columns=[target_column])
    y = result[target_column].astype(int)

    logger.debug("Подготовлены X/y: X_shape=%s, y_shape=%s", X.shape, y.shape)
    return X, y


def _build_model(settings: Settings) -> XGBClassifier:
    """Создание экземпляра модели XGBClassifier с параметрами из настроек.

    Args:
        settings (Settings): Настройки, содержащие параметры для модели.

    Returns:
        XGBClassifier: Экземпляр модели XGBClassifier с заданными параметрами.
    """
    return XGBClassifier(
        objective=settings.training.objective,
        eval_metric=settings.training.eval_metric,
        max_depth=settings.training.max_depth,
        learning_rate=settings.training.learning_rate,
        n_estimators=settings.training.n_estimators,
        subsample=settings.training.subsample,
        colsample_bytree=settings.training.colsample_bytree,
        early_stopping_rounds=settings.model.early_stopping_rounds,
        random_state=settings.model.random_state,
        n_jobs=settings.training.n_jobs,
    )


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    """Сохранение данных в формате JSON.

    Args:
        path (Path): Путь к файлу для сохранения.
        payload (dict[str, Any]): Данные для сохранения.
    """
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def train_pandas_model(settings, logger) -> dict[str, object]:
    """Обучение модели на обработанном датасете.

    Args:
        settings (_type_): Настройки для обучения модели.
        logger (_type_): Логгер для записи информации.

    Returns:
        dict[str, object]: Результаты обучения модели.
    """
    train_processed_path = settings.data_processed_dir / "train_processed.parquet"
    model_path = settings.models_dir / f"{settings.model.name}_{settings.model.version}.pkl"

    logger.info("Загрузка обработанного train датасета: %s", train_processed_path)
    df = pd.read_parquet(train_processed_path)
    logger.info("Данные загружены: rows=%s cols=%s", df.shape[0], df.shape[1])

    if "user_id" in df.columns:
        logger.debug("Удаляем служебную колонку user_id")
        df = df.drop(columns=["user_id"])

    logger.debug("Удаляем служебные колонки CHURN и MRG из признаков")
    X = df.drop(columns=["CHURN", "MRG"], errors="ignore")
    y = df["CHURN"].astype(int)

    logger.debug("Матрица признаков: rows=%s cols=%s", X.shape[0], X.shape[1])
    logger.debug("Доля положительного класса: %.6f", y.mean())

    common_params = {
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

    cv_folds = settings.model.cv_folds
    logger.info("Запуск кросс-валидации: cv_folds=%s", cv_folds)

    cv = StratifiedKFold(
        n_splits=cv_folds,
        shuffle=True,
        random_state=settings.model.random_state,
    )

    # без early stopping для cross_val_score
    model_cv = XGBClassifier(**common_params)

    cv_scores = cross_val_score(
        model_cv,
        X,
        y,
        cv=cv,
        scoring="roc_auc",
        n_jobs=1,          # безопаснее для xgboost на Windows
        error_score="raise",
    )

    logger.info("CV ROC-AUC: mean=%.4f std=%.4f", cv_scores.mean(), cv_scores.std())

    logger.info("Запуск финального обучения с early stopping")
    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=settings.model.test_size,
        stratify=y,
        random_state=settings.model.random_state,
    )

    # Здесь early stopping включён
    model = XGBClassifier(
        **common_params,
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

    joblib.dump(model, model_path)
    logger.info("Модель сохранена: %s", model_path)

    return {
        "model_path": str(model_path),
        "train_rows": int(X_train.shape[0]),
        "val_rows": int(X_val.shape[0]),
        "cv_roc_auc_mean": float(cv_scores.mean()),
        "cv_roc_auc_std": float(cv_scores.std()),
        "best_iteration": int(model.best_iteration) if getattr(model, "best_iteration", None) is not None else None,
    }