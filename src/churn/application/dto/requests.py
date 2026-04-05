from dataclasses import dataclass


@dataclass(slots=True)
class RunPipelineRequest:
    '''DTO для запроса на выполнение pipeline с определенным профилем и опциями пропуска этапов.
    attrs:
        profile (str): Идентификатор профиля выполнения, который определяет набор параметров и конфигураций для pipeline.
        execute (bool): Флаг, указывающий, следует ли немедленно выполнить pipeline после его построения.
        skip_load (bool): Флаг, указывающий, следует ли пропустить этап загрузки данных.
        skip_features (bool): Флаг, указывающий, следует ли пропустить этап генерации признаков.
        skip_train (bool): Флаг, указывающий, следует ли пропустить этап обучения модели.
        skip_eval (bool): Флаг, указывающий, следует ли пропустить этап оценки модели.
    '''
    profile: str
    execute: bool = False
    skip_load: bool = False
    skip_features: bool = False
    skip_train: bool = False
    skip_eval: bool = False

    def to_run_options(self) -> dict[str, bool]:
        """Преобразует атрибуты запроса в словарь опций для выполнения pipeline, указывая, какие этапы следует пропустить.
        returns:
            dict[str, bool]: Словарь, где ключи - это названия этапов pipeline, а значения - булевы флаги, указывающие, следует ли пропустить эти этапы.
        """
        return {
            "skip_load": self.skip_load,
            "skip_features": self.skip_features,
            "skip_train": self.skip_train,
            "skip_eval": self.skip_eval,
        }