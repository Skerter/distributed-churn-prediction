import time
import dask.dataframe as dd
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from dask_ml.model_selection import train_test_split
from xgboost.dask import DaskXGBClassifier
from dask.distributed import get_client, Client

from src.churn.infrastructure.config.loader import find_project_root, load_config
from src.churn.infrastructure.logging.factory import get_logger


# ====================== КОНФИГ И ЛОГГЕР ======================
PROJECT_ROOT = find_project_root()
config = load_config(PROJECT_ROOT)

logger = get_logger(
    name=__name__,
    log_dir=PROJECT_ROOT / config["paths"]["logs"],
    log_prefix="train_dask",
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
MODEL_PATH = MODELS_DIR / f"{config['model']['name']}_{config['model']['version']}_dask.json"  # .json — официальный формат XGBoost


# ====================== ОСНОВНАЯ ЛОГИКА ======================
def train_model_dask() -> None:
    '''Обучаем DaskXGBClassifier на Dask DataFrame и сохраняем модель'''

    # подключаемся к существующему Dask Client
    try:
        client = get_client()
        logger.info("Используется существующий Dask Client")
    except ValueError:
        client = Client(n_workers=4, threads_per_worker=1)
        logger.info("Создан новый Dask Client")

    logger.info(f"Dask Client: {client}")
    
    logger.info("Начало обучения модели XGBoost на Dask")
    start_time = time.time()

    df = dd.read_parquet(TRAIN_PROCESSED_PATH)
    logger.info(f"Загружено {df.npartitions} partitions ({len(df)} строк)")

    # Подготовка X, y
    if "user_id" in df.columns:
        df = df.drop("user_id", axis=1)
    if "MRG" in df.columns:
        df = df.drop("MRG", axis=1)

    X = df.drop("CHURN", axis=1)
    y = df["CHURN"].astype("int8")

    # Распределённое разбиение (dask_ml)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=config["model"]["test_size"],
        random_state=config["model"]["random_state"]
    )

    logger.info("Данные разбиты на train/test (distributed)")

    # ====================== РАСПРЕДЕЛЁННАЯ МОДЕЛЬ ======================
    model = DaskXGBClassifier(
        objective=config["training"]["objective"],
        eval_metric=config["training"]["eval_metric"],
        max_depth=config["training"]["max_depth"],
        learning_rate=config["training"]["learning_rate"],
        n_estimators=config["training"]["n_estimators"],
        subsample=config["training"]["subsample"],
        colsample_bytree=config["training"]["colsample_bytree"],
        early_stopping_rounds=config["model"]["early_stopping_rounds"],
        random_state=config["model"]["random_state"],
        tree_method="hist",          # обязательно для distributed
        verbosity=1
    )

    logger.info("Начало обучения DaskXGBClassifier...")
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=True
    )

    logger.info("Обучение завершено. Лучшая итерация: %d", model.best_iteration)
    logger.info("Время обучения: %.2f сек", time.time() - start_time)

    # ====================== СОХРАНЕНИЕ ======================
    model.save_model(str(MODEL_PATH))
    logger.info("Модель сохранена: %s", MODEL_PATH)

    # ====================== FEATURE IMPORTANCE ======================
    booster = model.get_booster()
    importance = pd.Series(
        booster.get_score(importance_type="weight"),
        name="importance"
    ).sort_values(ascending=False)

    plt.figure(figsize=(12, 8))
    sns.barplot(x=importance.values[:20], y=importance.index[:20])
    plt.title("Top 20 Feature Importance (Dask XGBoost)")
    plt.tight_layout()
    plt.savefig(MODEL_PLOTS_DIR / "feature_importance_dask.png", dpi=300, bbox_inches="tight")
    plt.close()

    logger.info("Топ-5 признаков:")
    for feat, imp in importance.head(5).items():
        logger.info("  %s: %.4f", feat, imp)

    logger.info("Распределённое обучение завершено успешно")


if __name__ == "__main__":
    from dask.distributed import Client

    with Client(n_workers=4, threads_per_worker=1, memory_limit="4GB", dashboard_address=":8787") as client:
        logger.info("Dask Client запущен: %s", client)
        try:
            train_model_dask()
        except Exception as e:
            logger.error("Ошибка при распределённом обучении: %s", e)
            raise