from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.shared.enums import RuntimeMode, PipelineExecutorKind
from src.shared.exceptions import ConfigError


@dataclass(slots=True)
class AppMetaSettings:
    name: str
    version: str


@dataclass(slots=True)
class PathsSettings:
    data_source: str
    data_processed: str
    models: str
    logs: str
    notebooks: str


@dataclass(slots=True)
class DataSettings:
    dataset_slug: str | None
    train_filename: str
    test_filename: str
    target_column: str


@dataclass(slots=True)
class LoggingSettings:
    level: str
    log_to_file: bool
    use_coloredlogs: bool
    fmt: str


@dataclass(slots=True)
class RuntimeSettings:
    mode: RuntimeMode


@dataclass(slots=True)
class DaskSettings:
    scheduler_address: str | None
    n_workers: int
    threads_per_worker: int


@dataclass(slots=True)
class PipelineSettings:
    default_execute: bool = False


@dataclass(slots=True)
class ModelSettings:
    name: str
    version: str
    random_state: int
    test_size: float
    cv_folds: int
    early_stopping_rounds: int


@dataclass(slots=True)
class PreprocessingSettings:
    fillna_num: str
    fillna_cat: str
    target_encoding: bool
    smoothing: float
    categorical_columns: list[str]
    drop_columns: list[str]


@dataclass(slots=True)
class TrainingSettings:
    objective: str
    eval_metric: str
    max_depth: int
    learning_rate: float
    n_estimators: int
    subsample: float
    colsample_bytree: float
    n_jobs: int


@dataclass(slots=True)
class EvaluationSettings:
    top_fraction: float = 0.1
    

@dataclass(slots=True)
class ApiKubernetesSettings:
    namespace: str
    job_name_prefix: str
    job_image: str
    image_pull_policy: str
    storage_pvc_name: str
    storage_mount_path: str
    pipeline_profile: str


@dataclass(slots=True)
class ApiSettings:
    pipeline_executor: PipelineExecutorKind
    max_concurrent_pipeline_runs: int
    kubernetes: ApiKubernetesSettings


