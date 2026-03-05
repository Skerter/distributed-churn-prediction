import numpy as np
import pandas as pd

from src.utils.logger import get_logger
from src.utils.config import find_project_root, load_config

project_root = find_project_root()
config = load_config(project_root)
logger = get_logger(name=__name__, 
                    log_dir=project_root / config["paths"]["logs"], 
                    log_prefix="preprocessing",
                    level=config["logging"]["level"])


def fill_numeric_na(df: pd.DataFrame, strategy="median", target_col="CHURN") -> pd.DataFrame:
    '''Заполняем пропуски в числовых признаках, исключая целевую переменную (если она есть)'''

    num_cols = df.select_dtypes(include=[np.number]).columns.drop([target_col], errors="ignore")
    logger.debug("Числовые колонки для заполнения NA: %s", num_cols.tolist())

    for col in num_cols:
        if strategy == "median":
            value = df[col].median()
            logger.debug("Заполняем пропуски в числовом признаке '%s' медианой: %s", col, value)
        elif strategy == "mean":
            value = df[col].mean()
            logger.debug("Заполняем пропуски в числовом признаке '%s' средним: %s", col, value)
        else:
            logger.error('Неожиданная стратегия fillna_num из config.yaml -> %s', strategy)
            raise ValueError('''В файле config.yaml в разделе preprocessing для числовых значений для заполнения N/A 
                            выбрано %s, логикой проекта предусмотрено только mean и median''', strategy)
        
        df[col].fillna(value, inplace=True)

    return df


def fill_categorical_na(df: pd.DataFrame, cat_cols: list, fill_value="missing") -> pd.DataFrame:
    '''Заполняем пропуски в категориальных признаках'''

    for col in cat_cols:
        df[col].fillna(fill_value, inplace=True)
        logger.debug("Заполняем пропуски в категориальном признаке '%s' значением: %s", col, fill_value)

    return df