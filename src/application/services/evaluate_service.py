from __future__ import annotations

from logging import Logger
from pathlib import Path
from typing import Any

import dask.dataframe as dd
import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from dask.distributed import wait
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    log_loss,
    precision_recall_curve,
    precision_score,
    roc_auc_score,
    roc_curve,
)
from xgboost.dask import predict

from src.app.settings import Settings
from src.application.services.train_service import (
    prepare_dask_features_target,
    prepare_features_target,
)


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    """Сохраняет словарь в JSON-файл.

    Args:
        path (Path): Путь к файлу.
        payload (dict[str, Any]): Сохраняемые данные.
    """
    with path.open("w", encoding="utf-8") as file:
        import json

        json.dump(payload, file, ensure_ascii=False, indent=2)


def _plot_confusion_matrix(cm: np.ndarray, output_path: Path) -> None:
    """Строит и сохраняет confusion matrix.

    Args:
        cm (np.ndarray): Матрица ошибок.
        output_path (Path): Путь для сохранения графика.
    """
    plt.figure(figsize=(6, 4))
    plt.imshow(cm, interpolation="nearest")
    plt.title("Confusion Matrix")
    plt.colorbar()
    ticks = np.arange(2)
    plt.xticks(ticks, ["0", "1"])
    plt.yticks(ticks, ["0", "1"])
    plt.xlabel("Predicted")
    plt.ylabel("True")

    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            plt.text(j, i, str(cm[i, j]), ha="center", va="center")

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def _plot_roc_curve(
    fpr: np.ndarray,
    tpr: np.ndarray,
    roc_auc: float,
    output_path: Path,
) -> None:
    """Строит и сохраняет ROC-кривую.

    Args:
        fpr (np.ndarray): False Positive Rate.
        tpr (np.ndarray): True Positive Rate.
        roc_auc (float): Значение ROC-AUC.
        output_path (Path): Путь для сохранения графика.
    """
    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, label=f"ROC-AUC = {roc_auc:.4f}")
    plt.plot([0, 1], [0, 1], linestyle="--")
    plt.title("ROC Curve")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def _plot_pr_curve(
    recall: np.ndarray,
    precision: np.ndarray,
    pr_auc: float,
    output_path: Path,
) -> None:
    """Строит и сохраняет PR-кривую.

    Args:
        recall (np.ndarray): Recall.
        precision (np.ndarray): Precision.
        pr_auc (float): Значение PR-AUC.
        output_path (Path): Путь для сохранения графика.
    """
    plt.figure(figsize=(8, 6))
    plt.plot(recall, precision, label=f"PR-AUC = {pr_auc:.4f}")
    plt.title("Precision-Recall Curve")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def _materialize_dask_vector(vector) -> np.ndarray:
    """Преобразует Dask collection или pandas-объект в одномерный numpy-массив.

    Это нужно, чтобы передавать предсказания и target в sklearn-метрики
    в одном и том же формате.

    Args:
        vector: Dask collection, pandas Series/DataFrame column или numpy-like объект.

    Returns:
        np.ndarray: Одномерный numpy-массив.
    """
    if hasattr(vector, "compute"):
        vector = vector.compute()

    if hasattr(vector, "to_numpy"):
        vector = vector.to_numpy()

    return np.asarray(vector).reshape(-1)


