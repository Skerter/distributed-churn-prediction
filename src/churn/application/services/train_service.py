from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from xgboost import XGBClassifier

from src.churn.app.settings import Settings


def _to_python_float(value: Any) -> float:
    return float(value)


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
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def train_pandas_model(settings: Settings, logger) -> dict[str, Any]:
    train_processed_path = settings.data_processed_dir / "train_processed.parquet"
    if not train_processed_path.exists():
        logger.error("Не найден parquet для обучения: %s", train_processed_path)
        raise FileNotFoundError(
            f"Не найден parquet для обучения: {train_processed_path}"
        )

    settings.models_dir.mkdir(parents=True, exist_ok=True)
    model_plots_dir = settings.notebooks_dir / "model_plots"
    model_plots_dir.mkdir(parents=True, exist_ok=True)

    model_path = settings.models_dir / (
        f"{settings.model.name}_{settings.model.version}.pkl"
    )
    train_summary_path = settings.models_dir / (
        f"{settings.model.name}_{settings.model.version}_train_summary.json"
    )
    feature_importance_path = model_plots_dir / (
        f"{settings.model.name}_{settings.model.version}_feature_importance.png"
    )

    logger.info("Старт обучения pandas/XGBoost модели")
    logger.debug("train_processed_path=%s", train_processed_path)

    df = pd.read_parquet(train_processed_path)
    logger.info("Parquet загружен: shape=%s", df.shape)

    X, y = prepare_features_target(df, settings, logger)

    logger.info("Запуск кросс-валидации: cv_folds=%s", settings.model.cv_folds)
    cv = StratifiedKFold(
        n_splits=settings.model.cv_folds,
        shuffle=True,
        random_state=settings.model.random_state,
    )

    cv_model = _build_model(settings)
    cv_scores = cross_val_score(
        cv_model,
        X,
        y,
        cv=cv,
        scoring="roc_auc",
        n_jobs=settings.training.n_jobs,
    )

    logger.info(
        "CV ROC-AUC: mean=%.6f std=%.6f",
        cv_scores.mean(),
        cv_scores.std(),
    )

    logger.info("Запуск финального train/validation split")
    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=settings.model.test_size,
        stratify=y,
        random_state=settings.model.random_state,
    )
    logger.debug(
        "Train/val split: X_train=%s X_val=%s y_train=%s y_val=%s",
        X_train.shape,
        X_val.shape,
        y_train.shape,
        y_val.shape,
    )

    model = _build_model(settings)
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    best_iteration = getattr(model, "best_iteration", None)
    logger.info("Финальное обучение завершено. best_iteration=%s", best_iteration)

    joblib.dump(model, model_path)
    logger.info("Модель сохранена: %s", model_path)

    importance = pd.Series(
        model.feature_importances_,
        index=X.columns,
        dtype=float,
    ).sort_values(ascending=False)

    top20 = importance.head(20).sort_values()
    plt.figure(figsize=(12, 8))
    plt.barh(top20.index, top20.values)
    plt.title("Top 20 Feature Importance (XGBoost)")
    plt.xlabel("Importance")
    plt.tight_layout()
    plt.savefig(feature_importance_path, dpi=300, bbox_inches="tight")
    plt.close()

    logger.info("График importance сохранён: %s", feature_importance_path)

    top_features = [
        {"feature": feature, "importance": float(value)}
        for feature, value in importance.head(10).items()
    ]
    for item in top_features[:5]:
        logger.info(
            "Top feature: %s -> %.6f",
            item["feature"],
            item["importance"],
        )

    summary = {
        "cv": {
            "roc_auc_mean": _to_python_float(cv_scores.mean()),
            "roc_auc_std": _to_python_float(cv_scores.std()),
            "scores": [_to_python_float(score) for score in cv_scores],
        },
        "model": {
            "path": str(model_path),
            "best_iteration": int(best_iteration) if best_iteration is not None else None,
        },
        "data": {
            "train_rows": int(X_train.shape[0]),
            "val_rows": int(X_val.shape[0]),
            "n_features": int(X.shape[1]),
        },
        "artifacts": {
            "model_path": str(model_path),
            "train_summary_path": str(train_summary_path),
            "feature_importance_plot": str(feature_importance_path),
        },
        "top_features": top_features,
    }

    _save_json(train_summary_path, summary)
    logger.info("Train summary сохранён: %s", train_summary_path)

    return summary