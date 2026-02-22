import pandas as pd
import logging
import coloredlogs


logger = logging.getLogger(__name__)
coloredlogs.install(level='INFO', logger=logger, fmt='%(asctime)s [%(levelname)s] %(message)s',
                    level_styles={'info': {'color': 'green'}, 'error': {'color': 'red', 'bold': True}})


def read_data(train=True):

    DATA_PATH = 'C:/vs_code_projects/distributed-churn-prediction/data/Train.csv'

    all_cols = ['user_id', 'REGION', 'TENURE', 'MONTANT', 'FREQUENCE_RECH', 'REVENUE',
                'ARPU_SEGMENT', 'FREQUENCE', 'DATA_VOLUME', 'ON_NET', 'ORANGE', 'TIGO',
                'ZONE1', 'ZONE2', 'MRG', 'REGULARITY', 'TOP_PACK', 'FREQ_TOP_PACK', 'CHURN']
    use_cols = all_cols.copy()
    use_cols.remove('MRG')
    if not train:
        use_cols.remove('CHURN')

    print(f'all_cols: {len(all_cols)}')
    print(f'use_cols: {len(use_cols)}')
        
    df = pd.read_csv(
        filepath_or_buffer=DATA_PATH,
        sep=',',
        encoding='utf-8',
        na_values=['', 'N/A', 'n/a', 'NULL', 'null', 'Null', ' ', 'nan', 'None'],
        usecols=use_cols)

    if df.empty:
        logger.error(f'Ошибка чтения файла {DATA_PATH}')
        raise Exception(f'Ошибка чтения файла {DATA_PATH}')
    else:
        logger.info(f'Данные из файла {DATA_PATH} успешно загружены в переменную df')
        return df

read_data(train=True)