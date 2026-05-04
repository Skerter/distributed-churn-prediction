from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthApiResponse(BaseModel):
    app_name: str
    app_version: str
    profile_mode: str
    backend: str
    project_root: str


class RunPipelineApiRequest(BaseModel):
    execute: bool = Field(
        default=False,
        description=(
            "Если false — dry-run. Если true — реальный запуск pipeline."
        ),
    )
    skip_load: bool = False
    skip_features: bool = False
    skip_train: bool = False
    skip_eval: bool = False


class RunPipelineApiResponse(BaseModel):
    success: bool
    profile: str
    mode: str
    backend: str
    pipeline_path: str
    executed: bool
    message: str
    result: Any | None = None


class ProfileApiItem(BaseModel):
    name: str
    runtime_mode: str
    backend: str
    web_enabled: bool
    description: str
    warning: str | None = None


class ProfilesApiResponse(BaseModel):
    default_profile: str
    profiles: list[ProfileApiItem]


class ConfigSummaryApiResponse(BaseModel):
    app: dict[str, Any]
    runtime: dict[str, Any]
    backend: str
    model: dict[str, Any]
    data: dict[str, Any]
    dask: dict[str, Any]
    pipeline: dict[str, Any]
    paths: dict[str, Any]


class ModelInfoApiResponse(BaseModel):
    profile: str
    mode: str
    backend: str
    model: dict[str, Any]
    artifacts: dict[str, Any]
    metrics: dict[str, Any] | None = None


class CreatePipelineRunApiRequest(BaseModel):
    execute: bool = Field(
        default=True,
        description="Если true — pipeline будет запущен. Если false — dry-run.",
    )
    skip_load: bool = False
    skip_features: bool = False
    skip_train: bool = False
    skip_eval: bool = False


class PipelineRunApiResponse(BaseModel):
    run_id: str
    status: str
    profile: str
    executor: str
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    request: dict[str, Any]
    result: Any | None = None
    error: str | None = None
    metadata: dict[str, Any]


class ErrorApiBody(BaseModel):
    code: str
    message: str


class ErrorApiResponse(BaseModel):
    success: bool = False
    error: ErrorApiBody
