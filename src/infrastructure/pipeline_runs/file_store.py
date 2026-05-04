from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.shared.enums import PipelineRunStatus


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class FilePipelineRunStore:
    """Файловое хранилище состояния pipeline runs."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        return self.root_dir / f"{run_id}.json"

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.save(payload)
        return payload

    def save(self, payload: dict[str, Any]) -> None:
        path = self._path(payload["run_id"])

        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

    def get(self, run_id: str) -> dict[str, Any]:
        path = self._path(run_id)

        if not path.exists():
            raise FileNotFoundError(f"Pipeline run не найден: {run_id}")

        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def mark_running(self, run_id: str) -> dict[str, Any]:
        payload = self.get(run_id)
        payload["status"] = PipelineRunStatus.RUNNING.value
        payload["started_at"] = utc_now_iso()
        payload["updated_at"] = utc_now_iso()
        self.save(payload)
        return payload

    def mark_succeeded(
        self,
        run_id: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self.get(run_id)
        payload["status"] = PipelineRunStatus.SUCCEEDED.value
        payload["finished_at"] = utc_now_iso()
        payload["updated_at"] = utc_now_iso()
        payload["result"] = result
        self.save(payload)
        return payload

    def mark_failed(self, run_id: str, error: str) -> dict[str, Any]:
        payload = self.get(run_id)
        payload["status"] = PipelineRunStatus.FAILED.value
        payload["finished_at"] = utc_now_iso()
        payload["updated_at"] = utc_now_iso()
        payload["error"] = error
        self.save(payload)
        return payload

    def update_metadata(
        self,
        run_id: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self.get(run_id)
        payload.setdefault("metadata", {}).update(metadata)
        payload["updated_at"] = utc_now_iso()
        self.save(payload)
        return payload

    def has_active_runs(self) -> bool:
        active_statuses = {
            PipelineRunStatus.QUEUED.value,
            PipelineRunStatus.RUNNING.value,
        }

        for path in self.root_dir.glob("*.json"):
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)

            if payload.get("status") in active_statuses:
                return True

        return False