@dataclass(slots=True)
class Settings:
    """Основной класс настроек приложения, который агрегирует все конфигурационные параметры, необходимые для работы приложения, включая пути, параметры данных, настройки логирования, режим выполнения, параметры Dask, настройки модели и другие.

    Raises:
        ConfigError: Если не удалось разрешить конфигурационные параметры.
        ConfigError: Если не удалось создать экземпляр настроек.

    Returns:
        Settings: Экземпляр класса Settings, содержащий все инициализированные конфигурационные параметры.
    """
    project_root: Path
    app: AppMetaSettings
    paths: PathsSettings
    data: DataSettings
    logging: LoggingSettings
    runtime: RuntimeSettings
    dask: DaskSettings
    pipeline: PipelineSettings
    model: ModelSettings
    preprocessing: PreprocessingSettings
    training: TrainingSettings
    evaluation: EvaluationSettings
    api: ApiSettings

    @property
    def data_source_dir(self) -> Path:
        return self.project_root / self.paths.data_source

    @property
    def data_processed_dir(self) -> Path:
        return self.project_root / self.paths.data_processed

    @property
    def models_dir(self) -> Path:
        return self.project_root / self.paths.models

    @property
    def logs_dir(self) -> Path:
        return self.project_root / self.paths.logs

    @property
    def notebooks_dir(self) -> Path:
        return self.project_root / self.paths.notebooks

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "app": {
                "name": self.app.name,
                "version": self.app.version,
            },
            "paths": {
                "data_source": self.paths.data_source,
                "data_processed": self.paths.data_processed,
                "models": self.paths.models,
                "logs": self.paths.logs,
                "notebooks": self.paths.notebooks,
            },
            "data": {
                "dataset_slug": self.data.dataset_slug,
                "train_filename": self.data.train_filename,
                "test_filename": self.data.test_filename,
                "target_column": self.data.target_column,
            },
            "logging": {
                "level": self.logging.level,
                "log_to_file": self.logging.log_to_file,
                "use_coloredlogs": self.logging.use_coloredlogs,
                "fmt": self.logging.fmt,
            },
            "runtime": {
                "mode": self.runtime.mode.value,
            },
            "dask": {
                "scheduler_address": self.dask.scheduler_address,
                "n_workers": self.dask.n_workers,
                "threads_per_worker": self.dask.threads_per_worker,
            },
            "pipeline": {
                "default_execute": self.pipeline.default_execute,
            },
            "model": {
                "name": self.model.name,
                "version": self.model.version,
                "random_state": self.model.random_state,
                "test_size": self.model.test_size,
                "cv_folds": self.model.cv_folds,
                "early_stopping_rounds": self.model.early_stopping_rounds,
            },
            "preprocessing": {
                "fillna_num": self.preprocessing.fillna_num,
                "fillna_cat": self.preprocessing.fillna_cat,
                "target_encoding": self.preprocessing.target_encoding,
                "smoothing": self.preprocessing.smoothing,
                "categorical_columns": self.preprocessing.categorical_columns,
                "drop_columns": self.preprocessing.drop_columns,
            },
            "training": {
                "objective": self.training.objective,
                "eval_metric": self.training.eval_metric,
                "max_depth": self.training.max_depth,
                "learning_rate": self.training.learning_rate,
                "n_estimators": self.training.n_estimators,
                "subsample": self.training.subsample,
                "colsample_bytree": self.training.colsample_bytree,
                "n_jobs": self.training.n_jobs,
            },
            "evaluation": {
                "top_fraction": self.evaluation.top_fraction,
            },
            "api": {
                "pipeline_executor": self.api.pipeline_executor.value,
                "max_concurrent_pipeline_runs": self.api.max_concurrent_pipeline_runs,
                "kubernetes": {
                    "namespace": self.api.kubernetes.namespace,
                    "job_name_prefix": self.api.kubernetes.job_name_prefix,
                    "job_image": self.api.kubernetes.job_image,
                    "image_pull_policy": self.api.kubernetes.image_pull_policy,
                    "storage_pvc_name": self.api.kubernetes.storage_pvc_name,
                    "storage_mount_path": self.api.kubernetes.storage_mount_path,
                    "pipeline_profile": self.api.kubernetes.pipeline_profile,
                },
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], project_root: Path) -> "Settings":
        try:
            app_data = data["app"]
            paths_data = data["paths"]
            data_data = data["data"]
            logging_data = data["logging"]
            runtime_data = data["runtime"]
            dask_data = data.get("dask", {})
            pipeline_data = data.get("pipeline", {})
            model_data = data["model"]
            preprocessing_data = data["preprocessing"]
            training_data = data["training"]
            evaluation_data = data.get("evaluation", {})
            api_data = data.get("api", {})
            kubernetes_data = api_data.get("kubernetes", {})
        except KeyError as exc:
            raise ConfigError(f"В конфиге отсутствует обязательный ключ: {exc}") from exc

        try:
            runtime_mode = RuntimeMode(runtime_data["mode"])
        except ValueError as exc:
            raise ConfigError(
                f"Недопустимый runtime.mode: {runtime_data.get('mode')}"
            ) from exc

        return cls(
            project_root=project_root,
            app=AppMetaSettings(
                name=app_data["name"],
                version=app_data["version"],
            ),
            paths=PathsSettings(
                data_source=paths_data["data_source"],
                data_processed=paths_data["data_processed"],
                models=paths_data["models"],
                logs=paths_data["logs"],
                notebooks=paths_data["notebooks"],
            ),
            data=DataSettings(
                dataset_slug=data_data.get("dataset_slug"),
                train_filename=data_data.get("train_filename", "Train.csv"),
                test_filename=data_data.get("test_filename", "Test.csv"),
                target_column=data_data.get("target_column", "CHURN"),
            ),
            logging=LoggingSettings(
                level=logging_data["level"],
                log_to_file=bool(logging_data["log_to_file"]),
                use_coloredlogs=bool(logging_data.get("use_coloredlogs", True)),
                fmt=logging_data["fmt"],
            ),
            runtime=RuntimeSettings(mode=runtime_mode),
            dask=DaskSettings(
                scheduler_address=dask_data.get("scheduler_address"),
                n_workers=int(dask_data.get("n_workers", 2)),
                threads_per_worker=int(dask_data.get("threads_per_worker", 1)),
            ),
            pipeline=PipelineSettings(
                default_execute=bool(pipeline_data.get("default_execute", False)),
            ),
            model=ModelSettings(
                name=model_data["name"],
                version=model_data["version"],
                random_state=int(model_data["random_state"]),
                test_size=float(model_data["test_size"]),
                cv_folds=int(model_data["cv_folds"]),
                early_stopping_rounds=int(model_data["early_stopping_rounds"]),
            ),
            preprocessing=PreprocessingSettings(
                fillna_num=preprocessing_data["fillna_num"],
                fillna_cat=preprocessing_data["fillna_cat"],
                target_encoding=bool(preprocessing_data["target_encoding"]),
                smoothing=float(preprocessing_data["smoothing"]),
                categorical_columns=list(preprocessing_data["categorical_columns"]),
                drop_columns=list(preprocessing_data.get("drop_columns", [])),
            ),
            training=TrainingSettings(
                objective=training_data["objective"],
                eval_metric=training_data["eval_metric"],
                max_depth=int(training_data["max_depth"]),
                learning_rate=float(training_data["learning_rate"]),
                n_estimators=int(training_data["n_estimators"]),
                subsample=float(training_data["subsample"]),
                colsample_bytree=float(training_data["colsample_bytree"]),
                n_jobs=int(training_data.get("n_jobs", -1)),
            ),
            evaluation=EvaluationSettings(
                top_fraction=float(evaluation_data.get("top_fraction", 0.1)),
            ),
            api=ApiSettings(
                pipeline_executor=PipelineExecutorKind(
                    api_data.get("pipeline_executor", "web")
                ),
                max_concurrent_pipeline_runs=int(
                    api_data.get("max_concurrent_pipeline_runs", 1)
                ),
                kubernetes=ApiKubernetesSettings(
                    namespace=kubernetes_data.get("namespace", "default"),
                    job_name_prefix=kubernetes_data.get("job_name_prefix", "dcp-pipeline"),
                    job_image=kubernetes_data.get("job_image", "dcp-pipeline:latest"),
                    image_pull_policy=kubernetes_data.get("image_pull_policy", "IfNotPresent"),
                    storage_pvc_name=kubernetes_data.get("storage_pvc_name", "dcp-storage"),
                    storage_mount_path=kubernetes_data.get("storage_mount_path", "/mnt/dcp"),
                    pipeline_profile=kubernetes_data.get("pipeline_profile", "dask_k8s"),
                ),
            ),
        )