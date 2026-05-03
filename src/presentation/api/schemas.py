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
    profile: str = Field(
        default="pandas",
        description="Runtime profile: pandas, dask_local или dask_k8s.",
    )
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


class ErrorApiResponse(BaseModel):
    detail: str