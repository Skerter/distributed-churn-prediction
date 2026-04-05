from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.churn.shared.enums import RuntimeMode
from src.churn.shared.exceptions import ConfigError


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
class Settings:
    project_root: Path
    app: AppMetaSettings
    paths: PathsSettings
    logging: LoggingSettings
    runtime: RuntimeSettings
    dask: DaskSettings
    pipeline: PipelineSettings

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
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], project_root: Path) -> "Settings":
        try:
            app_data = data["app"]
            paths_data = data["paths"]
            logging_data = data["logging"]
            runtime_data = data["runtime"]
            dask_data = data.get("dask", {})
            pipeline_data = data.get("pipeline", {})
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
        )