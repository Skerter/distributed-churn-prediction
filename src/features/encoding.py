import json
import pandas as pd


def target_encode(train: pd.DataFrame, test: pd.DataFrame, cols: list, target: str, smoothing: float) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    '''Выполняем target encoding для списка колонок cols. Возвращаем преобразованные датафреймы и словарь с маппингами для каждой колонки'''

    prior = train[target].mean()
    maps = {}

    for col in cols:

        stats = train.groupby(col)[target].agg(["mean", "count"])

        smoothed = (
            stats["count"] * stats["mean"] + smoothing * prior
        ) / (stats["count"] + smoothing)

        mapping = smoothed.to_dict()

        mapping["__UNKNOWN__"] = prior

        train[col] = train[col].map(mapping).fillna(prior)
        test[col] = test[col].map(mapping).fillna(prior)

        maps[col] = mapping

    return train, test, maps


def save_encoding_maps(path: str, maps: dict) -> None:
    '''Сохраняем словарь с маппингами для target encoding в JSON файл по указанному пути'''

    with open(path, "w", encoding="utf-8") as f:
        json.dump(maps, f, ensure_ascii=False, indent=2)