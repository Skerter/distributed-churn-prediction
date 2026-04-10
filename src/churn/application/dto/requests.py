from dataclasses import dataclass


@dataclass(slots=True)
class RunPipelineRequest:
    """Класс запроса для запуска pipeline, который содержит информацию о профиле конфигурации и опциях для пропуска определенных этапов выполнения.

    Returns:
        RunPipelineRequest: Экземпляр класса RunPipelineRequest, содержащий информацию о профиле и опциях для выполнения pipeline.
    """
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