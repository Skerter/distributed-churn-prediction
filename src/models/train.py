import pandas as pd
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from xgboost import XGBClassifier

from src.utils.config import find_project_root, load_config
from src.utils.logger import get_logger


# ====================== КОНФИГ И ЛОГГЕР ======================
PROJECT_ROOT = find_project_root()
config = load_config(PROJECT_ROOT)

logger = get_logger(
    name=__name__,
    log_dir=PROJECT_ROOT / config["paths"]["logs"],
    log_prefix="train_model",
    level=config["logging"]["level"]
)

# ====================== ПУТИ ======================
DATA_PROCESSED = PROJECT_ROOT / config["paths"]["data_processed"]
MODELS_DIR = PROJECT_ROOT / config["paths"]["models"]
MODEL_PLOTS_DIR = PROJECT_ROOT / config["paths"]["notebooks"] / "model_plots"

DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PLOTS_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_PROCESSED_PATH = DATA_PROCESSED / "train_processed.parquet"
MODEL_PATH = MODELS_DIR / f"{config['model']['name']}_{config['model']['version']}.pkl"

def load_data(path) -> pd.DataFrame:
    logger.info("Загрузка данных из %s", path)
    df = pd.read_parquet(path)
    logger.info("Данные загружены: %s строк, %s столбцов", df.shape[0], df.shape[1])
    return df

# ====================== ОБУЧЕНИЕ ======================
def train_model() -> None:
    logger.info("Начало обучения модели XGBoost (локальный прототип)")

    df = load_data(TRAIN_PROCESSED_PATH)

    # Подготовка X, y
    if "user_id" in df.columns:
        df = df.drop("user_id", axis=1)
        assert "user_id" not in df.columns
    X = df.drop(["CHURN", "MRG"], axis=1)
    y = df["CHURN"].astype(int)

    assert "CHURN" not in X.columns
    assert "MRG" not in X.columns

    # ====================== КРОСС-ВАЛИДАЦИЯ ======================
    cv_folds = config["model"].get("cv_folds", 5)
    
    logger.info("Начало кросс-валидации с %s фолдами", cv_folds)
    
    cv = StratifiedKFold(
        n_splits=cv_folds,
        shuffle=True,
        random_state=config["model"]["random_state"]
    )

    model_cv = XGBClassifier(
        objective=config["training"]["objective"],
        eval_metric=config["training"]["eval_metric"],
        max_depth=config["training"]["max_depth"],
        learning_rate=config["training"]["learning_rate"],
        n_estimators=config["training"]["n_estimators"],
        subsample=config["training"]["subsample"],
        colsample_bytree=config["training"]["colsample_bytree"],
        random_state=config["model"]["random_state"],
        n_jobs=-1
    )

    cv_scores = cross_val_score(
        model_cv, X, y, cv=cv, scoring="roc_auc", n_jobs=-1
    )
    logger.info("CV ROC-AUC: mean=%.4f, std=%.4f", cv_scores.mean(), cv_scores.std())

    # ====================== ФИНАЛЬНОЕ ОБУЧЕНИЕ С EARLY STOPPING ======================
    logger.info("Начало финального обучения с ранней остановкой...")
    X_train, X_val, y_train, y_val = train_test_split(
        X, y,
        test_size=config["model"]["test_size"],
        stratify=y,
        random_state=config["model"]["random_state"]
    )

    model = XGBClassifier(
        objective=config["training"]["objective"],
        eval_metric=config["training"]["eval_metric"],
        max_depth=config["training"]["max_depth"],
        learning_rate=config["training"]["learning_rate"],
        n_estimators=config["training"]["n_estimators"],
        subsample=config["training"]["subsample"],
        colsample_bytree=config["training"]["colsample_bytree"],
        early_stopping_rounds=config["model"]["early_stopping_rounds"],
        random_state=config["model"]["random_state"],
        n_jobs=-1
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=True
    )

    logger.info("Обучение завершено. Лучшая итерация: %s", model.best_iteration)

    # ====================== СОХРАНЕНИЕ ======================
    joblib.dump(model, MODEL_PATH)
    logger.info("Модель сохранена: %s", MODEL_PATH)

    # ====================== FEATURE IMPORTANCE ======================
    importance = pd.Series(
        model.feature_importances_,
        index=X.columns
    ).sort_values(ascending=False)

    plt.figure(figsize=(12, 8))
    sns.barplot(x=importance.values[:20], y=importance.index[:20])
    plt.title("Top 20 Feature Importance (XGBoost)")
    plt.tight_layout()
    plt.savefig(MODEL_PLOTS_DIR / "feature_importance.png", dpi=300, bbox_inches="tight")
    plt.close()

    logger.info("Топ-5 признаков:")
    for feat, imp in importance.head(5).items():
        logger.info("  %s: %.4f", feat, imp)

    logger.info("Обучение модели завершено успешно")


if __name__ == "__main__":
    try:
        train_model()
    except Exception as e:
        logger.error("Ошибка при обучении: %s", str(e))
        raise