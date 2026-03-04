import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import logging, coloredlogs
from datetime import datetime


def find_project_root(start_path: Path | None = None) -> Path:
    """Ищем папку configs/, поднимаясь вверх по дереву"""
    if start_path is None:
        start_path = Path.cwd()
    current = start_path.resolve()
    while current != current.parent:
        if (current / "configs").exists():
            return current
        current = current.parent
    raise FileNotFoundError("Не удалось найти папку configs/")

PROJECT_ROOT = find_project_root()
CONFIG_PATH = PROJECT_ROOT / "configs" / "config.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

logger = logging.getLogger(__name__)
log_level = getattr(logging, config['logging']['level'])

coloredlogs.install(
    log_level=log_level,
    logger=logger,
    fmt='%(asctime)s [%(levelname)s] %(message)s',
    level_styles={'info': {'color': 'green'}, 'error': {'color': 'red', 'bold': True}}
)

LOGS_DIR = PROJECT_ROOT / config['paths']['logs']
LOGS_DIR.mkdir(parents=True, exist_ok=True)

log_filename = LOGS_DIR / f'build_features_{datetime.now():%Y%m%d_%H%M%S}.log'
file_handler = logging.FileHandler(log_filename, mode='a', encoding='utf-8')
file_handler.setLevel(log_level)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(file_handler)

logger.info("Корень проекта определён: %s", PROJECT_ROOT)
logger.info("Логи сохраняются в: %s", log_filename)

DATA_SOURCE = PROJECT_ROOT / config["paths"]["data_source"]
DATA_PROCESSED = PROJECT_ROOT / config["paths"]["data_processed"]
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
TRAIN_PATH = DATA_SOURCE / "Train.csv"
TEST_PATH = DATA_SOURCE / "Test.csv"

def build_features():
    logger.info('Начало feature engineering')
    
    df_train = pd.read_csv(TRAIN_PATH)
    df_test = pd.read_csv(TEST_PATH)
    logger.info("Загружено Train: %s строк, Test: %s строк", len(df_train), len(df_test))
    
    cat_cols = config['preprocessing']['categorical_columns']
    smoothing = config['preprocessing']['smoothing']
    
    num_cols = df_train.select_dtypes(include=[np.number]).columns.drop(['CHURN'], errors='ignore')
    
    for col in num_cols:
        if config['preprocessing']['fillna_num'] == 'median':
            fill_value = df_train[col].median()
        elif config['preprocessing']['fillna_num'] == 'mean':
            fill_value = df_train[col].mean()
        else:
            logger.error('Неожиданный fillna_num из config.yaml -> %s', config['preprocessing']['fillna_num'])
            raise Exception('''В файле config.yaml в разделе preprocessing для числовых значений для заполнения N/A 
                            выбрано %s, логикой проекта предусмотрено только mean и median''', str(config['preprocessing']['fillna_num']))
        df_train[col] = df_train[col].fillna(fill_value)
        df_test[col] = df_test[col].fillna(fill_value)
        
    for col in cat_cols:
        fill_value = config['preprocessing']['fillna_cat']
        df_train[col] = df_train[col].fillna(fill_value)
        df_test[col] = df_test[col].fillna(fill_value)
        
    logger.info('Пропуски заполнены')
    # TODO продолжить написание новых признаков, при необходимости дропнуть ZONA1, ZONA2, MRG и другие мусорные признаки


if __name__ == "__main__":
    try:
        build_features()
    except Exception as e:
        logger.error("Ошибка при построении признаков: %s", str(e))
        raise