def evaluate_pandas_model(settings: Settings, logger: Logger) -> dict[str, Any]:
    """Оценивает pandas-модель на hold-out выборке.

    Args:
        settings (Settings): Настройки приложения.
        logger (Logger): Логгер для записи этапов оценки.

    Raises:
        FileNotFoundError: Если не найдены parquet или модель.

    Returns:
        dict[str, Any]: Метрики и пути к сохранённым артефактам.
    """
    valid_processed_path = settings.data_processed_dir / "valid_processed.parquet"
    model_path = settings.models_dir / f"{settings.model.name}_{settings.model.version}.pkl"

    if not valid_processed_path.exists():
        logger.error("Не найден valid parquet для оценки: %s", valid_processed_path)
        raise FileNotFoundError(
            f"Не найден valid parquet для оценки: {valid_processed_path}"
        )

    if not model_path.exists():
        logger.error("Не найдена модель для оценки: %s", model_path)
        raise FileNotFoundError(f"Не найдена модель для оценки: {model_path}")

    eval_plots_dir = settings.notebooks_dir / "eval_plots"
    eval_plots_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = settings.models_dir / f"{settings.model.name}_{settings.model.version}_eval_metrics.json"
    confusion_matrix_path = eval_plots_dir / "confusion_matrix.png"
    roc_curve_path = eval_plots_dir / "roc_curve.png"
    pr_curve_path = eval_plots_dir / "pr_curve.png"

    logger.info("Старт оценки pandas-модели на validation set")
    logger.debug("valid_processed_path=%s", valid_processed_path)
    logger.debug("model_path=%s", model_path)

    valid_df = pd.read_parquet(valid_processed_path)
    model = joblib.load(model_path)

    X_val, y_val = prepare_features_target(valid_df, settings, logger)

    logger.info(
        "Validation set загружен: X_val=%s y_val=%s",
        X_val.shape,
        y_val.shape,
    )

    y_pred_proba = model.predict_proba(X_val)[:, 1]
    y_pred = model.predict(X_val)

    roc_auc = float(roc_auc_score(y_val, y_pred_proba))
    pr_auc = float(average_precision_score(y_val, y_pred_proba))
    logloss = float(log_loss(y_val, y_pred_proba))

    top_k = max(1, int(len(y_val) * settings.evaluation.top_fraction))
    threshold = float(np.sort(y_pred_proba)[::-1][top_k - 1])
    y_pred_top = (y_pred_proba >= threshold).astype(int)
    precision_top = float(precision_score(y_val, y_pred_top, zero_division=0))

    logger.info("Метрики validation:")
    logger.info("ROC-AUC: %.6f", roc_auc)
    logger.info("PR-AUC: %.6f", pr_auc)
    logger.info("LogLoss: %.6f", logloss)
    logger.info(
        "Precision@top_fraction(%.2f): %.6f",
        settings.evaluation.top_fraction,
        precision_top,
    )

    cm = confusion_matrix(y_val, y_pred)
    fpr, tpr, _ = roc_curve(y_val, y_pred_proba)
    precision, recall, _ = precision_recall_curve(y_val, y_pred_proba)

    _plot_confusion_matrix(cm, confusion_matrix_path)
    _plot_roc_curve(fpr, tpr, roc_auc, roc_curve_path)
    _plot_pr_curve(recall, precision, pr_auc, pr_curve_path)

    logger.info("Eval plots сохранены в %s", eval_plots_dir)

    metrics = {
        "metrics": {
            "roc_auc": roc_auc,
            "pr_auc": pr_auc,
            "logloss": logloss,
            "precision_top_fraction": precision_top,
            "top_fraction": float(settings.evaluation.top_fraction),
            "top_k": int(top_k),
            "threshold": threshold,
        },
        "artifacts": {
            "metrics_path": str(metrics_path),
            "confusion_matrix_path": str(confusion_matrix_path),
            "roc_curve_path": str(roc_curve_path),
            "pr_curve_path": str(pr_curve_path),
        },
        "validation": {
            "source": str(valid_processed_path),
            "rows": int(len(y_val)),
        },
    }

    _save_json(metrics_path, metrics)
    logger.info("Eval metrics сохранены: %s", metrics_path)

    return metrics


