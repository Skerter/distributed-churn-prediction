import time
import dask.dataframe as dd
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import xgboost as xgb
from sklearn.metrics import (
    roc_auc_score, average_precision_score, log_loss,
    precision_score, confusion_matrix, roc_curve, precision_recall_curve
)
from dask_ml.model_selection import train_test_split

from src.utils.config import find_project_root, load_config
from src.utils.logger import get_logger


# ====================== КОНФИГ И ЛОГГЕР ======================
PROJECT_ROOT = find_project_root()
config = load_config(PROJECT_ROOT)
logger = get_logger(
    name=__name__,
    log_dir=PROJECT_ROOT / config["paths"]["logs"],
    log_prefix="evaluate_dask",
    level=config["logging"]["level"]
)

# ====================== ПУТИ ======================
DATA_PROCESSED = PROJECT_ROOT / config["paths"]["data_processed"]
MODELS_DIR = PROJECT_ROOT / config["paths"]["models"]
EVAL_PLOTS_DIR = PROJECT_ROOT / config["paths"]["notebooks"] / "eval_plots"

DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
EVAL_PLOTS_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_PROCESSED_PATH = DATA_PROCESSED / "train_processed.parquet"
# Используем модель, сохранённую в train_dask.py
MODEL_PATH = MODELS_DIR / f"{config['model']['name']}_{config['model']['version']}_dask.json"


# ====================== ОСНОВНАЯ ЛОГИКА ======================
def evaluate_model_dask() -> None:
    logger.info("Запуск оценки модели на Dask")
    start_time = time.time()

    # Загрузка данных в Dask параллельно по partitions
    df = dd.read_parquet(TRAIN_PROCESSED_PATH)
    logger.info(f"Загружено {df.npartitions} partitions ({len(df)} строк)")

    if "user_id" in df.columns:
        df = df.drop("user_id", axis=1)
    if "MRG" in df.columns:
        df = df.drop("MRG", axis=1)

    X = df.drop("CHURN", axis=1)
    y = df["CHURN"].astype("int8")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=config["model"]["test_size"],
        random_state=config["model"]["random_state"]
    )

    # Persist для ускорения предсказания
    X_test = X_test.persist()
    y_test = y_test.persist()

    logger.info("Hold-out выборка подготовлена (distributed)")

    # Booster — универсальный формат из DaskXGBClassifier.save_model)
    booster = xgb.Booster()
    booster.load_model(str(MODEL_PATH))
    logger.info(f"Модель загружена: {MODEL_PATH}")

    # Переводим в pandas только для метрик и графиков — данные не огромные и это проще для sklearn-метрик
    # Для по-настоящему больших данных здесь можно использовать xgboost.dask.predict
    X_test_pd = X_test.compute()
    y_test_pd = y_test.compute()

    dmatrix_test = xgb.DMatrix(X_test_pd)
    y_pred_proba = booster.predict(dmatrix_test)
    y_pred = (y_pred_proba > 0.5).astype(int)

    logger.info(f"Предсказания получены за {time.time() - start_time:.2f} сек")

    # ====================== МЕТРИКИ ======================
    roc_auc = roc_auc_score(y_test_pd, y_pred_proba)
    pr_auc = average_precision_score(y_test_pd, y_pred_proba)
    logloss = log_loss(y_test_pd, y_pred_proba)

    # Precision@top-10% (бизнес-метрика для churn: кого первым спасать)
    top_k = int(len(y_test_pd) * 0.1)
    threshold = np.sort(y_pred_proba)[::-1][top_k - 1]
    y_pred_top = (y_pred_proba >= threshold).astype(int)
    precision_top = precision_score(y_test_pd, y_pred_top)

    logger.info("Метрики на hold-out (Dask пайплайн):")
    logger.info("  ROC-AUC:     %.4f", roc_auc)
    logger.info("  PR-AUC:      %.4f", pr_auc)
    logger.info("  LogLoss:     %.4f", logloss)
    logger.info("  Precision@top-10%%: %.4f", precision_top)

    # ====================== A/B-СИМУЛЯЦИЯ ======================
    logger.info("A/B-симуляция: удержание топ-10%% рисков оттока")
    logger.info("  → Если кампания удержит этих клиентов, ожидаемый lift в retention = %.1f%% от всего оттока",
                precision_top * 100)

    # ====================== ГРАФИКИ ======================
    # Confusion Matrix
    cm = confusion_matrix(y_test_pd, y_pred)
    plt.figure(figsize=(6, 4))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
    plt.title("Confusion Matrix (Dask XGBoost)")
    plt.ylabel("True")
    plt.xlabel("Predicted")
    plt.savefig(EVAL_PLOTS_DIR / "confusion_matrix_dask.png", dpi=300, bbox_inches="tight")
    plt.close()

    # ROC Curve
    fpr, tpr, _ = roc_curve(y_test_pd, y_pred_proba)
    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, label=f"ROC-AUC = {roc_auc:.4f}")
    plt.plot([0, 1], [0, 1], linestyle="--")
    plt.title("ROC Curve (Dask XGBoost)")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.legend()
    plt.savefig(EVAL_PLOTS_DIR / "roc_curve_dask.png", dpi=300, bbox_inches="tight")
    plt.close()

    # PR Curve
    precision, recall, _ = precision_recall_curve(y_test_pd, y_pred_proba)
    plt.figure(figsize=(8, 6))
    plt.plot(recall, precision, label=f"PR-AUC = {pr_auc:.4f}")
    plt.title("Precision-Recall Curve (Dask XGBoost)")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.legend()
    plt.savefig(EVAL_PLOTS_DIR / "pr_curve_dask.png", dpi=300, bbox_inches="tight")
    plt.close()

    logger.info(f"Графики сохранены в {EVAL_PLOTS_DIR}")
    logger.info(f"Полная оценка завершена за {time.time() - start_time:.2f} сек")
    logger.info("Оценка модели на Dask завершена успешно")


if __name__ == "__main__":
    from dask.distributed import Client

    with Client(n_workers=4, threads_per_worker=1, memory_limit="4GB") as client:
        logger.info(f"Dask Client запущен: {client}")
        try:
            evaluate_model_dask()
        except Exception as e:
            logger.error(f"Ошибка при оценке на Dask: {e}")
            raise