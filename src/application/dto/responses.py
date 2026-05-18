from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class HealthResponse:
    """Класс ответа для проверки состояния приложения, который содержит информацию о состоянии здоровья приложения, включая имя приложения, версию, режим профиля, бэкенд и корневой путь проекта.

    Returns:
        HealthResponse: Экземпляр класса HealthResponse, содержащий информацию о состоянии здоровья приложения.
    """
    app_name: str
    app_version: str
    profile_mode: str
    project_root: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "profile_mode": self.profile_mode,
            "project_root": self.project_root,
        }


@dataclass(slots=True)
class RunPipelineResponse:
    """Класс ответа для выполнения pipeline, который содержит информацию о результате выполнения, включая статус успеха, профиль, режим, бэкенд, путь к pipeline, флаг выполнения и сообщение.

    Returns:
        RunPipelineResponse: Экземпляр класса RunPipelineResponse, содержащий информацию о результате выполнения pipeline.
    """
    success: bool
    profile: str
    mode: str
    pipeline_path: str
    executed: bool
    message: str
    result: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "profile": self.profile,
            "mode": self.mode,
            "pipeline_path": self.pipeline_path,
            "executed": self.executed,
            "message": self.message,
            "result": self.result,
        }


@dataclass(slots=True)
class ProfileInfo:
    name: str
    runtime_mode: str
    web_enabled: bool
    description: str
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "runtime_mode": self.runtime_mode,
            "web_enabled": self.web_enabled,
            "description": self.description,
            "warning": self.warning,
        }


@dataclass(slots=True)
class ProfilesResponse:
    default_profile: str
    profiles: list[ProfileInfo]

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_profile": self.default_profile,
            "profiles": [profile.to_dict() for profile in self.profiles],
        }


@dataclass(slots=True)
class ConfigSummaryResponse:
    app: dict[str, Any]
    runtime: dict[str, Any]
    model: dict[str, Any]
    data: dict[str, Any]
    dask: dict[str, Any]
    pipeline: dict[str, Any]
    api: dict[str, Any]
    paths: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "app": self.app,
            "runtime": self.runtime,
            "model": self.model,
            "data": self.data,
            "dask": self.dask,
            "pipeline": self.pipeline,
            "api": self.api,
            "paths": self.paths,
        }

@dataclass(slots=True)
class ModelInfoResponse:
    profile: str
    mode: str
    model: dict[str, Any]
    artifacts: dict[str, Any]
    metrics: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "mode": self.mode,
            "model": self.model,
            "artifacts": self.artifacts,
            "metrics": self.metrics,
        }


@dataclass(slots=True)
class PipelineRunResponse:
    """Ответ с состоянием асинхронного pipeline run."""

    run_id: str
    status: str
    profile: str
    executor: str
    created_at: str
    updated_at: str
    request: dict[str, Any]
    started_at: str | None = None
    finished_at: str | None = None
    result: Any | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "profile": self.profile,
            "executor": self.executor,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "request": self.request,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata or {},
        }
