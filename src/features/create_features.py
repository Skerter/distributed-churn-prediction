import pandas as pd


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    '''Создаем новые признаки на основе имеющихся

    AVG_REVENUE - средний доход на транзакцию
    RECH_TO_DATA_RATIO - соотношение между количеством пополнений и объемом данных
    REGULARITY_SCORE - нормализованная регулярность использования
    HAS_TOP_PACK - есть ли топовый пакет
    MISSING_ZONE - пропущены ли обе зоны (ZONE1 и ZONE2)'''

    df["AVG_REVENUE"] = df["REVENUE"] / (df["FREQUENCE"] + 1)

    df["RECH_TO_DATA_RATIO"] = (df["FREQUENCE_RECH"] / (df["DATA_VOLUME"] + 1))

    df["REGULARITY_SCORE"] = df["REGULARITY"] / 90.0

    df["HAS_TOP_PACK"] = (df["TOP_PACK"] != "missing").astype(int)

    df["MISSING_ZONE"] = (df[["ZONE1", "ZONE2"]].isnull().all(axis=1)).astype(int)

    return df