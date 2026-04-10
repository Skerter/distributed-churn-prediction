from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    log_loss,
    precision_recall_curve,
    precision_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split

from src.churn.app.settings import Settings
from src.churn.application.services.train_service import prepare_features_target


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    """Сохранение данных в формате JSON.

    Args:
        path (Path): Путь к файлу для сохранения.
        payload (dict[str, Any]): Данные для сохранения.
    """
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _plot_confusion_matrix(cm: np.ndarray, output_path: Path) -> None:
    """Построение и сохранение графика confusion matrix.

    Args:
        cm (np.ndarray): Матрица ошибок для построения графика.
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


def _plot_roc_curve(fpr: np.ndarray, tpr: np.ndarray, roc_auc: float, output_path: Path) -> None:
    """Построение и сохранение графика ROC curve.

    Args:
        fpr (np.ndarray): Массив значений False Positive Rate.
        tpr (np.ndarray): Массив значений True Positive Rate.
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


def _plot_pr_curve(recall: np.ndarray, precision: np.ndarray, pr_auc: float, output_path: Path) -> None:
    """Построение и сохранение графика Precision-Recall кривой.

    Args:
        recall (np.ndarray): Массив значений Recall.
        precision (np.ndarray): Массив значений Precision.
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


def evaluate_pandas_model(settings: Settings, logger) -> dict[str, Any]:
    """Оценивает модель на тестовой выборке.

    Args:
        settings (Settings): Настройки для оценки модели
        logger (logging.Logger): Логгер для записи информации

    Raises:
        FileNotFoundError: если не найдены необходимые файлы для оценки (parquet или модель)

    Returns:
        dict[str, Any]: Результаты оценки модели, включая метрики и пути к сохраненным артефактам
    """
    train_processed_path = settings.data_processed_dir / "train_processed.parquet"
    model_path = settings.models_dir / f"{settings.model.name}_{settings.model.version}.pkl"

    if not train_processed_path.exists():
        logger.error("Не найден parquet для оценки: %s", train_processed_path)
        raise FileNotFoundError(f"Не найден parquet для оценки: {train_processed_path}")

    if not model_path.exists():
        logger.error("Не найдена модель для оценки: %s", model_path)
        raise FileNotFoundError(f"Не найдена модель для оценки: {model_path}")

    eval_plots_dir = settings.notebooks_dir / "eval_plots"
    eval_plots_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = settings.models_dir / f"{settings.model.name}_{settings.model.version}_eval_metrics.json"
    confusion_matrix_path = eval_plots_dir / "confusion_matrix.png"
    roc_curve_path = eval_plots_dir / "roc_curve.png"
    pr_curve_path = eval_plots_dir / "pr_curve.png"

    logger.info("Старт оценки модели")
    logger.debug("train_processed_path=%s", train_processed_path)
    logger.debug("model_path=%s", model_path)

    df = pd.read_parquet(train_processed_path)
    model = joblib.load(model_path)

    X, y = prepare_features_target(df, settings, logger)

    _, X_val, _, y_val = train_test_split(
        X,
        y,
        test_size=settings.model.test_size,
        stratify=y,
        random_state=settings.model.random_state,
    )

    logger.info("Сформирован hold-out для оценки: X_val=%s y_val=%s", X_val.shape, y_val.shape)

    y_pred_proba = model.predict_proba(X_val)[:, 1]
    y_pred = model.predict(X_val)

    roc_auc = float(roc_auc_score(y_val, y_pred_proba))
    pr_auc = float(average_precision_score(y_val, y_pred_proba))
    logloss = float(log_loss(y_val, y_pred_proba))

    top_k = max(1, int(len(y_val) * settings.evaluation.top_fraction))
    threshold = float(np.sort(y_pred_proba)[::-1][top_k - 1])
    y_pred_top = (y_pred_proba >= threshold).astype(int)
    precision_top = float(precision_score(y_val, y_pred_top, zero_division=0))

    logger.info("Метрики hold-out:")
    logger.info("ROC-AUC: %.6f", roc_auc)
    logger.info("PR-AUC: %.6f", pr_auc)
    logger.info("LogLoss: %.6f", logloss)
    logger.info("Precision@top_fraction(%.2f): %.6f", settings.evaluation.top_fraction, precision_top)

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
            "rows": int(len(y_val)),
        },
    }

    _save_json(metrics_path, metrics)
    logger.info("Eval metrics сохранены: %s", metrics_path)

    return metrics