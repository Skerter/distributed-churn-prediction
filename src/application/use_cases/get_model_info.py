from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.app.container import AppContainer
from src.application.dto.responses import ModelInfoResponse
from src.shared.enums import RuntimeMode


def _get_expected_model_extension(mode: RuntimeMode) -> str:
    if mode == RuntimeMode.PANDAS:
        return ".pkl"

    return ".json"


def _build_file_info(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": None,
        "modified_at": None,
    }

    if not path.exists():
        return result

    stat = path.stat()
    result["size_bytes"] = int(stat.st_size)
    result["modified_at"] = datetime.fromtimestamp(
        stat.st_mtime,
        tz=timezone.utc,
    ).isoformat()

    return result


def _load_metrics_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_model_info(container: AppContainer, profile: str) -> ModelInfoResponse:
    """Возвращает информацию об ожидаемой модели и связанных артефактах.
    
    Args:
        container (AppContainer): Контейнер приложения, содержащий настройки и зависимости.
        profile (str): Имя профиля, для которого запрашивается информация о модели.

    Returns:
        ModelInfoResponse: Экземпляр класса ModelInfoResponse, содержащий информацию об ожидаемой модели и связанных артефактах.
    """

    settings = container.settings
    mode = settings.runtime.mode
    model_extension = _get_expected_model_extension(mode)

    model_filename = f"{settings.model.name}_{settings.model.version}{model_extension}"
    metrics_filename = f"{settings.model.name}_{settings.model.version}_eval_metrics.json"

    model_path = settings.models_dir / model_filename
    metrics_path = settings.models_dir / metrics_filename

    model_file = _build_file_info(model_path)
    metrics_file = _build_file_info(metrics_path)

    return ModelInfoResponse(
        profile=profile,
        mode=mode.value,
        model={
            "name": settings.model.name,
            "version": settings.model.version,
            "expected_format": model_extension.lstrip("."),
            "expected_filename": model_filename,
            "exists": model_file["exists"],
        },
        artifacts={
            "model_file": model_file,
            "metrics_file": metrics_file,
        },
        metrics=_load_metrics_if_exists(metrics_path),
    )