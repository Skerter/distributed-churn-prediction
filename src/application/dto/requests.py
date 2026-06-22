from dataclasses import dataclass


@dataclass(slots=True)
class ExecutePipelineRequest:
    """Запрос на непосредственное выполнение pipeline внутри процесса."""

    profile: str
    execute: bool = False
    skip_load: bool = False
    skip_features: bool = False
    skip_train: bool = False
    skip_eval: bool = False

    def to_run_options(self) -> dict[str, bool]:
        return {
            "skip_load": self.skip_load,
            "skip_features": self.skip_features,
            "skip_train": self.skip_train,
            "skip_eval": self.skip_eval,
        }


@dataclass(slots=True)
class CreatePipelineRunRequest:
    """Запрос на создание pipeline run."""

    execute: bool = True
    skip_load: bool = False
    skip_features: bool = False
    skip_train: bool = False
    skip_eval: bool = False

    def to_run_options(self) -> dict[str, bool]:
        return {
            "skip_load": self.skip_load,
            "skip_features": self.skip_features,
            "skip_train": self.skip_train,
            "skip_eval": self.skip_eval,
        }
