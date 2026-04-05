from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class HealthResponse:
    app_name: str
    app_version: str
    profile_mode: str
    backend: str
    project_root: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "profile_mode": self.profile_mode,
            "backend": self.backend,
            "project_root": self.project_root,
        }


@dataclass(slots=True)
class RunPipelineResponse:
    success: bool
    profile: str
    mode: str
    backend: str
    pipeline_path: str
    executed: bool
    message: str
    result: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "profile": self.profile,
            "mode": self.mode,
            "backend": self.backend,
            "pipeline_path": self.pipeline_path,
            "executed": self.executed,
            "message": self.message,
            "result": self.result,
        }