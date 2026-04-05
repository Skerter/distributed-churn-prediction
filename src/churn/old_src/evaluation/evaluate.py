import pandas as pd
import yaml
import logging
from pathlib import Path
from datetime import datetime
import coloredlogs
import joblib
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    roc_auc_score, average_precision_score, log_loss,
    precision_score, confusion_matrix, roc_curve, precision_recall_curve
)
import seaborn as sns
import numpy as np

from src.churn.infrastructure.config.loader import find_project_root, load_config
from src.churn.infrastructure.logging.factory import get_logger


# ====================== КОНФИГ И ЛОГГЕР ======================
PROJECT_ROOT = find_project_root()
config = load_config(PROJECT_ROOT)
logger = get_logger(
    name=__name__,
    log_dir=PROJECT_ROOT / config["paths"]["logs"],
    log_prefix="evaluate_model",
    level=config["logging"]["level"]
)

# ====================== ПУТИ ======================
DATA_PROCESSED = PROJECT_ROOT / config["paths"]["data_processed"]
MODELS_DIR = PROJECT_ROOT / config["paths"]["models"]
EVAL_PLOTS_DIR = PROJECT_ROOT / config["paths"]["notebooks"] / "eval_plots"

DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
EVAL_PLOTS_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_PROCESSED_PATH = DATA_PROCESSED / "train_processed.parquet"
MODEL_PATH = MODELS_DIR / f"{config['model']['name']}_{config['model']['version']}.pkl"

# ====================== ОЦЕНКА ======================
def evaluate_model() -> None:
    logger.info("Начало оценки модели (локальный прототип)")

    # Загрузка данных и модели
    df = pd.read_parquet(TRAIN_PROCESSED_PATH)
    model = joblib.load(MODEL_PATH)
    logger.info("Модель загружена: %s", MODEL_PATH)
    logger.info("Данные загружены: %s строк", len(df))

    # Подготовка hold-out (val) — повторяем split для reproducibility
    if "user_id" in df.columns:
        df = df.drop("user_id", axis=1)
    X = df.drop(["CHURN", "MRG"], axis=1)
    y = df["CHURN"].astype(int)

    X_train, X_val, y_train, y_val = train_test_split(
        X, y,
        test_size=config["model"]["test_size"],
        stratify=y,
        random_state=config["model"]["random_state"]
    )

    # Предсказания
    y_pred_proba = model.predict_proba(X_val)[:, 1]
    y_pred = model.predict(X_val)

    # ====================== МЕТРИКИ ======================
    roc_auc = roc_auc_score(y_val, y_pred_proba)
    pr_auc = average_precision_score(y_val, y_pred_proba)
    logloss = log_loss(y_val, y_pred_proba)

    # Precision@top-10% (бизнес-метрика для churn: топ клиентов для retention)
    top_k = int(len(y_val) * 0.1)
    threshold = np.sort(y_pred_proba)[::-1][top_k - 1]
    y_pred_top = (y_pred_proba >= threshold).astype(int)
    precision_top = precision_score(y_val, y_pred_top)

    logger.info("Метрики на hold-out:")
    logger.info("  ROC-AUC: %.4f", roc_auc)
    logger.info("  PR-AUC: %.4f", pr_auc)
    logger.info("  LogLoss: %.4f", logloss)
    logger.info("  Precision@top-10%%: %.4f", precision_top)

    # ====================== ГРАФИКИ ======================
    # Confusion Matrix
    cm = confusion_matrix(y_val, y_pred)
    plt.figure(figsize=(6, 4))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
    plt.title("Confusion Matrix")
    plt.ylabel("True")
    plt.xlabel("Predicted")
    plt.savefig(EVAL_PLOTS_DIR / "confusion_matrix.png", dpi=300, bbox_inches="tight")
    plt.close()

    # ROC Curve
    fpr, tpr, _ = roc_curve(y_val, y_pred_proba)
    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, label=f"ROC-AUC = {roc_auc:.4f}")
    plt.plot([0, 1], [0, 1], linestyle="--")
    plt.title("ROC Curve")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.legend()
    plt.savefig(EVAL_PLOTS_DIR / "roc_curve.png", dpi=300, bbox_inches="tight")
    plt.close()

    # PR Curve
    precision, recall, _ = precision_recall_curve(y_val, y_pred_proba)
    plt.figure(figsize=(8, 6))
    plt.plot(recall, precision, label=f"PR-AUC = {pr_auc:.4f}")
    plt.title("Precision-Recall Curve")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.legend()
    plt.savefig(EVAL_PLOTS_DIR / "pr_curve.png", dpi=300, bbox_inches="tight")
    plt.close()

    logger.info("Графики сохранены в %s", EVAL_PLOTS_DIR)
    logger.info("Оценка модели завершена успешно")


if __name__ == "__main__":
    try:
        evaluate_model()
    except Exception as e:
        logger.error("Ошибка при оценке: %s", str(e))
        raise