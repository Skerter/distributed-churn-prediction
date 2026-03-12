import pandas as pd

from src.utils.config import find_project_root, load_config
from src.utils.logger import get_logger
from src.features.preprocessing import fill_numeric_na, fill_categorical_na
from src.features.create_features import create_features
from src.features.encoding import target_encode, save_encoding_maps

# ====================== КОНФИГ И ЛОГГЕР ======================
PROJECT_ROOT = find_project_root()
config = load_config(PROJECT_ROOT)
logger = get_logger(
    name=__name__, 
    log_dir=PROJECT_ROOT / config["paths"]["logs"], 
    log_prefix="feature_engineering_local", 
    level=config["logging"]["level"]
)

logger.info("Корень проекта определён: %s", PROJECT_ROOT)
logger.info("Логи сохраняются в: %s", PROJECT_ROOT / config["paths"]["logs"])

# Определяем пути к данным
DATA_SOURCE = PROJECT_ROOT / config["paths"]["data_source"]
DATA_PROCESSED = PROJECT_ROOT / config["paths"]["data_processed"]
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
TRAIN_PATH = DATA_SOURCE / "Train.csv"
TEST_PATH = DATA_SOURCE / "Test.csv"
MAPS_PATH = DATA_PROCESSED / 'target_encoding_maps.json'
TRAIN_PROCESSED_PATH = DATA_PROCESSED / 'train_processed.parquet'
TEST_PROCESSED_PATH = DATA_PROCESSED / 'test_processed.parquet'


def validate_columns(df: pd.DataFrame, required_cols: list) -> None:
    '''Проверяем, что в датафрейме есть все необходимые колонки
    param df: входной датафрейм
    param required_cols: список обязательных колонок'''

    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"Отсутствуют колонки: {missing}")


def feature_engineering() -> None:
    '''Главная функция для построения признаков'''

    logger.info('Начало feature engineering')
    
    df_train = pd.read_csv(TRAIN_PATH)
    df_test = pd.read_csv(TEST_PATH)
    logger.info("Загружено Train: %s строк, Test: %s строк", len(df_train), len(df_test))
    
    cat_cols = config['preprocessing']['categorical_columns']
    smoothing = config['preprocessing']['smoothing']
    
    validate_columns(df_train, cat_cols + ["CHURN"])
    
    logger.info("Заполнение пропусков")
    
    df_train = fill_numeric_na(df_train, config["preprocessing"]["fillna_num"], "CHURN")
    df_test = fill_numeric_na(df_test, config["preprocessing"]["fillna_num"], "CHURN")
    
    df_train = fill_categorical_na(df_train, cat_cols, config['preprocessing']['fillna_cat'])
    df_test = fill_categorical_na(df_test, cat_cols, config['preprocessing']['fillna_cat'])
 
    logger.info('Пропуски успешно заполнены')
    
    logger.info("Создание новых признаков (feature engineering)")

    df_train = create_features(df_train)
    df_test = create_features(df_test)
    
    logger.info("Создано 5 новых признаков: AVG_REVENUE, RECH_TO_DATA_RATIO, REGULARITY_SCORE, HAS_TOP_PACK, MISSING_ZONE")

    # Если включено target encoding, то выполняем его
    if config['preprocessing']['target_encoding']:
        
        logger.info('Начало Target Encoding для категориальных признаков: %s', cat_cols)
    
        logger.debug('Параметр сглаживания для Target Encoding: %s', smoothing)
        logger.debug('Целевая переменная для Target Encoding: %s', "CHURN")
        logger.debug('Количество строк в Train перед Target Encoding: %s', len(df_train))
        logger.debug('Количество строк в Test перед Target Encoding: %s', len(df_test))
        
        df_train, df_test, target_enc_maps = target_encode(df_train, df_test, cat_cols, target="CHURN", smoothing=smoothing)
        
        save_encoding_maps(MAPS_PATH, target_enc_maps)

        logger.info('Target Encoding завершен успешно')
        
        logger.debug('Маппинги сохранены в %s', MAPS_PATH)
        logger.debug('Количество строк в Train после Target Encoding: %s', len(df_train))
        logger.debug('Количество строк в Test после Target Encoding: %s', len(df_test))
        
    logger.info("Сохранение обработанных данных в Parquet формате")
    
    df_train.to_parquet(TRAIN_PROCESSED_PATH, index=False)
    df_test.to_parquet(TEST_PROCESSED_PATH, index=False)

    logger.info("Данные сохранены:")
    logger.info("  - %s", TRAIN_PROCESSED_PATH)
    logger.info("  - %s", TEST_PROCESSED_PATH)
    logger.info("Feature engineering завершён успешно")


if __name__ == "__main__":
    try:
        feature_engineering()
    except Exception as e:
        logger.error("Ошибка при построении признаков: %s", str(e))
        raise
