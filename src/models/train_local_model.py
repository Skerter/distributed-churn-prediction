import pandas as pd
import xgboost as xgb
import json
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report, f1_score

from src.utils.config import find_project_root, load_config
from src.utils.logger import get_logger

# Инициализация конфига и логгера
PROJECT_ROOT = find_project_root()
config = load_config(PROJECT_ROOT)
logger = get_logger(
    name=__name__, 
    log_dir=PROJECT_ROOT / config["paths"]["logs"], 
    log_prefix="train_local_model", 
    level=config["logging"]["level"]
)

# Пути
DATA_PROCESSED = PROJECT_ROOT / config["paths"]["data_processed"]
MODEL_DIR = PROJECT_ROOT / config["paths"]["models"]
MODEL_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_PATH = DATA_PROCESSED / 'train_processed.parquet'
MODEL_PATH = MODEL_DIR / config['model']['name'] + config['model']['version'] + ".json"
METRICS_PATH = PROJECT_ROOT / config["paths"]["metrics"]
METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)


def train_model():

    # 1. Загрузка данных
    logger.info("Загрузка данных из %s", TRAIN_PATH)
    df = pd.read_parquet(TRAIN_PATH)
    
    X = df.drop(columns=['CHURN'])
    y = df['CHURN']
    
    # 2. Split на Train/Validation
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, 
        test_size=config["training"]["subsample"], 
        random_state=config["training"]["random_state"],
        stratify=y # Важно для оттока (несбалансированные классы)
    )
    logger.info("Данные разделены: Train=%s, Val=%s", X_train.shape[0], X_val.shape[0])

    # 3. Инициализация модели
    params = config["model"]["early_stopping_rounds"]
    # Извлекаем early_stopping_rounds, так как он передается в fit
    early_stop = params.pop("early_stopping_rounds", 50)
    
    clf = xgb.XGBClassifier(
        **params,
        use_label_encoder=False,
        eval_metric=config['training']['eval_metric']
    )

    # 4. Обучение
    logger.info("Начало обучения XGBoost...")
    clf.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        early_stopping_rounds=early_stop,
        verbose=100
    )

    # 5. Оценка
    logger.info("Оценка модели...")
    preds_prob = clf.predict_proba(X_val)[:, 1]
    preds_class = clf.predict(X_val)
    
    roc_auc = roc_auc_score(y_val, preds_prob)
    f1 = f1_score(y_val, preds_class)
    
    metrics = {
        "roc_auc": float(roc_auc),
        "f1_score": float(f1),
        "best_iteration": clf.get_booster().best_iteration
    }
    
    logger.info("Метрики: ROC-AUC: %.4f, F1: %.4f", roc_auc, f1)
    logger.info("\n%s", classification_report(y_val, preds_class))

    # 6. Сохранение артефактов
    clf.save_model(MODEL_PATH)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=4)
        
    logger.info("Модель сохранена в: %s", MODEL_PATH)
    logger.info("Метрики сохранены в: %s", METRICS_PATH)

if __name__ == "__main__":
    try:
        train_model()
    except Exception as e:
        logger.error("Ошибка при обучении: %s", str(e), exc_info=True)
        raise