from __future__ import annotations

from typing import Protocol

from src.application.dto.requests import CreatePipelineRunRequest


class PipelineExecutor(Protocol):
    def submit(self, request: CreatePipelineRunRequest) -> dict:
        """Создаёт pipeline run и возвращает metadata."""

    def refresh(self, run_id: str) -> dict:
        """Обновляет и возвращает состояние pipeline run."""