def evaluate_dask_local_model(
    settings: Settings,
    logger: Logger,
    client,
) -> dict[str, Any]:
    """Оценивает модель в режиме dask_local на hold-out выборке.

    Сценарий шага:
    1. Загружаем заранее подготовленный validation parquet через Dask
    2. Подготавливаем Dask X/y
    3. Materialize validation в памяти кластера через persist
    4. Загружаем booster из JSON
    5. Получаем distributed предсказания
    6. Материализуем предсказания и target в numpy
    7. Считаем метрики
    8. Сохраняем plots и metrics JSON

    Args:
        settings (Settings): Настройки приложения.
        logger (Logger): Логгер для записи этапов оценки.
        client: Активный Dask client.

    Raises:
        RuntimeError: Если оценка вызвана без Dask client.
        FileNotFoundError: Если не найдены validation parquet или модель.

    Returns:
        dict[str, Any]: Метрики и пути к сохранённым артефактам.
    """
    if client is None:
        logger.error("evaluate_dask_local_model вызван без Dask client")
        raise RuntimeError("Для Dask local evaluation требуется активный Dask client")

    valid_processed_path = settings.data_processed_dir / "valid_processed.parquet"
    model_path = settings.models_dir / f"{settings.model.name}_{settings.model.version}.json"

    if not valid_processed_path.exists():
        logger.error("Не найден valid parquet для оценки: %s", valid_processed_path)
        raise FileNotFoundError(
            f"Не найден valid parquet для оценки: {valid_processed_path}"
        )

    if not model_path.exists():
        logger.error("Не найдена модель для оценки: %s", model_path)
        raise FileNotFoundError(f"Не найдена модель для оценки: {model_path}")

    eval_plots_dir = settings.notebooks_dir / "eval_plots"
    eval_plots_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = settings.models_dir / f"{settings.model.name}_{settings.model.version}_eval_metrics.json"
    confusion_matrix_path = eval_plots_dir / "confusion_matrix.png"
    roc_curve_path = eval_plots_dir / "roc_curve.png"
    pr_curve_path = eval_plots_dir / "pr_curve.png"

    logger.info("Старт оценки Dask local модели на validation set")
    logger.debug("valid_processed_path=%s", valid_processed_path)
    logger.debug("model_path=%s", model_path)

    valid_ddf = dd.read_parquet(valid_processed_path)

    logger.info(
        "Dask validation parquet загружен: partitions=%s columns=%s",
        valid_ddf.npartitions,
        list(valid_ddf.columns),
    )

    X_val, y_val = prepare_dask_features_target(valid_ddf, settings, logger)

    logger.info("Persist validation набора в памяти кластера")
    X_val, y_val = client.persist([X_val, y_val])
    wait([X_val, y_val])

    val_rows = int(y_val.map_partitions(len).sum().compute())

    logger.info(
        "Validation набор materialized: rows=%s partitions=%s",
        val_rows,
        X_val.npartitions,
    )

    booster = xgb.Booster()
    booster.load_model(model_path)
    logger.info("Booster загружен: %s", model_path)

    logger.info("Запуск distributed predict")
    y_pred_proba = predict(client, booster, X_val)

    y_pred_proba_np = _materialize_dask_vector(y_pred_proba)
    y_val_np = _materialize_dask_vector(y_val)
    y_pred_np = (y_pred_proba_np >= 0.5).astype(int)

    roc_auc = float(roc_auc_score(y_val_np, y_pred_proba_np))
    pr_auc = float(average_precision_score(y_val_np, y_pred_proba_np))
    logloss = float(log_loss(y_val_np, y_pred_proba_np))

    top_k = max(1, int(len(y_val_np) * settings.evaluation.top_fraction))
    threshold = float(np.sort(y_pred_proba_np)[::-1][top_k - 1])
    y_pred_top = (y_pred_proba_np >= threshold).astype(int)
    precision_top = float(precision_score(y_val_np, y_pred_top, zero_division=0))

    logger.info("Метрики validation:")
    logger.info("ROC-AUC: %.6f", roc_auc)
    logger.info("PR-AUC: %.6f", pr_auc)
    logger.info("LogLoss: %.6f", logloss)
    logger.info(
        "Precision@top_fraction(%.2f): %.6f",
        settings.evaluation.top_fraction,
        precision_top,
    )

    cm = confusion_matrix(y_val_np, y_pred_np)
    fpr, tpr, _ = roc_curve(y_val_np, y_pred_proba_np)
    precision, recall, _ = precision_recall_curve(y_val_np, y_pred_proba_np)

    _plot_confusion_matrix(cm, confusion_matrix_path)
    _plot_roc_curve(fpr, tpr, roc_auc, roc_curve_path)
    _plot_pr_curve(recall, precision, pr_auc, pr_curve_path)

    logger.info("Eval plots сохранены в %s", eval_plots_dir)

    metrics = {
        "metrics": {
            "roc_auc": roc_auc,
            "pr_auc": pr_auc,
            "logloss": logloss,
            "precision_top_fraction": precision_top,
            "top_fraction": float(settings.evaluation.top_fraction),
            "top_k": int(top_k),
            "threshold": threshold,
        },
        "artifacts": {
            "metrics_path": str(metrics_path),
            "confusion_matrix_path": str(confusion_matrix_path),
            "roc_curve_path": str(roc_curve_path),
            "pr_curve_path": str(pr_curve_path),
        },
        "validation": {
            "source": str(valid_processed_path),
            "rows": int(len(y_val_np)),
            "partitions": int(X_val.npartitions),
        },
    }

    _save_json(metrics_path, metrics)
    logger.info("Eval metrics сохранены: %s", metrics_path)

    return metrics